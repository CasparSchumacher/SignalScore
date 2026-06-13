"""
SignalScore – Streamlit-Frontend.

Score-Ampel + farbige, erklaerende Highlights + Demo-Buttons.
Importiert analyze_text aus analyzer.py (faellt automatisch auf den regelbasierten
Baseline zurueck, falls kein LLM erreichbar ist -> laeuft immer).
"""
import html
import json
import os

import streamlit as st

from analyzer import analyze_text
from document import analyze_document, is_large
from prompts import load_markers

st.set_page_config(page_title="SignalScore", page_icon="🩺", layout="wide")

# --- Marker-Farben/Labels aus der Quelle der Wahrheit ---
_CATS = {c["type"]: c for c in load_markers()["categories"]}


@st.cache_data
def load_demos():
    if os.path.exists("demos.json"):
        with open("demos.json", encoding="utf-8") as f:
            return json.load(f)
    return [
        {"label": "Beispiel A", "text": "I cannot do this anymore. Nothing matters and I feel like a burden. I have a plan and tonight feels like the end. Goodbye."},
        {"label": "Beispiel B", "text": "Work has been stressful and I feel a bit down lately, but the weekend helped."},
    ]


def chip(ctype: str) -> str:
    c = _CATS.get(ctype, {})
    return (f'<span style="background:{c.get("color","#ddd")};color:#111;border-radius:10px;'
            f'padding:2px 8px;font-size:.8rem;margin:2px;display:inline-block;">'
            f'{c.get("label_de", ctype)}</span>')


