"""
Kuratiert Demo-Beispiele aus der CSV fuer den Hackathon-Pitch.

Waehlt deterministisch je 3 hoch-/moderat-/niedrig-riskante echte Texte. Bewertung
erfolgt ueber den regelbasierten Baseline (mock_analyzer) -> keine API/kein Modell
noetig. Ergebnis: demos.json  [{"label","text","expected"}].

Aufruf:  python3 prepare_demos.py
"""
import csv
import json
import os

from mock_analyzer import analyze_text

csv.field_size_limit(10_000_000)
CSV_PATH = "data/reddit_depression_suicidewatch.csv"
OUT = "demos.json"

MIN_LEN, MAX_LEN = 120, 600


def clean(t: str) -> str:
    return " ".join(t.split())


def main():
    rows = []
    with open(CSV_PATH, newline="", encoding="utf-8", errors="replace") as f:
        for row in csv.DictReader(f):
            txt = clean(row.get("text") or "")
            if MIN_LEN <= len(txt) <= MAX_LEN:
                rows.append((txt, (row.get("label") or "").strip()))

    # Deterministisch: nach Textinhalt sortieren (kein Zufall, reproduzierbar).
    rows.sort(key=lambda r: r[0])

    high, moderate, low = [], [], []
    for txt, label in rows:
        res = analyze_text(txt)
        s = res["score"]
        if s >= 67 and len(high) < 3:
            high.append((txt, s))
        elif 34 <= s <= 60 and len(moderate) < 3:
            moderate.append((txt, s))
        elif s <= 15 and len(low) < 3:
            low.append((txt, s))
        if len(high) == 3 and len(moderate) == 3 and len(low) == 3:
            break

    demos = []
    for i, (txt, s) in enumerate(high, 1):
        demos.append({"label": f"Krise {i}", "text": txt, "expected": s})
    for i, (txt, s) in enumerate(moderate, 1):
        demos.append({"label": f"Moderat {i}", "text": txt, "expected": s})
    for i, (txt, s) in enumerate(low, 1):
        demos.append({"label": f"Kontrolle {i}", "text": txt, "expected": s})

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(demos, f, ensure_ascii=False, indent=2)
    print(f"{len(demos)} Demos geschrieben -> {OUT}")
    for d in demos:
        print(f"  {d['label']}  (Baseline-Score {d['expected']})  {d['text'][:60]}...")


if __name__ == "__main__":
    main()
