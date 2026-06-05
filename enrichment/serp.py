from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
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


def search_all(company_name: str, domain: str | None = None) -> dict:
    """Run all 5 SerpAPI searches in parallel and return combined results."""

    queries = {
        "news_general": {
            "engine": "google_news",
            "q": f'"{company_name}" (Nachricht OR News OR Investition OR Übernahme OR Kooperation OR Strategie OR Eröffnung OR Schließung OR Management) after:{_date_ago(60)}',
            "tbm": "nws",
            "num": "15",
            "tbs": "qdr:m2",
            "sort_by": "date",
        },
        "news_fashion": {
            "engine": "google_news",
            "q": f'"{company_name}" (Textil OR Mode OR Fashion OR Bekleidung OR Nachhaltigkeit OR Kollektion) (site:textilwirtschaft.de OR site:swisstextiles.ch OR site:fashionunited.de OR site:fashionnetwork.com) after:{_date_ago(180)}',
            "tbm": "nws",
            "num": "15",
            "tbs": "qdr:m6",
            "sort_by": "date",
        },
        "construction": {
            "engine": "google",
            "q": f'"{company_name}" (Neubau OR Standort OR Produktion OR Lager OR Bauvorhaben OR Eröffnung)',
            "tbm": "nws",
            "tbs": "qdr:m5",
            "num": "10",
        },
        "jobs": {
            "engine": "google",
            "q": f'(site:jobs.ch OR site:jobup.ch{(" OR site:" + domain) if domain else ""}) "{company_name}" (Logistik OR "Supply Chain" OR Operations OR CEO OR CFO OR COO OR CIO)',
            "tbs": "qdr:m3",
            "num": "10",
        },
        "associations": {
            "engine": "google",
            "q": f'"{company_name}" (Mitglied OR Membership OR Partner) AND (HANDELSVERBAND.swiss OR swisstextiles.ch OR swissfairtrade.ch OR swissmode.org OR procure.ch OR gs1.ch)',
            "tbm": "nws",
            "tbs": "qdr:m6",
            "num": "10",
        },
    }

    results = {}
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {pool.submit(_get, params): key for key, params in queries.items()}
        for future in as_completed(futures):
            key = futures[future]
            results[key] = future.result()

    news = _extract(results.get("news_general", {}), "news_results")
    news += _extract(results.get("news_fashion", {}), "news_results")
    construction = _extract(results.get("construction", {}), "news_results")
    jobs = _extract(results.get("jobs", {}), "organic_results")
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
