# SignalScore

Erklärbares Decision-Support-Werkzeug, das Freitext (Tagebuch, Forenpost, Chat) in
Sekunden auf sprachliche Warnsignale für **Depression und Suizidalität** prüft. Es
liefert einen **Risiko-Score 0–100**, markiert die begründenden Textstellen farbig
und gibt eine kurze klinische Einordnung.

> ⚠️ **Decision-Support, kein Ersatz für klinische Diagnose.** Zielgruppe ist
> geschultes psychiatrisches Fachpersonal / Triage. Im Krisenfall: Notruf **112**,
> Telefonseelsorge **0800 111 0 111**.

## Kernidee

Kein eigenes ML-Training. Wir steuern ein **fertiges LLM** (Claude/GPT) per
evidenzbasiertem System-Prompt zu einer strukturierten Analyse. USP =
**Erklärbarkeit** (man sieht *warum*) + **sofort einsatzbereit** (kein Training).

```
Text → [System-Prompt zwingt LLM zur Analyse] → strukturiertes JSON → UI mit Highlights
```

## Evidenz-Fundament

`markers.json` ist die einzige Wahrheit für die Bewertung. Die Kategorien + Gewichte
stammen aus:
- **Theorie**: Al-Mosaiwi & Johnson-Laird 2018 (Absolutismus), Pennebaker (Ich-Bezogenheit).
- **Daten**: gewichtete Log-Odds über 20.363 echte Reddit-Posts (`explore_markers.py`).

Wichtigste Befunde der Datenanalyse:
- Nur das **Suizidalitäts-Lexikon** trennt klar (2,71× erhöht in akuten Texten).
- Datengetrieben entdeckt: eigene Kategorien **Imminenz/Plan** und **Methode/Mittel**
  (`tonight, plan, note, goodbye, gun, pills, …`) — klinisch der stärkste Eskalator.
- **Caveat**: kein gesunder Kontrolldatensatz → `absolutism`/`self_focus` sind hier
  nicht als Krisenmarker validiert. Score-Achse misst **Akuität**, nicht krank-vs-gesund.

## JSON-Vertrag (Schnittstelle für alle Module)

`analyze_text(text: str) -> dict`:

```json
{
  "score": 73,
  "risk_level": "low | medium | high",
  "summary": "Kurze klinische Einordnung.",
  "highlights": [
    {"text": "exakter Substring", "type": "imminence", "explanation": "..."}
  ],
  "detected_patterns": ["imminence", "hopelessness"]
}
```
`type` ∈ `imminence, method_means, suicidal_ideation, hopelessness, worthlessness, absolutism, social_withdrawal, self_focus`.
`highlights[].text` ist **immer ein exakter Substring** des Eingabetexts (sonst nicht markierbar).

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # einen API-Key eintragen
streamlit run app.py
```

## Dateien

| Datei | Rolle | Status |
|---|---|---|
| `markers.json` | Evidenzbasiertes Marker-Modell (Quelle der Wahrheit) | ✅ |
| `explore_markers.py` | Reproduzierbare Datenanalyse | ✅ |
| `prompts.py` | System-Prompt, dynamisch aus markers.json | ✅ |
| `mock_analyzer.py` | Regelbasierter Baseline (kein API-Key nötig) | ✅ |
| `analyzer.py` | Echtes LLM-Backend (`analyze_text`) | ⏳ |
| `app.py` | Streamlit-Frontend (Score-Bar + Highlights) | ⏳ |
| `prepare_demos.py` / `demos.json` | Kuratierte Demo-Beispiele aus der CSV | ⏳ |
| `eval.py` | Sanity-Check (SuicideWatch-Score > depression-Score) | ⏳ |

## Daten

`data/reddit_depression_suicidewatch.csv` (`text,label`, ~20k Posts). Wird **nicht**
committet (`.gitignore`) — sensibel. Dient als Demo-Quelle und Eval-Material, **nicht**
zum Training.
