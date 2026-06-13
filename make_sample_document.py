"""Baut eine realistische grosse Demo-Datei: banales Journal mit einer einzelnen
eingebetteten Krisenpassage (Nadel im Heuhaufen) -> sample_document.txt."""
import json

banal = [
    "Got up at 7, made coffee, answered some emails before work.",
    "Lunch with Sara today, we talked about the trip to Italy in autumn.",
    "Gym in the evening, legs day. Tired but good.",
    "Watched a documentary about the ocean. Pretty relaxing.",
    "Grocery shopping, forgot the milk again. Cooked pasta.",
    "Long meeting at work, mostly boring. Caught up with Tom afterwards.",
    "Rainy day, stayed in and read a book. Called mom about the weekend.",
    "Fixed the leaking tap finally. Small win.",
    "Went for a walk in the park, the leaves are turning.",
    "Planned the budget for next month, nothing exciting.",
]

crisis = (
    "I do not know why I am even writing this. Everything feels pointless and "
    "nothing will ever get better. I am so tired of pretending. I feel like a "
    "burden to everyone around me and they would honestly be better off without me. "
    "I have thought about it for weeks and I think I have a plan now. Tonight feels "
    "like the end. If anyone reads this, I am sorry. Goodbye."
)


def main():
    lines = []
    for day in range(1, 26):
        lines.append(f"--- Day {day} ---")
        # banale Eintraege
        for k in range(3):
            lines.append(banal[(day + k) % len(banal)])
        # an Tag 17 die Krisenpassage einbetten
        if day == 17:
            lines.append(crisis)
        lines.append("")
    text = "\n".join(lines)
    with open("sample_document.txt", "w", encoding="utf-8") as f:
        f.write(text)
    print(f"sample_document.txt: {len(text)} Zeichen, {len(text.split())} Wörter, "
          f"Krise an Tag 17 eingebettet.")


if __name__ == "__main__":
    main()
