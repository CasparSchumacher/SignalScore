"""
Echtes LLM-Backend fuer SignalScore.

ENDPOINT-AGNOSTISCH: spricht jeden OpenAI-kompatiblen Endpoint an. Damit laeuft
derselbe Code gegen
  - lokales MLX     (mlx_lm.server, M4-nativ, KEIN API-Key, DSGVO-freundlich)  <- Default
  - lokales Ollama  (ollama serve)
  - Groq / OpenAI / Azure / ...  (nur LLM_BASE_URL + LLM_API_KEY aendern)

Konfiguration via .env:
  LLM_BASE_URL   (default http://localhost:8080/v1   -> MLX)
  LLM_MODEL      (default mlx-community/Qwen2.5-7B-Instruct-4bit)
  LLM_API_KEY    (default "local"; bei Cloud-Anbietern echten Key eintragen)

Vertrag identisch zum Mock:  analyze_text(text: str) -> dict
"""
import json
import os
import re
import time

from dotenv import load_dotenv

from prompts import SYSTEM_PROMPT, load_markers

load_dotenv()

BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:8080/v1")
MODEL = os.getenv("LLM_MODEL", "mlx-community/Qwen2.5-7B-Instruct-4bit")
API_KEY = os.getenv("LLM_API_KEY", "local")
TIMEOUT = float(os.getenv("LLM_TIMEOUT", "60"))
MAX_RETRIES = 3

_VALID_TYPES = {c["type"] for c in load_markers()["categories"]}


def _client():
    # Lazy-Import, damit das Modul auch ohne installiertes openai-Paket importierbar bleibt.
    from openai import OpenAI
    return OpenAI(base_url=BASE_URL, api_key=API_KEY, timeout=TIMEOUT)


def _extract_json(raw: str) -> dict:
    """Robustes Parsen: entfernt Code-Fences, schneidet auf das erste {...}-Objekt."""
    s = raw.strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\n?", "", s)
        s = re.sub(r"\n?```$", "", s).strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        start, depth = s.find("{"), 0
        if start == -1:
            raise
        for i in range(start, len(s)):
            depth += (s[i] == "{") - (s[i] == "}")
            if depth == 0:
                return json.loads(s[start:i + 1])
        raise


def _validate(data: dict, original: str) -> dict:
    """Erzwingt den Vertrag: clamp score, valide types, Highlights MUESSEN Substrings sein."""
    score = data.get("score", 0)
    try:
        score = int(round(float(score)))
    except (TypeError, ValueError):
        score = 0
    score = max(0, min(100, score))

    level = data.get("risk_level")
    if level not in ("low", "medium", "high"):
        level = "high" if score >= 67 else "medium" if score >= 34 else "low"

    clean_highlights = []
    for h in data.get("highlights", []) or []:
        if not isinstance(h, dict):
            continue
        htext = h.get("text", "")
        htype = h.get("type", "")
        # KERNREGEL der Erklaerbarkeit: nur woertliche Substrings durchlassen.
        if htext and htext in original and htype in _VALID_TYPES:
            clean_highlights.append({
                "text": htext,
                "type": htype,
                "explanation": str(h.get("explanation", "")),
            })

    patterns = [p for p in (data.get("detected_patterns") or []) if p in _VALID_TYPES]
    if not patterns:
        patterns = sorted({h["type"] for h in clean_highlights})

    return {
        "score": score,
        "risk_level": level,
        "summary": str(data.get("summary", ""))[:500],
        "highlights": clean_highlights[:25],
        "detected_patterns": patterns,
    }


def _error(msg: str) -> dict:
    return {
        "score": -1, "risk_level": "error", "summary": f"Analysefehler: {msg}",
        "highlights": [], "detected_patterns": [],
    }


def analyze_text(text: str, max_retries: int = MAX_RETRIES) -> dict:
    if not text or not text.strip():
        return {"score": 0, "risk_level": "low", "summary": "Kein Text zur Analyse.",
                "highlights": [], "detected_patterns": []}

    try:
        client = _client()
    except Exception as e:  # openai nicht installiert o.ae.
        return _fallback(text, f"Client-Init fehlgeschlagen ({e})")

    last_err = None
    for attempt in range(max_retries):
        try:
            kwargs = dict(
                model=MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": text},
                ],
                temperature=0.2,
                max_tokens=700,  # begrenzt Latenz; JSON-Antwort ist kompakt
            )
            # JSON-Mode versuchen; manche lokale Server kennen das Feld nicht.
            try:
                resp = client.chat.completions.create(
                    response_format={"type": "json_object"}, **kwargs)
            except Exception:
                resp = client.chat.completions.create(**kwargs)

            raw = resp.choices[0].message.content
            return _validate(_extract_json(raw), text)
        except Exception as e:
            last_err = e
            # Endpoint nicht erreichbar -> nicht 3x warten, sofort Fallback (Demo-Tempo).
            if "Connection" in type(e).__name__ or "connect" in str(e).lower():
                break
            time.sleep(1.5 * (attempt + 1))  # linearer Backoff bei transienten Fehlern

    return _fallback(text, f"LLM nicht erreichbar nach {max_retries} Versuchen ({last_err})")


def _fallback(text: str, reason: str) -> dict:
    """
    Demo-Versicherung: faellt das LLM aus (Endpoint down, kein Paket), nutze den
    regelbasierten Keyword-Baseline aus mock_analyzer, damit die Demo nie leer ist.
    Markiert das Ergebnis transparent in der summary.
    """
    try:
        from mock_analyzer import analyze_text as mock
        res = mock(text)
        res["summary"] = f"[Keyword-Baseline – LLM offline] {res['summary']}"
        return res
    except Exception:
        return _error(reason)


if __name__ == "__main__":
    import pprint
    demo = ("I cannot do this anymore. Nothing matters and I feel like a burden. "
            "I have a plan and tonight feels like the end. Goodbye.")
    print(f"Endpoint: {BASE_URL}  Modell: {MODEL}")
    pprint.pprint(analyze_text(demo))
