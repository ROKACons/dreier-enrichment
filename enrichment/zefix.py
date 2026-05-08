"""
ZEFIX Lookup:
- SerpAPI findet die zefix.ch-URL (zuverlässig)
- Perplexity liefert UID / Adresse / Rechtsform als Bonus
"""
import json
import re
from enrichment import ssl_session as requests
from config import SERPAPI_KEY, SERPAPI_BASE, PERPLEXITY_KEY, PERPLEXITY_BASE


def lookup(company_name: str) -> dict:
    """Suche ZEFIX-URL und Handelsregisterdaten."""
    result = _not_found()

    # ── 1. ZEFIX-URL via SerpAPI (sehr zuverlässig) ────────────────────────
    zefix_url = _find_zefix_url(company_name)
    if zefix_url:
        result["zefix_gefunden"] = True
        result["zefix_url"] = zefix_url

    # ── 2. Handelsregister-Daten via Perplexity (Best-Effort) ─────────────
    try:
        prompt = (
            f"Suche im Schweizer Handelsregister (zefix.ch) nach: {company_name}\n"
            f"Antworte NUR mit diesem JSON (kein Markdown):\n"
            f'{{"uid":"CHE-...", "name_offiziell":"...", "rechtsform":"AG/GmbH/...", '
            f'"plz":"...", "ort":"...", "kanton":"...", '
            f'"branche":"Zweck aus Handelsregister max 200 Zeichen", '
            f'"entscheider":"CEO/VR-Mitglieder falls bekannt"}}\n'
            f"Nur echte Daten aus dem Handelsregister. Nichts erfinden."
        )
        resp = requests.post(
            f"{PERPLEXITY_BASE}/chat/completions",
            json={
                "model": "sonar",
                "messages": [
                    {"role": "system", "content": "Antworte ausschliesslich mit einem JSON-Objekt."},
                    {"role": "user",   "content": prompt},
                ],
                "temperature": 0.1,
            },
            headers={
                "Authorization": f"Bearer {PERPLEXITY_KEY}",
                "Content-Type": "application/json",
            },
            timeout=25,
        )
        if resp.status_code == 200:
            raw = resp.json()["choices"][0]["message"]["content"]
            raw = re.sub(r"```json\n?|```", "", raw).strip()
            data = json.loads(raw)
            for field in ["uid", "name_offiziell", "rechtsform", "plz", "ort", "kanton",
                          "branche", "entscheider"]:
                val = data.get(field, "")
                if val and val not in ("...", "–", "null", "None", ""):
                    result[field] = val
            if result.get("uid") or result.get("ort"):
                result["zefix_gefunden"] = True
    except Exception:
        pass  # Perplexity-Fehler: kein Problem, Fallback auf vorhandene Daten

    return result


def _find_zefix_url(company_name: str) -> str:
    """Findet die zefix.ch-URL via SerpAPI."""
    try:
        resp = requests.get(
            SERPAPI_BASE,
            params={
                "api_key": SERPAPI_KEY,
                "engine": "google",
                "q": f"site:zefix.ch {company_name}",
                "num": "5",
                "gl": "ch",
                "hl": "de",
            },
            timeout=15,
        )
        resp.raise_for_status()
        for r in resp.json().get("organic_results", []):
            link = r.get("link", "")
            if "zefix.ch" in link and "/firm/" in link:
                return link
    except Exception:
        pass
    return ""


def _not_found() -> dict:
    return {
        "zefix_gefunden": False,
        "zefix_url": "",
        "uid": "", "name_offiziell": "", "rechtsform": "",
        "plz": "", "ort": "", "kanton": "",
        "branche": "", "entscheider": "",
    }
