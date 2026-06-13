"""
Dokument-Analyse fuer GROSSE Texte (Chat-Exporte, Journale, WhatsApp-Verlaeufe).

Zwei-Stufen-Scan:
  Stufe 1 (schnell, ganzes Dokument): regelbasierter Baseline scort JEDES Segment
           -> Marker-Dichte + Identifikation der Hotspots.
  Stufe 2 (teuer, nur Hotspots): das LLM analysiert die auffaelligsten Segmente tief.

Scoring-Philosophie:
  - risk_level kommt vom SPITZENRISIKO (max. Segment-Score) -> akute Passagen werden
    in langen Texten NICHT verduennt.
  - Dichte (Treffer/1000 Woerter, % auffaelliger Segmente) wird SEPARAT ausgewiesen
    und setzt die Keywords ins Verhaeltnis zur Gesamtlaenge.
"""
import re

from mock_analyzer import analyze_text as _baseline

MAX_SEG_CHARS = 2500   # ~600-700 Tokens pro Segment
# Texte unter dieser Laenge gelten als "kurz" -> Einzelanalyse statt Dokument-Modus.
DOC_THRESHOLD_CHARS = 4000


def _risk_level(score: int) -> str:
    if score >= 67:
        return "high"
    if score >= 34:
        return "medium"
    return "low"


def chunk_text(text: str, max_chars: int = MAX_SEG_CHARS):
    """Teilt Text an Zeilen-/Absatzgrenzen in Segmente von ~max_chars Laenge."""
    lines = text.splitlines(keepends=True)
    segments, buf = [], ""
    for ln in lines:
        if len(buf) + len(ln) > max_chars and buf:
            segments.append(buf)
            buf = ""
        # ueberlange Einzelzeile hart schneiden
        while len(ln) > max_chars:
            segments.append(ln[:max_chars])
            ln = ln[max_chars:]
        buf += ln
    if buf.strip():
        segments.append(buf)
    return [s for s in segments if s.strip()]


def is_large(text: str) -> bool:
    return len(text) > DOC_THRESHOLD_CHARS


def analyze_document(text: str, deep_threshold: int = 34, max_deep: int = 8,
                     deep_fn=None) -> dict:
    """
    Analysiert ein grosses Dokument.
    deep_fn = LLM-Analysefunktion (default: analyzer.analyze_text, 1 Versuch).
    deep_threshold = ab welchem Baseline-Score ein Segment vom LLM verifiziert wird.
    max_deep = Obergrenze der LLM-Calls (Latenzschutz).

    WICHTIG: Der Gesamtscore kommt NUR von LLM-verifizierten Segmenten. Rohe
    Baseline-Keyword-Treffer (ohne Kontext) duerfen keinen HIGH-Alarm ausloesen.
    """
    if deep_fn is None:
        from analyzer import analyze_text as _at
        deep_fn = lambda t: _at(t, max_retries=1)  # noqa: E731

    words = len(re.findall(r"\S+", text))
    raw_segments = chunk_text(text)
    n = len(raw_segments)
    if n == 0:
        return {"mode": "document", "score": 0, "risk_level": "low",
                "summary": "Leeres Dokument.", "highlights": [], "detected_patterns": [],
                "document": {"words": 0, "n_segments": 0}}

    # --- Stufe 1: Baseline ueber ALLE Segmente (instant) ---
    segs = []
    total_hits = 0
    for i, seg_text in enumerate(raw_segments):
        b = _baseline(seg_text)
        total_hits += len(b["highlights"])
        segs.append({"idx": i, "text": seg_text, "baseline": b,
                     "score": b["score"], "deep": None})

    elevated = [s for s in segs if s["baseline"]["score"] >= 34]
    frac_elevated = len(elevated) / n
    hits_per_1000 = (total_hits / words * 1000) if words else 0.0

    # --- Stufe 2: LLM verifiziert ALLE Kandidaten-Segmente (Baseline >= Schwelle) ---
    # Patterns sammeln wir NUR aus verifizierten Segmenten -> keine unkontextua-
    # lisierten Baseline-Falschmeldungen im Ergebnis.
    patterns = set()
    ranked = sorted(segs, key=lambda s: -s["baseline"]["score"])
    candidates = [s for s in ranked if s["baseline"]["score"] >= deep_threshold]
    if not candidates and ranked and ranked[0]["baseline"]["score"] > 0:
        candidates = ranked[:1]  # zumindest das auffaelligste Segment verifizieren
    hotspots = candidates[:max_deep]
    for s in hotspots:
        d = deep_fn(s["text"])
        if d.get("risk_level") != "error":
            s["deep"] = d
            s["score"] = d["score"]
            patterns |= set(d.get("detected_patterns", []))

    # --- Aggregation: Spitzenrisiko treibt den Gesamtscore (keine Verduennung) ---
    overall = max(s["score"] for s in segs)
    level = _risk_level(overall)
    peak = max(segs, key=lambda s: s["score"])
    peak_src = peak["deep"] or peak["baseline"]

    pct = round(frac_elevated * 100)
    summary = (
        f"Dokument mit {n} Segmenten ({words} Wörtern). "
        f"Spitzenrisiko {level.upper()} in Segment {peak['idx'] + 1}. "
        f"Erhöhte Marker in {pct}% der Segmente. "
        f"{peak_src.get('summary', '')}"
    )

    # Hotspot-Details fuers UI (mit reichen Highlights)
    hotspot_details = []
    for s in sorted(hotspots, key=lambda s: -s["score"]):
        src = s["deep"] or s["baseline"]
        hotspot_details.append({
            "idx": s["idx"], "score": s["score"], "risk_level": _risk_level(s["score"]),
            "summary": src.get("summary", ""), "text": s["text"],
            "highlights": src.get("highlights", []),
            "deep": s["deep"] is not None,
        })

    # Gemergte Highlights (nur Hotspots) + Muster (gesamt)
    merged_highlights = [h for hd in hotspot_details for h in hd["highlights"]]

    return {
        "mode": "document",
        "score": overall,
        "risk_level": level,
        "summary": summary,
        "highlights": merged_highlights,
        "detected_patterns": sorted(patterns),
        "document": {
            "words": words,
            "n_segments": n,
            "analyzed_segments": len(hotspots),
            "hits_per_1000": round(hits_per_1000, 1),
            "fraction_elevated": round(frac_elevated, 3),
            "peak_segment": peak["idx"],
            "timeline": [{"idx": s["idx"], "score": s["score"],
                          "is_hotspot": s["deep"] is not None} for s in segs],
            "hotspots": hotspot_details,
        },
    }


if __name__ == "__main__":
    import pprint
    # Mini-Test mit eingebetteter Krisenpassage in viel banalem Text
    banal = ("Today I went to the store and bought some groceries. The weather was fine. "
             "I watched a movie in the evening. ") * 40
    crisis = ("\n\nI cannot do this anymore. Nothing matters and I am a burden to everyone. "
              "I have a plan and tonight feels like the end. Goodbye.\n\n")
    more = ("Then I cleaned the kitchen and called my mother about the weekend plans. ") * 40
    doc = banal + crisis + more
    res = analyze_document(doc, deep_fn=_baseline)  # Baseline als deep_fn fuer schnellen Test
    print(f"Laenge: {len(doc)} Zeichen")
    pprint.pprint({k: v for k, v in res.items() if k != "highlights"})
