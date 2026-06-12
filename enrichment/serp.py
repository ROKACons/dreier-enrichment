from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
import re
import unicodedata
from enrichment import ssl_session as requests
from config import SERPAPI_KEY, SERPAPI_BASE

_COMMON = {"api_key": SERPAPI_KEY, "gl": "ch", "hl": "de", "no_cache": "false"}


def _get(params: dict) -> dict:
    try:
        r = requests.get(SERPAPI_BASE, params={**_COMMON, **params}, timeout=20)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        return {"_error": str(exc)}


def _date_ago(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")


def _qdr(months: int) -> str:
    """Google qdr-Parameter aus Monaten ableiten (Cap auf 12)."""
    m = max(1, min(int(months), 12))
    return f"qdr:m{m}"


def _normalize(text: str) -> str:
    """Lowercase + Diakritika entfernen + DE-Transliteration kollabieren → Fuzzy-Match."""
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(c for c in nfkd if not unicodedata.combining(c)).lower()
    # Deutsche Doppel-Transliteration auf Single-Vokal kollabieren,
    # damit "Bächli"→"bachli" und "Baechli"→"bachli" denselben Token ergeben.
    for src, dst in (("ae", "a"), ("oe", "o"), ("ue", "u"), ("ss", "s")):
        ascii_text = ascii_text.replace(src, dst)
    return re.sub(r"[^a-z0-9]+", " ", ascii_text).strip()


def _company_tokens(name: str) -> list[str]:
    """Signifikante Tokens für Firmen-Match (AG/GmbH-Suffixe weg, kurze Tokens weg)."""
    norm = _normalize(name)
    stop = {"ag", "gmbh", "sa", "sarl", "co", "kg", "ltd", "llc", "inc", "the", "und", "and"}
    return [t for t in norm.split() if len(t) >= 3 and t not in stop]


def _hit_contains_company(hit: dict, tokens: list[str]) -> bool:
    """True wenn mind. 1 signifikanter Firmen-Token in title/snippet/link/source vorkommt."""
    if not tokens:
        return True
    haystack = _normalize(
        f"{hit.get('title','')} {hit.get('snippet','')} "
        f"{hit.get('link','')} {hit.get('source','')} {hit.get('displayed_link','')}"
    )
    return any(t in haystack for t in tokens)


def search_all(
    company_name: str,
    domain: str | None = None,
    max_age_months: int = 6,
    job_settings: dict | None = None,
) -> dict:
    """Run all SerpAPI searches in parallel and return combined results.

    Args:
        max_age_months: Zeitfilter für News/Bau/Verband (1–12).
        job_settings: dict mit Keys:
            - enabled (bool, default True)
            - keywords (list[str], default Logistik/SC/CXO-Liste)
            - max_age_months (int, default = max_age_months)
    """
    age_general = max(1, min(int(max_age_months), 12))
    js = job_settings or {}
    job_enabled = js.get("enabled", True)
    job_keywords = js.get("keywords") or [
        "Logistik", "Supply Chain", "Operations", "CEO", "CFO", "COO", "CIO"
    ]
    job_age = max(1, min(int(js.get("max_age_months", age_general)), 12))
    job_kw_clause = " OR ".join(f'"{k}"' for k in job_keywords)

    queries = {
        "news_general": {
            "engine": "google_news",
            "q": (
                f'"{company_name}" (Nachricht OR News OR Investition OR Übernahme OR Kooperation '
                f'OR Strategie OR Eröffnung OR Schließung OR Management) '
                f'after:{_date_ago(age_general * 30)}'
            ),
            "tbm": "nws",
            "num": "15",
            "tbs": _qdr(age_general),
            "sort_by": "date",
        },
        "news_fashion": {
            "engine": "google_news",
            "q": (
                f'"{company_name}" (Textil OR Mode OR Fashion OR Bekleidung OR Nachhaltigkeit OR Kollektion) '
                f'(site:textilwirtschaft.de OR site:swisstextiles.ch OR site:fashionunited.de '
                f'OR site:fashionnetwork.com) after:{_date_ago(age_general * 30)}'
            ),
            "tbm": "nws",
            "num": "15",
            "tbs": _qdr(age_general),
            "sort_by": "date",
        },
        "construction": {
            "engine": "google",
            "q": f'"{company_name}" (Neubau OR Standort OR Produktion OR Lager OR Bauvorhaben OR Eröffnung)',
            "tbm": "nws",
            "tbs": _qdr(age_general),
            "num": "10",
        },
        "associations": {
            "engine": "google",
            "q": (
                f'"{company_name}" (Mitglied OR Membership OR Partner) AND '
                f'(HANDELSVERBAND.swiss OR swisstextiles.ch OR swissfairtrade.ch OR '
                f'swissmode.org OR procure.ch OR gs1.ch)'
            ),
            "tbm": "nws",
            "tbs": _qdr(age_general),
            "num": "10",
        },
    }

    if job_enabled:
        queries["jobs"] = {
            "engine": "google",
            "q": (
                f'(site:jobs.ch OR site:jobup.ch OR site:ostjob.ch OR site:indeed.ch'
                f'{(" OR site:" + domain) if domain else ""}) '
                f'"{company_name}" ({job_kw_clause})'
            ),
            "tbs": _qdr(job_age),
            "num": "10",
        }

    results = {}
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {pool.submit(_get, params): key for key, params in queries.items()}
        for future in as_completed(futures):
            key = futures[future]
            results[key] = future.result()

    tokens = _company_tokens(company_name)

    news = _extract(results.get("news_general", {}), "news_results")
    news += _extract(results.get("news_fashion", {}), "news_results")
    construction = _extract(results.get("construction", {}), "news_results")
    # Auch News mit Firmenname-Match validieren (Sicherheit gegen falsche Treffer)
    news = [n for n in news if _hit_contains_company(n, tokens)]
    construction = [c for c in construction if _hit_contains_company(c, tokens)]

    jobs_raw = _extract(results.get("jobs", {}), "organic_results") if job_enabled else []
    # Job-Validation: Firmenname MUSS in title/snippet/link/source vorkommen
    jobs = [j for j in jobs_raw if _hit_contains_company(j, tokens)]

    assoc_raw = results.get("associations", {})
    try:
        total_assoc = int(assoc_raw.get("search_metadata", {}).get("total_results", 0) or 0)
    except (ValueError, TypeError):
        total_assoc = 0
    verband_status = (
        "Mögliche Mitgliedschaft gefunden" if total_assoc > 0
        else "Nicht eindeutig gefunden"
    )

    return {
        "news": _dedup(news),
        "construction": _dedup(construction),
        "jobs": _dedup(jobs),
        "verband_status": verband_status,
        "verband_links": [r.get("link", "") for r in assoc_raw.get("organic_results", [])[:3]],
        "_filter_info": {
            "max_age_months_general": age_general,
            "max_age_months_jobs": job_age,
            "job_enabled": job_enabled,
            "job_keywords": job_keywords,
            "jobs_dropped_by_name_filter": len(jobs_raw) - len(jobs),
        },
    }


def _extract(data: dict, key: str) -> list:
    return data.get(key, []) if isinstance(data.get(key), list) else []


def _dedup(items: list) -> list:
    seen = set()
    out = []
    for item in items:
        link = item.get("link", "")
        if link and link not in seen:
            seen.add(link)
            out.append(item)
    return out
