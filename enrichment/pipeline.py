from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from enrichment import parser, zefix, serp, firecrawl, perplexity, claude, branches_store


def run(raw_input: str, progress_callback=None) -> dict:
    """
    Full enrichment pipeline for one company.
    progress_callback(step: str, pct: int) is called at each stage if provided.
    Returns the structured result dict from Claude plus raw metadata.
    """

    def notify(step: str, pct: int):
        if progress_callback:
            progress_callback(step, pct)

    notify("Firmenname parsen …", 5)
    company_info = parser.parse_company_input(raw_input)
    name = company_info["companyName"]
    domain = company_info.get("domain")

    notify("ZEFIX & Perplexity abrufen …", 15)
    with ThreadPoolExecutor(max_workers=2) as pool:
        f_zefix = pool.submit(zefix.lookup, name)
        f_perp = pool.submit(perplexity.get_company_overview, name)
        zefix_data = f_zefix.result()
        perp_data = f_perp.result()

    notify("Google-Suchen laufen (5 parallel) …", 35)
    serp_data = serp.search_all(name, domain)

    notify("Artikel scrapen (Firecrawl) …", 55)
    all_news = serp_data.get("news", []) + serp_data.get("construction", [])
    scraped = firecrawl.scrape_articles(all_news, max_articles=3)

    notify("Claude analysiert Daten …", 75)
    matrix = branches_store.load_matrix()
    matrix_block = branches_store.matrix_to_prompt_block(matrix)
    result = claude.analyse(name, zefix_data, perp_data, serp_data, scraped, matrix_block)

    notify("Fertig.", 100)
    result["_meta"] = {
        "input": raw_input,
        "companyName": name,
        "domain": domain,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "zefix_gefunden": zefix_data.get("zefix_gefunden", False),
    }
    return result


def run_batch(company_list: list[str], progress_callback=None) -> list[dict]:
    """
    Run pipeline for multiple companies sequentially
    (parallel would exceed API rate limits).
    progress_callback(company, step, pct, idx, total)
    """
    results = []
    total = len(company_list)
    for idx, raw in enumerate(company_list):
        def _cb(step, pct, _idx=idx, _raw=raw):
            if progress_callback:
                progress_callback(_raw, step, pct, _idx, total)

        try:
            res = run(raw, progress_callback=_cb)
        except Exception as exc:
            res = {
                "company": raw,
                "summary": f"Fehler: {exc}",
                "pain_point_1": "", "pain_point_2": "", "pain_point_3": "",
                "_error": str(exc),
                "_meta": {"input": raw, "companyName": raw},
            }
        results.append(res)
    return results
