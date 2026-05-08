from enrichment import ssl_session as requests
from config import FIRECRAWL_KEY, FIRECRAWL_BASE


def scrape_articles(news_items: list, max_articles: int = 3) -> list[dict]:
    """Scrape up to max_articles news articles and return their markdown content."""
    scraped = []
    candidates = [
        item for item in news_items
        if item.get("link", "").startswith("https://")
    ][:max_articles]

    for item in candidates:
        url = item["link"]
        try:
            resp = requests.post(
                f"{FIRECRAWL_BASE}/scrape",
                json={"url": url, "formats": ["markdown"], "timeout": 30000},
                headers={
                    "Authorization": f"Bearer {FIRECRAWL_KEY}",
                    "Content-Type": "application/json",
                },
                timeout=40,
            )
            resp.raise_for_status()
            data = resp.json()
            markdown = data.get("data", {}).get("markdown", "")
            if markdown:
                scraped.append({
                    "url": url,
                    "title": item.get("title", ""),
                    "markdown": markdown[:3000],
                })
        except Exception:
            pass

    return scraped
