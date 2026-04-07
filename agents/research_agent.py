"""
Agent 4 — RAG Event Enrichment
Uses APIFY to scrape web content about a specific prediction market event,
then summarises it with LLM and stores in the RAG cache.
"""
import logging
from core import chat, search_and_scrape, save_rag, get_rag, search_rag

logger = logging.getLogger(__name__)


def _summarise_content(event_query: str, scraped: list[dict]) -> str:
    """Condense multiple scraped pages into a single RAG document."""
    combined_text = "\n\n---\n\n".join(
        f"Source: {item.get('url', 'unknown')}\n{item.get('text', '')[:2000]}"
        for item in scraped
        if item.get("text")
    )
    if not combined_text.strip():
        return "No content available for this event."

    system = """You are a research assistant for a predictions market platform.
Summarise the provided web content into a concise, fact-dense briefing
that helps a trader understand the current state of a prediction market event.
Include key facts, dates, probabilities if mentioned, and recent developments.
Aim for 300-500 words."""

    prompt = f"""Event / query: "{event_query}"

Scraped content:
{combined_text[:6000]}

Write the research briefing:"""

    return chat([{"role": "user", "content": prompt}], system=system)


def enrich(event_query: str, force_refresh: bool = False) -> dict:
    """
    Main entry: search & scrape the web about an event, summarise, cache.
    Returns {query, summary, sources, cached}
    """
    # Check cache first
    if not force_refresh:
        cached = get_rag(event_query)
        if cached:
            logger.info(f"📦 RAG cache hit: '{event_query}'")
            return {
                "query": event_query,
                "summary": cached["content"],
                "sources": cached.get("source_urls", []),
                "cached": True,
            }

    logger.info(f"🌐 Scraping web for: '{event_query}'...")
    scraped = search_and_scrape(event_query, max_results=4)
    sources = [item.get("url", "") for item in scraped]

    logger.info(f"  Got {len(scraped)} pages. Summarising with LLM...")
    summary = _summarise_content(event_query, scraped)

    # Store in RAG cache
    save_rag(event_query, summary, sources)
    logger.info(f"✅ RAG enrichment done for: '{event_query}'")

    return {
        "query": event_query,
        "summary": summary,
        "sources": sources,
        "cached": False,
    }


def search_existing(keywords: str) -> list[dict]:
    """Search the local RAG cache without hitting the web."""
    results = search_rag(keywords)
    return [{"query": r["query"], "summary": r["content"][:400] + "..."} for r in results]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from dotenv import load_dotenv; load_dotenv()
    from core.storage import init_db; init_db()
    result = enrich("2024 US Presidential Election prediction market odds")
    print(f"\nQuery: {result['query']}")
    print(f"Cached: {result['cached']}")
    print(f"\nSummary:\n{result['summary']}")
    print(f"\nSources: {result['sources']}")