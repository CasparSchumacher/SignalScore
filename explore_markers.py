#!/usr/bin/env python3
"""
Marker-Exploration fuer den Depression/Suizidalitaet-Analysator.

Zweck: NICHT trainieren, sondern (1) theoriegetriebene linguistische Marker auf
echten Daten validieren und (2) datengetrieben entdecken, welche Woerter
Krisentexte (SuicideWatch) von normaler Depression abheben.

Ergebnis: ein evidenzbasiertes Lexikon + Effektgroessen, das in den System-Prompt
einfliesst.
"""
import csv, re, math, sys
from collections import Counter, defaultdict

CSV_PATH = "data/reddit_depression_suicidewatch.csv"
csv.field_size_limit(10_000_000)

# ----------------------------------------------------------------------------
# 1) THEORIEGETRIEBENE SAAT-LEXIKA  (Kategorie -> Wort/Phrase)
#    Quellen: Al-Mosaiwi & Johnson-Laird 2018 (Absolutismus),
#             Pennebaker (Ich-Bezogenheit), klinische Standardmarker.
# ----------------------------------------------------------------------------
LEXICONS = {
    "absolutism": [
        "absolutely","all","always","complete","completely","constant","constantly",
        "definitely","entire","ever","every","everyone","everything","full","must",
        "never","nothing","totally","whole","no one","nobody","forever",
    ],
    "self_focus": ["i","me","my","mine","myself"],
    "social_words": ["we","us","our","ours","ourselves","they","them","friend","friends","people"],
    "hopelessness": [
        "hopeless","pointless","useless","worthless","no point","no future","give up",
        "gave up","giving up","nothing matters","never get better","no way out","trapped",
        "stuck","can't go on","cant go on","no hope","meaningless","empty","numb",
    ],
    "worthlessness": [
        "worthless","failure","burden","hate myself","pathetic","disgusting","ashamed",
        "not good enough","unlovable","broken","weak",
    ],
    "social_withdrawal": [
        "alone","lonely","nobody","no one","isolated","no friends","by myself",
        "withdraw","avoid","disconnect",
    ],
    "suicidal_ideation": [
        "suicide","suicidal","kill myself","end it","end my life","want to die","die",
        "death","dead","better off dead","no reason to live","not be here","disappear",
        "overdose","goodbye","self harm","self-harm","cut myself","hurt myself","jump",
    ],
}

# ----------------------------------------------------------------------------
# Daten laden
# ----------------------------------------------------------------------------
def load():
    rows = []
    with open(CSV_PATH, newline="", encoding="utf-8", errors="replace") as f:
        r = csv.DictReader(f)
        for row in r:
            text = (row.get("text") or "").strip()
            label = (row.get("label") or "").strip()
            if text and label:
                rows.append((text.lower(), label))
    return rows

WORD_RE = re.compile(r"[a-z']+")
def tokenize(t):
    return WORD_RE.findall(t)

def count_lexicon_hits(text, terms):
    """Zaehlt Vorkommen (Woerter exakt, Mehrwort-Phrasen als Substring)."""
    toks = tokenize(text)
    tokset = Counter(toks)
    n = 0
    for term in terms:
        if " " in term or "-" in term:
            n += text.count(term)
        else:
            n += tokset.get(term, 0)
    return n