def render_glossary(types, heading: str):
    """Psychologisch fundierte Erklaerung der angegebenen Marker-Kategorien."""
    st.markdown(f"**{heading}**")
    st.caption("Dies sind sprachliche Marker, **keine Diagnosen** – sie unterstützen die "
               "Einschätzung durch Fachpersonal.")
    for t in types:
        c = _CATS.get(t)
        if not c:
            continue
        st.markdown(
            f'<div style="border-left:4px solid {c["color"]};padding:4px 0 4px 12px;margin:8px 0;">'
            f'<span style="font-weight:600;">{c["label_de"]}</span> '
            f'<span style="color:#888;font-size:.8rem;">(Gewicht {c["weight"]})</span><br>'
            f'<span>{c.get("what","")}</span><br>'
            f'<span style="color:#aaa;font-size:.9rem;"><i>Warum relevant:</i> {c.get("why","")}</span><br>'
            f'<span style="color:#777;font-size:.78rem;">Quelle: {c.get("source","")}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )


def ampel_color(score: int) -> str:
    if score >= 67:
        return "#d32f2f"
    if score >= 34:
        return "#f9a825"
    return "#2e7d32"


def render_document(res: dict):
    """Dokument-Ansicht fuer grosse Texte: Dichte-Metriken, Risiko-Timeline, Hotspots."""
    doc = res["document"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Wörter", f"{doc['words']:,}".replace(",", "."))
    c2.metric("Segmente", doc["n_segments"])
    c3.metric("Treffer / 1.000 W.", doc["hits_per_1000"])
    c4.metric("Auffällige Segmente", f"{round(doc['fraction_elevated'] * 100)} %")
    st.caption("**Score = Spitzenrisiko** (kritischstes Segment, nicht verwässert). "
               "**Dichte** zeigt, wie durchgängig die Belastung ist.")

    st.markdown("**Risiko-Verlauf über das Dokument**")
    st.caption("Jeder Balken = ein Segment · Höhe/Farbe = Risiko · ▲ = LLM-tiefenanalysiert")
    tl = doc["timeline"]
    step = max(1, len(tl) // 150)  # bei sehr vielen Segmenten ausduennen
    shown = tl[::step]
    bars = []
    for seg in shown:
        s = seg["score"]
        h = max(3, int(s * 0.55))
        mark = "▲" if seg["is_hotspot"] else "&nbsp;"
        bars.append(
            f'<div title="Segment {seg["idx"] + 1}: Score {s}" '
            f'style="flex:1;display:flex;flex-direction:column;justify-content:flex-end;align-items:center;min-width:2px;">'
            f'<div style="font-size:.55rem;color:#aaa;line-height:1;">{mark}</div>'
            f'<div style="width:100%;height:{h}px;background:{ampel_color(s)};border-radius:2px 2px 0 0;"></div></div>'
        )
    note = f" (von {len(tl)} Segmenten ausgedünnt dargestellt)" if step > 1 else ""
    st.markdown(
        f'<div style="display:flex;gap:1px;align-items:flex-end;height:75px;border-bottom:1px solid #555;">{"".join(bars)}</div>'
        f'<div style="font-size:.7rem;color:#888;text-align:right;">{note}</div>',
        unsafe_allow_html=True,
    )

    st.subheader("🔎 Kritische Stellen")
    for hs in doc["hotspots"]:
        tag = "LLM-Tiefenanalyse" if hs["deep"] else "Keyword-Baseline"
        with st.expander(
            f"Segment {hs['idx'] + 1} · Score {hs['score']} · {hs['risk_level'].upper()} · {tag}",
            expanded=(hs["risk_level"] == "high"),
        ):
            st.write(hs["summary"])
            st.markdown(
                f'<div style="line-height:1.8;font-size:1.02rem;">{render_highlighted(hs["text"], hs["highlights"])}</div>',
                unsafe_allow_html=True,
            )
            used = {h["type"] for h in hs["highlights"]}
            if used:
                st.markdown("**Muster:** " + " ".join(chip(t) for t in used), unsafe_allow_html=True)


def render_highlighted(text: str, highlights: list) -> str:
    """Markiert highlights[].text im Originaltext. Loest Ueberlappungen auf
    (hoeheres Gewicht / laengere Phrase gewinnt) und escaped HTML sicher."""
    n = len(text)
    owner = [None] * n  # pro Zeichen: type-id oder None

    def weight(t):
        return _CATS.get(t, {}).get("weight", 0)

    # laengere & hoeher gewichtete zuerst -> haben Vorrang bei Ueberlappung
    ordered = sorted(highlights, key=lambda h: (-weight(h.get("type", "")), -len(h.get("text", ""))))
    low = text.lower()
    for h in ordered:
        term = (h.get("text") or "")
        ttype = h.get("type", "")
        if not term:
            continue
        start = 0
        tl = term.lower()
        while True:
            idx = low.find(tl, start)
            if idx == -1:
                break
            if all(owner[i] is None for i in range(idx, idx + len(term))):
                for i in range(idx, idx + len(term)):
                    owner[i] = ttype
            start = idx + len(term)

    # zusammenhaengende Laeufe rendern
    out, i = [], 0
    while i < n:
        t = owner[i]
        j = i
        while j < n and owner[j] == t:
            j += 1
        chunk = html.escape(text[i:j])
        if t:
            color = _CATS.get(t, {}).get("color", "#ddd")
            label = _CATS.get(t, {}).get("label_de", t)
            out.append(
                f'<span style="background:{color};color:#111;border-radius:3px;'
                f'padding:1px 3px;" title="{html.escape(label)}">{chunk}</span>'
            )
        else:
            out.append(chunk)
        i = j
    return "".join(out).replace("\n", "<br>")


# ============================ UI ============================
st.title("🩺 SignalScore")
st.caption("Erklärbare linguistische Risiko-Analyse für Depression & Suizidalität – "
           "Decision-Support für klinisches Fachpersonal.")

st.warning(
    "**Decision-Support, kein Ersatz für klinische Diagnose.** "
    "Im Krisenfall: Notruf **112** · Telefonseelsorge **0800 111 0 111**.",
    icon="⚠️",
)

if "input_text" not in st.session_state:
    st.session_state.input_text = ""

with st.sidebar:
    st.subheader("Demo-Beispiele")
    st.caption("Vordefinierte echte Texte – latenz- und tippfehlerfrei für den Pitch.")
    for d in load_demos():
        if st.button(d["label"], use_container_width=True, key=d["label"]):
            st.session_state.input_text = d["text"]

    if os.path.exists("sample_document.txt"):
        if st.button("📄 Großes Dokument (Journal)", use_container_width=True, key="__doc__"):
            with open("sample_document.txt", encoding="utf-8") as f:
                st.session_state.input_text = f.read()

    st.divider()
    with st.expander("📖 Marker-Glossar (alle Warnsignale)"):
        all_types = [c["type"] for c in sorted(_CATS.values(), key=lambda c: -c["weight"])]
        render_glossary(all_types, "Alle linguistischen Marker")

left, right = st.columns([1, 1])

with left:
    st.subheader("Eingabe")
    uploaded = st.file_uploader(
        "Datei hochladen (Chat-Export, Journal, WhatsApp, .txt/.md/.csv/.log)",
        type=["txt", "md", "csv", "json", "log"])
    file_text = None
    if uploaded is not None:
        file_text = uploaded.read().decode("utf-8", errors="replace")
        st.info(f"📄 **{uploaded.name}** — {len(file_text):,} Zeichen, "
                f"{len(file_text.split()):,} Wörter".replace(",", "."))
    text_input = st.text_area(
        "Zu analysierender Text", value=st.session_state.input_text, height=240,
        label_visibility="collapsed",
        placeholder="Text einfügen, Demo wählen — oder oben eine Datei hochladen …")
    analyze = st.button("🔍 Analysieren", type="primary", use_container_width=True)

# Hochgeladene Datei hat Vorrang vor dem Textfeld.
text = file_text if (file_text and file_text.strip()) else text_input

# Genau EIN Analyse-Aufruf pro Klick. Grosse Texte -> Dokument-Modus (Zwei-Stufen-Scan).
res = None
if analyze and text.strip():
    if is_large(text):
        with st.spinner("Dokument-Scan (Stufe 1: ganzes Dokument · Stufe 2: Hotspots) …"):
            res = analyze_document(text)
    else:
        with st.spinner("Analysiere …"):
            res = analyze_text(text)

with right:
    st.subheader("Ergebnis")
    if res is not None:
        if res.get("risk_level") == "error":
            st.error(res.get("summary", "Analysefehler."))
        else:
            score = res["score"]
            color = ampel_color(score)
            st.markdown(
                f'<div style="font-size:3rem;font-weight:700;color:{color};line-height:1;">'
                f'{score}<span style="font-size:1rem;color:#888;"> / 100</span></div>'
                f'<div style="height:14px;background:#eee;border-radius:7px;overflow:hidden;margin:8px 0;">'
                f'<div style="width:{score}%;height:100%;background:{color};"></div></div>'
                f'<div style="font-weight:600;color:{color};text-transform:uppercase;letter-spacing:1px;">'
                f'Risiko: {res["risk_level"]}</div>',
                unsafe_allow_html=True,
            )
            st.write(res["summary"])
            if res.get("detected_patterns"):
                chips = " ".join(chip(p) for p in res["detected_patterns"])
                st.markdown("**Erkannte Muster:** " + chips, unsafe_allow_html=True)
                with st.expander("ℹ️ Was bedeuten diese Muster?"):
                    render_glossary(res["detected_patterns"], "Erläuterung der erkannten Muster")
    elif analyze:
        st.info("Bitte zuerst Text eingeben.")
    else:
        st.info("Text eingeben und **Analysieren** klicken.")

# --- Vollbreite-Sektion: Dokument-Ansicht ODER markierter Einzeltext ---
if res is not None and res.get("risk_level") != "error":
    st.divider()
    if res.get("mode") == "document":
        render_document(res)
    else:
        st.subheader("Begründung im Text")
        st.markdown(
            f'<div style="line-height:1.9;font-size:1.05rem;">{render_highlighted(text, res["highlights"])}</div>',
            unsafe_allow_html=True,
        )
        used = {h["type"] for h in res["highlights"]}
        if used:
            leg = " ".join(
                f'<span style="background:{_CATS[t]["color"]};color:#111;border-radius:3px;'
                f'padding:1px 6px;margin:2px;font-size:.8rem;">{_CATS[t]["label_de"]}</span>'
                for t in used if t in _CATS
            )
            st.markdown("**Legende:** " + leg, unsafe_allow_html=True)
