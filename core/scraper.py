"""
APIFY scraper for event enrichment.
Uses the free web scraper actor to pull content from relevant URLs.
"""
import os
import logging
import requests

logger = logging.getLogger(__name__)

APIFY_TOKEN = os.getenv("APIFY_API_TOKEN", "")
BASE_URL = "https://api.apify.com/v2"


def _run_actor(actor_id: str, run_input: dict) -> list[dict]:
    """Run an Apify actor synchronously and return dataset items."""
    url = f"{BASE_URL}/acts/{actor_id}/run-sync-get-dataset-items"
    params = {"token": APIFY_TOKEN}
    resp = requests.post(url, json=run_input, params=params, timeout=120)
    resp.raise_for_status()
    return resp.json()


def scrape_urls(urls: list[str], max_items: int = 5) -> list[dict]:
    """
    Use Apify's free web-scraper to fetch text content from a list of URLs.
    Returns list of {url, text} dicts.
    """
    if not APIFY_TOKEN:
        logger.warning("No APIFY_API_TOKEN set — returning mock data.")
        return [{"url": u, "text": f"[Mock content for {u} — set APIFY_API_TOKEN]"} for u in urls]

    try:
        items = _run_actor("apify/web-scraper", {
            "startUrls": [{"url": u} for u in urls[:max_items]],
            "pageFunction": """
                async function pageFunction(context) {
                    const { page, request } = context;
                    const title = await page.title();
                    const text = await page.evaluate(() => document.body.innerText.slice(0, 3000));
                    return { url: request.url, title, text };
                }
            """,
            "maxPagesPerCrawl": max_items,
            "maxCrawlingDepth": 0,
        })
        return items
    except Exception as e:
        logger.error(f"APIFY scrape error: {e}")
        return [{"url": u, "text": f"[Scrape failed: {e}]"} for u in urls]


def search_and_scrape(query: str, max_results: int = 3) -> list[dict]:
    """
    Use Apify's Google Search scraper to find + fetch pages about a topic.
    """
    if not APIFY_TOKEN:
        logger.warning("No APIFY_API_TOKEN — returning mock search results.")
        return [{
            "url": f"https://example.com/search?q={query.replace(' ', '+')}",
            "text": f"[Mock search result for '{query}' — set APIFY_API_TOKEN to enable real scraping]"
        }]
    try:
        # Use Apify's Google Search Results Scraper
        results = _run_actor("apify/google-search-scraper", {
            "queries": query,
            "maxPagesPerQuery": 1,
            "resultsPerPage": max_results,
            "mobileResults": False,
        })
        urls = [r.get("url") for r in results if r.get("url")][:max_results]
        if not urls:
            return []
        return scrape_urls(urls, max_items=max_results)
    except Exception as e:
        logger.error(f"APIFY search error: {e}")
        return [{"url": "error", "text": f"Search failed: {e}"}]