def main():
    rows = load()
    by_label = defaultdict(list)
    for text, label in rows:
        by_label[label].append(text)
    labels = sorted(by_label)
    print("="*78)
    print("DATENSATZ-UEBERBLICK")
    print("="*78)
    total_tokens = {}
    for lab in labels:
        texts = by_label[lab]
        toks = sum(len(tokenize(t)) for t in texts)
        total_tokens[lab] = toks
        lens = [len(tokenize(t)) for t in texts]
        lens.sort()
        med = lens[len(lens)//2]
        print(f"  {lab:14s}  Posts={len(texts):6d}  Tokens={toks:9d}  "
              f"Median-Laenge={med:4d} Woerter")
    print()

    # ------------------------------------------------------------------
    # 2) MARKER-RATEN PRO LABEL  (Treffer pro 1000 Woerter)
    # ------------------------------------------------------------------
    print("="*78)
    print("MARKER-RATEN  (Treffer pro 1000 Woerter)  -- validiert die Kategorien")
    print("="*78)
    print(f"  {'Kategorie':18s} {labels[0]:>14s} {labels[1]:>14s}   {'SW/dep-Ratio':>12s}")
    print("  " + "-"*64)
    cat_rates = {}
    for cat, terms in LEXICONS.items():
        rates = {}
        for lab in labels:
            hits = sum(count_lexicon_hits(t, terms) for t in by_label[lab])
            rates[lab] = 1000.0 * hits / max(1, total_tokens[lab])
        cat_rates[cat] = rates
        sw = rates.get("SuicideWatch", 0)
        dep = rates.get("depression", 1e-9)
        ratio = sw / dep if dep else float("inf")
        flag = "  <== erhoeht" if ratio > 1.15 else ("  (depression hoeher)" if ratio < 0.87 else "")
        print(f"  {cat:18s} {rates[labels[0]]:14.2f} {rates[labels[1]]:14.2f}   {ratio:11.2f}x{flag}")
    print()

    # ------------------------------------------------------------------
    # 3) DATENGETRIEBENE ENTDECKUNG: gewichtete Log-Odds mit Dirichlet-Prior
    #    (Monroe, Colaresi & Quinn 2008) -> welche Woerter heben SuicideWatch
    #    statistisch von depression ab? z-score als Signifikanz.
    # ------------------------------------------------------------------
    print("="*78)
    print("DATENGETRIEBEN: Woerter, die SuicideWatch am staerksten von depression")
    print("abheben  (gewichtete Log-Odds, z-score)  -- entdeckt echte Marker")
    print("="*78)
    STOP = set("the a an and or but if of to in on at for with as is are was were be "
               "been being have has had do does did i you he she it we they me my your "
               "this that these those so just like get got would could should will can "
               "not no yes about out up down all any from then than them his her our "
               "what when who how why which there here im ive dont cant thats really "
               "very too much even more most some who whom into over".split())
    cnt = {lab: Counter() for lab in labels}
    for lab in labels:
        for t in by_label[lab]:
            cnt[lab].update(w for w in tokenize(t) if len(w) > 2 and w not in STOP)
    vocab = set()
    for lab in labels:
        vocab |= {w for w, c in cnt[lab].items() if c >= 25}  # nur haeufige Woerter
    n1 = sum(cnt["SuicideWatch"][w] for w in vocab)
    n2 = sum(cnt["depression"][w] for w in vocab)
    a0 = 0.01  # uninformativer Prior pro Wort
    A0 = a0 * len(vocab)
    scored = []
    for w in vocab:
        y1, y2 = cnt["SuicideWatch"][w], cnt["depression"][w]
        l1 = math.log((y1 + a0) / (n1 + A0 - y1 - a0))
        l2 = math.log((y2 + a0) / (n2 + A0 - y2 - a0))
        delta = l1 - l2
        var = 1.0/(y1 + a0) + 1.0/(y2 + a0)
        z = delta / math.sqrt(var)
        scored.append((z, w, y1, y2))
    scored.sort(reverse=True)
    print("\n  >>> Stark Richtung SUICIDEWATCH (akute Krise):")
    print(f"  {'Wort':18s} {'z':>7s} {'SW':>6s} {'dep':>6s}")
    for z, w, y1, y2 in scored[:30]:
        print(f"  {w:18s} {z:7.1f} {y1:6d} {y2:6d}")
    print("\n  >>> Stark Richtung DEPRESSION (chronisch, weniger akut):")
    for z, w, y1, y2 in scored[-15:][::-1]:
        print(f"  {w:18s} {z:7.1f} {y1:6d} {y2:6d}")
    print()
    print("="*78)
    print("FERTIG. Interpretation folgt im Chat.")
    print("="*78)

if __name__ == "__main__":
    main()
