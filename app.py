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


def ampel_color(score: int) -> str:
    if score >= 67:
        return "#d32f2f"
    if score >= 34:
        return "#f9a825"
    return "#2e7d32"


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

left, right = st.columns([1, 1])

with left:
    st.subheader("Eingabe")
    text = st.text_area("Zu analysierender Text", value=st.session_state.input_text,
                        height=320, label_visibility="collapsed",
                        placeholder="Text hier einfügen oder ein Demo-Beispiel wählen …")
    analyze = st.button("🔍 Analysieren", type="primary", use_container_width=True)

# Genau EIN Analyse-Aufruf pro Klick.
res = None
if analyze and text.strip():
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
                chips = " ".join(
                    f'<span style="background:{_CATS.get(p,{}).get("color","#ddd")};'
                    f'color:#111;border-radius:10px;padding:2px 8px;font-size:.8rem;margin:2px;'
                    f'display:inline-block;">{_CATS.get(p,{}).get("label_de",p)}</span>'
                    for p in res["detected_patterns"]
                )
                st.markdown("**Erkannte Muster:** " + chips, unsafe_allow_html=True)
    elif analyze:
        st.info("Bitte zuerst Text eingeben.")
    else:
        st.info("Text eingeben und **Analysieren** klicken.")

# --- Markierter Text in voller Breite ---
if res is not None:
    if res.get("risk_level") != "error":
        st.divider()
        st.subheader("Begründung im Text")
        st.markdown(
            f'<div style="line-height:1.9;font-size:1.05rem;">{render_highlighted(text, res["highlights"])}</div>',
            unsafe_allow_html=True,
        )
        # Legende
        used = {h["type"] for h in res["highlights"]}
        if used:
            leg = " ".join(
                f'<span style="background:{_CATS[t]["color"]};color:#111;border-radius:3px;'
                f'padding:1px 6px;margin:2px;font-size:.8rem;">{_CATS[t]["label_de"]}</span>'
                for t in used if t in _CATS
            )
            st.markdown("**Legende:** " + leg, unsafe_allow_html=True)
