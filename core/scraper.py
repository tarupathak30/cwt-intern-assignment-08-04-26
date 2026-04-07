"""
APIFY scraper using the official apify-client SDK.
Actor: apify/google-search-scraper (free tier: $5 credit = 1000+ searches)
Falls back to DuckDuckGo+requests if APIFY_API_TOKEN is not set.
"""
import os
import logging
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

APIFY_TOKEN = os.getenv("APIFY_API_TOKEN", "")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


# ── APIFY path ────────────────────────────────────────────────────────────────

def _apify_search(query: str, max_results: int = 4) -> list[str]:
    """Use apify-client SDK to run google-search-scraper and return URLs."""
    try:
        from apify_client import ApifyClient
        client = ApifyClient(APIFY_TOKEN)

        run_input = {
            "queries": query,
            "resultsPerPage": max_results,
            "maxPagesPerQuery": 1,
            "languageCode": "en",
            "countryCode": "us",
            "mobileResults": False,
        }

        logger.info(f"  Running APIFY google-search-scraper for: {query}")
        run = client.actor("apify/google-search-scraper").call(run_input=run_input)
        dataset_id = run.get("defaultDatasetId")

        urls = []
        for item in client.dataset(dataset_id).iterate_items():
            for result in item.get("organicResults", []):
                url = result.get("url") or result.get("link")
                if url and url.startswith("http"):
                    urls.append(url)
                if len(urls) >= max_results:
                    break
            if len(urls) >= max_results:
                break

        logger.info(f"  APIFY returned {len(urls)} URLs")
        return urls

    except Exception as e:
        logger.error(f"APIFY search error: {e}")
        return []


# ── DuckDuckGo fallback ───────────────────────────────────────────────────────

def _ddg_search(query: str, max_results: int = 4) -> list[str]:
    """Fallback: DuckDuckGo HTML search."""
    try:
        resp = requests.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            headers=HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        urls = []
        for a in soup.select("a.result__url"):
            href = a.get("href", "")
            if href.startswith("http") and "duckduckgo" not in href:
                urls.append(href)
            if len(urls) >= max_results:
                break
        if not urls:
            for a in soup.select("a.result__a"):
                href = a.get("href", "")
                if href.startswith("http") and "duckduckgo" not in href:
                    urls.append(href)
                if len(urls) >= max_results:
                    break
        logger.info(f"  DDG found {len(urls)} URLs")
        return urls
    except Exception as e:
        logger.error(f"DDG fallback error: {e}")
        return []


# ── Page fetcher ──────────────────────────────────────────────────────────────

def _fetch_page(url: str, max_chars: int = 3000) -> dict:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = " ".join(soup.get_text(separator=" ", strip=True).split())[:max_chars]
        return {"url": url, "text": text}
    except Exception as e:
        logger.warning(f"  Could not fetch {url}: {e}")
        return {"url": url, "text": ""}


def scrape_urls(urls: list[str], max_items: int = 4) -> list[dict]:
    return [p for p in (_fetch_page(u) for u in urls[:max_items]) if p["text"]]


def search_and_scrape(query: str, max_results: int = 4) -> list[dict]:
    """
    Search (APIFY if token set, else DuckDuckGo) then scrape top pages.
    Returns list of {url, text} dicts.
    """
    if APIFY_TOKEN:
        urls = _apify_search(query, max_results=max_results)
        if not urls:
            logger.warning("APIFY returned no URLs, falling back to DDG")
            urls = _ddg_search(query, max_results=max_results)
    else:
        logger.info("No APIFY token — using DuckDuckGo fallback")
        urls = _ddg_search(query, max_results=max_results)

    if not urls:
        return [{"url": "none", "text": f"No search results found for: {query}"}]

    return scrape_urls(urls, max_items=max_results)