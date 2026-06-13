"""
Mock-Analysator: liefert schema-konformes JSON OHNE LLM/API.

Kein blinder Platzhalter, sondern ein echter regelbasierter Keyword-Baseline auf
Basis von markers.json. Zweck:
  1) Das Frontend (app.py) kann sofort gegen `from mock_analyzer import analyze_text`
     bauen, ohne auf das LLM-Backend oder einen API-Key zu warten.
  2) Demos sehen schon plausibel aus (echte Treffer, echte Highlights).
Spaeter Einzeiler-Swap im Frontend:  from analyzer import analyze_text

analyze_text(text) erfuellt exakt denselben Vertrag wie das echte Backend.
"""
import json
import os
import re

_HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(_HERE, "markers.json"), encoding="utf-8") as _f:
    _MARKERS = json.load(_f)

_CATS = _MARKERS["categories"]
_WORD_RE = re.compile(r"[a-zA-Z']+")


def _risk_level(score: int) -> str:
    if score >= 67:
        return "high"
    if score >= 34:
        return "medium"
    return "low"


def _find_spans(text: str, term: str):
    """Findet alle exakten (case-insensitive) Vorkommen von term im Originaltext."""
    spans = []
    pattern = re.escape(term)
    # Bei Einzelwoertern auf Wortgrenzen achten, bei Phrasen nicht.
    if " " not in term and "-" not in term:
        pattern = r"\b" + pattern + r"\b"
    for m in re.finditer(pattern, text, flags=re.IGNORECASE):
        spans.append((m.start(), m.end(), text[m.start():m.end()]))
    return spans


def analyze_text(text: str) -> dict:
    """Regelbasierter Mock. Gibt denselben dict-Vertrag zurueck wie das LLM-Backend."""
    if not text or not text.strip():
        return {
            "score": 0, "risk_level": "low",
            "summary": "Kein Text zur Analyse.",
            "highlights": [], "detected_patterns": [],
        }

    tokens = _WORD_RE.findall(text.lower())
    n_tokens = max(1, len(tokens))

    raw = 0.0
    highlights = []
    detected = set()
    seen_spans = set()

    for cat in _CATS:
        ctype = cat["type"]
        weight = cat["weight"]

        # self_focus: als Dichte behandeln, NICHT markieren
        if cat.get("treat_as_density"):
            hits = sum(1 for t in tokens if t in set(cat["lexicon"]))
            density = hits / n_tokens
            if density > 0.10:  # auffaellig hohe Ich-Bezogenheit
                raw += weight * hits * 0.05
                detected.add(ctype)
            continue

        cat_hit = False
        for term in cat["lexicon"]:
            term_hits = 0
            for start, end, exact in _find_spans(text, term):
                if (start, end) in seen_spans:
                    continue
                # Wiederholungs-Deckel: dasselbe Wort zaehlt max. 3x (verhindert,
                # dass banale Wiederholung in langen Texten den Score inflationiert).
                if term_hits >= 3:
                    break
                term_hits += 1
                seen_spans.add((start, end))
                raw += weight
                cat_hit = True
                highlights.append({
                    "text": exact,
                    "type": ctype,
                    "explanation": cat["label_de"],
                })
        if cat_hit:
            detected.add(ctype)

    # Normalisierung auf 0-100 (heuristisch; gedaempfte Saettigung).
    # Laengen-normalisiert, damit lange Texte nicht automatisch hoch scoren.
    per_100 = raw / n_tokens * 100
    score = int(min(100, per_100 * 14))

    # Regel: ein imminence/method-Treffer hebt auf mindestens high.
    if ("imminence" in detected or "method_means" in detected) and score < 67:
        score = max(score, 70)

    level = _risk_level(score)
    if level == "high":
        summary = "Mehrere hochgewichtete Warnsignale erkannt. Dringende klinische Sichtung empfohlen."
    elif level == "medium":
        summary = "Moderate depressive Sprachmarker erkannt. Beobachtung empfohlen."
    else:
        summary = "Keine deutlichen Warnsignale in der Sprache erkannt."

    # Highlights begrenzen (Lesbarkeit im UI)
    highlights = highlights[:25]

    return {
        "score": score,
        "risk_level": level,
        "summary": summary,
        "highlights": highlights,
        "detected_patterns": sorted(detected),
    }


if __name__ == "__main__":
    demo = ("I cannot do this anymore. Nothing matters and I feel like a burden to everyone. "
            "I have a plan and tonight feels like the end. Goodbye.")
    import pprint
    pprint.pprint(analyze_text(demo))
