from enrichment import ssl_session as requests
from config import PERPLEXITY_KEY, PERPLEXITY_BASE


SYSTEM_PROMPT = (
    "Du bist ein spezialisierter Senior Business Analyst für den Schweizer Textil-, "
    "Mode- und Retail-Markt. Antworte ausschliesslich im JSON-Format."
)

USER_PROMPT = (
    "Recherchiere folgende Firma: {company}.\n"
    "Gib mir Branche, Mitarbeiterzahl (ca.), Hauptsitz, Umsatz (falls bekannt) "
    "und eine kurze Beschreibung (2 Sätze) zurück.\n"
    "Schema: {{\"Branche\": \"...\", \"Mitarbeiter\": \"...\", \"Sitz\": \"...\", "
    "\"Umsatz\": \"...\", \"Beschreibung\": \"...\"}}"
)


def get_company_overview(company_name: str) -> dict:
    try:
        resp = requests.post(
            f"{PERPLEXITY_BASE}/chat/completions",
            json={
                "model": "sonar",
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": USER_PROMPT.format(company=company_name)},
                ],
                "temperature": 0.2,
            },
            headers={
                "Authorization": f"Bearer {PERPLEXITY_KEY}",
                "Content-Type": "application/json",
            },
            timeout=30,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        import json, re
        cleaned = re.sub(r"```json\n?|```", "", content).strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # Robuster Fallback via json-repair
            try:
                from json_repair import repair_json
                return json.loads(repair_json(cleaned, return_objects=False))
            except Exception:
                # JSON-Block aus Text extrahieren als letzter Ausweg
                m = re.search(r"\{[^{}]*\}", cleaned, re.DOTALL)
                if m:
                    try:
                        return json.loads(m.group(0))
                    except Exception:
                        pass
                raise
    except Exception as exc:
        return {
            "Branche": "", "Mitarbeiter": "", "Sitz": "",
            "Umsatz": "", "Beschreibung": f"Fehler: {exc}",
        }
