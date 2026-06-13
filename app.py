"""
WordMood – Streamlit-Frontend.

Score-Anzeige + farbige, erklaerende Highlights + Demo-Beispiele.
Importiert analyze_text aus analyzer.py (faellt automatisch auf den regelbasierten
Baseline zurueck, falls kein LLM erreichbar ist -> laeuft immer).
"""
import base64
import html
import json
import os

import streamlit as st

from analyzer import analyze_text
from document import analyze_document, is_large
from prompts import load_markers

st.set_page_config(page_title="WordMood", layout="wide")

# --- Marker-Farben/Labels aus der Quelle der Wahrheit ---
_CATS = {c["type"]: c for c in load_markers()["categories"]}

_BRAND_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600;700&family=Inter:wght@400;500;600;700&display=swap');

.stApp {
  background:
    radial-gradient(1100px 600px at 88% 10%, rgba(31,200,200,0.16), transparent 62%),
    radial-gradient(820px 520px at 94% 90%, rgba(58,210,159,0.12), transparent 60%),
    linear-gradient(160deg,#091a33 0%,#0b1f3a 55%,#0c2547 100%);
  color:#e7eef8;
}
html, body, [class*="css"], .stMarkdown, p, span, div, label, input, textarea, button { font-family:'Inter',sans-serif; }
h1,h2,h3 { font-family:'Playfair Display',serif !important; color:#f3f7fc; letter-spacing:.3px; font-weight:700; }
#MainMenu, footer, header[data-testid="stHeader"] { visibility:hidden; height:0; }
section[data-testid="stSidebar"] { background:rgba(7,20,38,0.55); border-right:1px solid rgba(255,255,255,.06); }

.wm-brand { display:flex; align-items:center; gap:16px; margin:10px 0 2px; }
.wm-word { font-weight:700; font-size:2.8rem; line-height:1; letter-spacing:-.5px; }
.wm-word .w { color:#eef3fa; }
.wm-word .m { background:linear-gradient(90deg,#7a3ff0 0%,#2e6df0 45%,#1fc8c8 75%,#3ad29f 100%);
  -webkit-background-clip:text; background-clip:text; -webkit-text-fill-color:transparent; }
.wm-tag { color:#9db2cc; font-size:.95rem; margin-top:7px; font-weight:400; }

.wm-disclaimer { background:rgba(255,255,255,.035); border:1px solid rgba(255,255,255,.08);
  border-left:3px solid #1fc8c8; border-radius:10px; padding:11px 16px; font-size:.84rem;
  color:#aec4dd; margin:16px 0 4px; }
.wm-disclaimer b { color:#d7e6f6; }

.stButton > button { border-radius:10px; border:1px solid rgba(255,255,255,.12);
  background:rgba(255,255,255,.04); color:#dde7f4; font-weight:500; transition:all .15s ease; }
.stButton > button:hover { border-color:#2e6df0; background:rgba(46,109,240,.14); color:#fff; }
.stButton > button[kind="primary"] { background:linear-gradient(90deg,#7a3ff0,#2e6df0);
  border:none; color:#fff; font-weight:600; }
.stButton > button[kind="primary"]:hover { filter:brightness(1.08); }

.stTextArea textarea, [data-testid="stFileUploaderDropzone"] {
  background:rgba(255,255,255,.03) !important; border-radius:10px !important; }
hr { border-color:rgba(255,255,255,.08); }
[data-testid="stMetricValue"] { font-family:'Playfair Display',serif; }
</style>
"""


def _logo_html(size: int = 52) -> str:
    """Echtes Logo aus assets/wordmood-logo.png, sonst SVG-Marke im Markenstil."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "wordmood-logo.png")
    if os.path.exists(path):
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        return f'<img src="data:image/png;base64,{b64}" style="height:{size}px;width:auto;border-radius:12px;">'
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">'
        '<defs><linearGradient id="wmg" x1="4" y1="6" x2="44" y2="42" gradientUnits="userSpaceOnUse">'
        '<stop stop-color="#7a3ff0"/><stop offset="0.5" stop-color="#2e6df0"/><stop offset="1" stop-color="#3ad29f"/>'
        '</linearGradient></defs>'
        '<rect x="2" y="2" width="44" height="44" rx="13" fill="url(#wmg)" opacity="0.16"/>'
        '<g fill="url(#wmg)">'
        '<rect x="11" y="13" width="14" height="3.2" rx="1.6"/>'
        '<rect x="11" y="19.5" width="22" height="3.2" rx="1.6"/>'
        '<rect x="11" y="26" width="12" height="3.2" rx="1.6"/>'
        '<rect x="11" y="32.5" width="18" height="3.2" rx="1.6"/>'
        '</g></svg>'
    )


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
        return "#e5484d"   # rose
    if score >= 34:
        return "#e0a93a"   # amber
    return "#2bb673"       # emerald


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

    st.subheader("Kritische Stellen")
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
st.markdown(_BRAND_CSS, unsafe_allow_html=True)
st.markdown(
    f'<div class="wm-brand">{_logo_html()}'
    '<div><div class="wm-word"><span class="w">Word</span><span class="m">Mood</span></div>'
    '<div class="wm-tag">Erklärbare linguistische Risiko-Analyse · Decision-Support für klinisches Fachpersonal</div>'
    '</div></div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="wm-disclaimer"><b>Decision-Support, kein Ersatz für klinische Diagnose.</b> '
    'Im Krisenfall: Notruf <b>112</b> · Telefonseelsorge <b>0800 111 0 111</b>.</div>',
    unsafe_allow_html=True,
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
        if st.button("Großes Dokument (Journal)", use_container_width=True, key="__doc__"):
            with open("sample_document.txt", encoding="utf-8") as f:
                st.session_state.input_text = f.read()

    st.divider()
    with st.expander("Marker-Glossar"):
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
        raw = uploaded.read()
        file_text = None
        for enc in ("utf-8", "cp1252", "latin-1"):  # WhatsApp/Word-Exporte variieren
            try:
                file_text = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        if file_text is None:
            file_text = raw.decode("utf-8", errors="replace")
        st.info(f"**{uploaded.name}** — {len(file_text):,} Zeichen, "
                f"{len(file_text.split()):,} Wörter".replace(",", "."))
    text_input = st.text_area(
        "Zu analysierender Text", value=st.session_state.input_text, height=240,
        label_visibility="collapsed",
        placeholder="Text einfügen, Demo wählen — oder oben eine Datei hochladen …")
    analyze = st.button("Analysieren", type="primary", use_container_width=True)

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
                f'<div style="font-family:\'Playfair Display\',serif;font-size:3.6rem;font-weight:700;color:{color};line-height:1;">'
                f'{score}<span style="font-size:1.1rem;color:#7e93ad;font-family:Inter,sans-serif;"> / 100</span></div>'
                f'<div style="height:10px;background:rgba(255,255,255,.08);border-radius:6px;overflow:hidden;margin:12px 0;">'
                f'<div style="width:{score}%;height:100%;background:{color};border-radius:6px;"></div></div>'
                f'<div style="font-weight:600;color:{color};text-transform:uppercase;letter-spacing:2px;font-size:.85rem;">'
                f'Risiko: {res["risk_level"]}</div>',
                unsafe_allow_html=True,
            )
            st.write(res["summary"])
            if res.get("detected_patterns"):
                chips = " ".join(chip(p) for p in res["detected_patterns"])
                st.markdown("**Erkannte Muster:** " + chips, unsafe_allow_html=True)
                with st.expander("Was bedeuten diese Muster?"):
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
