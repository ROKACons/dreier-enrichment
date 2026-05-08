import json
import ssl
import httpx
import anthropic
from config import ANTHROPIC_KEY, CLAUDE_MODEL

# Windows-Zertifikatsspeicher nutzen (Corporate-Proxy / SSL-Inspektion)
try:
    import truststore
    _ssl_ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    _http_client = httpx.Client(verify=_ssl_ctx)
except Exception:
    _http_client = httpx.Client(verify=False)

_client = anthropic.Anthropic(api_key=ANTHROPIC_KEY, http_client=_http_client)

PROMPT_TEMPLATE = """
Du bist ein Senior B2B-Vertriebsstratege für DreierFashion4You (Textillogistik-Dienstleister CH).
Analysiere die Rohdaten zur Firma **{company}** und erstelle ein strukturiertes Vertriebsbriefing.

════════════════════════════════════════════════════════════════
⚠️  HALLUZINIERUNGSVERBOT – ABSOLUT BINDEND:
- Schreibe NUR Fakten, die in den Rohdaten explizit belegt sind.
- Verwende NIE Superlative wie "Marktführer", "grösste", "führende" – ausser sie stehen wörtlich in den Quellen.
- Wenn eine Info fehlt, schreibe "Nicht bekannt" – NIEMALS erfinden.
- Jeder Pain Point muss aus einer konkreten Quelle stammen (News, Stelleninserat, Perplexity).
════════════════════════════════════════════════════════════════

=== STAMMDATEN (ZEFIX Handelsregister) ===
{zefix}

=== UNTERNEHMENS-OVERVIEW (Perplexity) ===
{perplexity}

=== AKTUELLE NEWS ({news_count} Artikel, max. 60 Tage) ===
{news}

=== BAU & EXPANSION ({construction_count} Treffer) ===
{construction}

=== OFFENE STELLEN ({jobs_count} Stellen, nur SC/Logistik/Führung) ===
{jobs}

=== VERBANDSMITGLIEDSCHAFT ===
{verband}

=== GESCRAPTE VOLLTEXTE (Top 3 Artikel) ===
{scraped}

════════════════════════════════════════════════════════════════
AUSGABE: Valides JSON-Objekt (kein Markdown-Block), exakt dieses Schema:

{{
  "company": "{company}",
  "sitz": "Ort, Kanton – aus ZEFIX oder Perplexity, sonst Nicht bekannt",
  "branche": "Hauptbranche – 1 Zeile",
  "rechtsform": "AG / GmbH / etc. aus ZEFIX",
  "uid": "CHE-XXX.XXX.XXX aus ZEFIX",
  "mitarbeiter": "Zahl oder Schätzung aus Perplexity, sonst Nicht bekannt",
  "umsatz": "Umsatz aus Perplexity, sonst Nicht bekannt",
  "summary": "2–3 Sätze: aktuelle Lage, Strategie, relevante Ereignisse – NUR aus Quellen",

  "pain_point_1": "Konkreter belegter Pain Point ≤15 Wörter (Quelle in Klammern)",
  "pain_point_2": "Konkreter belegter Pain Point ≤15 Wörter (Quelle in Klammern)",
  "pain_point_3": "Konkreter belegter Pain Point ≤15 Wörter – falls kein 3. belegter: Nicht bekannt",
  "pain_sources": ["Quelle 1", "Quelle 2", "Quelle 3"],

  "investitionssignale": ["Signal aus News/Bau/Jobs – belegt", "..."],

  "miller_heiman": {{
    "buying_influences": {{
      "economic_buyer": "Wer entscheidet Budget? (CEO/CFO/COO) – aus ZEFIX/News oder Nicht bekannt",
      "user_buyer": "Wer nutzt Textillogistik täglich? (Logistikleiter, Einkauf) – oder Nicht bekannt",
      "technical_buyer": "Wer evaluiert technisch? (IT, Procurement) – oder Nicht bekannt",
      "coach": "Interner Fürsprecher-Profil (welche Rolle profitiert von Dreier?) – oder Nicht bekannt"
    }},
    "current_situation": "IST-Zustand Logistik/Supply Chain der Firma – aus Quellen",
    "desired_outcome": "WAS will die Firma erreichen? (Expansion, Kostenreduktion, etc.) – aus Quellen",
    "solution_fit": "Wie passt DreierFashion4You konkret? (max. 3 Punkte)",
    "red_flags": ["Risiken / Einwände die der Vertrieb kennen muss"],
    "recommended_entry": "Empfohlener Gesprächseinstieg basierend auf stärkstem Pain Point",
    "talking_points": [
      "Gesprächspunkt 1 – direkt auf einen Pain Point gemünzt",
      "Gesprächspunkt 2",
      "Gesprächspunkt 3"
    ]
  }},

  "verband": "Verbandsstatus",
  "totalCount": 0,
  "news": [{{"title":"...","link":"...","date":"...","snippet":"..."}}],
  "construction": [{{"title":"...","link":"...","snippet":"..."}}],
  "jobs": [{{"title":"...","link":"...","snippet":"..."}}]
}}

REGELN:
1. pain_point_1/2/3: Nur Fakten aus Rohdaten. Quelle in Klammern angeben.
2. miller_heiman: Alle Felder ausfüllen – bei fehlender Info "Nicht bekannt".
3. totalCount = Anzahl Items in news + construction + jobs.
4. Antworte AUSSCHLIESSLICH mit dem JSON-Objekt. Kein Text davor oder danach.
"""


def analyse(company_name: str, zefix: dict, perplexity: dict,
            serp: dict, scraped: list) -> dict:
    prompt = PROMPT_TEMPLATE.format(
        company=company_name,
        zefix=json.dumps(zefix, ensure_ascii=False, indent=2),
        perplexity=json.dumps(perplexity, ensure_ascii=False, indent=2),
        news_count=len(serp.get("news", [])),
        news=json.dumps(serp.get("news", [])[:8], ensure_ascii=False, indent=2),
        construction_count=len(serp.get("construction", [])),
        construction=json.dumps(serp.get("construction", [])[:6], ensure_ascii=False, indent=2),
        jobs_count=len(serp.get("jobs", [])),
        jobs=json.dumps(serp.get("jobs", [])[:10], ensure_ascii=False, indent=2),
        verband=f"{serp.get('verband_status','')}\nLinks: {', '.join(serp.get('verband_links',[]))}",
        scraped=json.dumps(scraped, ensure_ascii=False, indent=2),
    )

    message = _client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = message.content[0].text.strip()
    import re
    raw = re.sub(r"```json\n?|```", "", raw).strip()

    # Robuster JSON-Parser
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        last_comma = max(raw.rfind(",\n"), raw.rfind(", "))
        if last_comma > 0:
            raw = raw[:last_comma] + "\n}"
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            brace_count = 0
            for i, ch in enumerate(raw):
                if ch == '{':
                    brace_count += 1
                elif ch == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        return json.loads(raw[:i+1])
            raise
