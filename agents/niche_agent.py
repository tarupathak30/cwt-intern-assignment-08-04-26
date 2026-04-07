"""
Agent 3 — Niche Mapper
Uses LLM to classify each trader into prediction market niches
(Politics, NBA, NFL, Weather, Crypto, Finance, Entertainment, etc.)
based on their trade history and notes.
"""
import json
import logging
from core import chat_json, get_traders, upsert_trader

logger = logging.getLogger(__name__)

KNOWN_NICHES = [
    "Politics", "Elections", "US Congress", "International Politics",
    "NBA", "NFL", "MLB", "Soccer", "Sports (General)",
    "Crypto", "Bitcoin", "Ethereum", "DeFi",
    "Finance", "Fed / Interest Rates", "Stocks", "Commodities",
    "Weather", "Climate",
    "Technology", "AI", "Big Tech",
    "Entertainment", "Movies", "TV", "Awards",
    "Science", "Space",
    "Health", "Pharmaceuticals",
]


def _classify_trader(trader: dict) -> list[str]:
    """Ask LLM to assign niches to one trader based on their raw_data + notes."""
    raw = trader.get("raw_data", "{}")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            raw = {}

    prompt = f"""
Given this predictions market trader profile, assign the top 1–3 niches they specialize in.

Trader info:
- Username: {trader.get('username')}
- Platform: {trader.get('platform')}
- Notes: {raw.get('notes', trader.get('notes', 'N/A'))}
- Categories from raw data: {raw.get('categories', raw.get('niches', []))}

Available niches: {KNOWN_NICHES}

Return JSON: {{"niches": ["Niche1", "Niche2"]}}
Only pick from the available niches list. Max 3.
"""
    result = chat_json(
        [{"role": "user", "content": prompt}],
        system="You are a market categorization expert. Return only JSON."
    )
    return result.get("niches", [])


def run(platform: str = None) -> list[dict]:
    """
    Load all traders from DB, classify each into niches, update DB.
    Returns list of traders with niches filled.
    """
    logger.info(f"🗂️  Niche mapping{'for ' + platform if platform else ' (all platforms)'}...")

    traders = get_traders(platform=platform)
    if not traders:
        logger.warning("No traders in DB yet. Run polymarket/kalshi agents first.")
        return []

    updated = []
    for trader in traders:
        niches = _classify_trader(trader)
        logger.info(f"  {trader.get('username', trader.get('wallet_address'))} → {niches}")

        # Update in DB
        trader["niches"] = niches
        raw = trader.get("raw_data", "{}")
        if isinstance(raw, str):
            try:
                raw_dict = json.loads(raw)
            except Exception:
                raw_dict = {}
        else:
            raw_dict = raw
        raw_dict["niches"] = niches
        trader.update(raw_dict)
        upsert_trader(trader["platform"], trader["wallet_address"], trader)
        updated.append(trader)

    logger.info(f"✅ Niche mapping done. {len(updated)} traders classified.")
    return updated


def get_traders_by_niche(niche: str) -> list[dict]:
    """Helper: get all traders specialising in a given niche."""
    return get_traders(niche=niche)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from dotenv import load_dotenv; load_dotenv()
    from core.storage import init_db; init_db()
    traders = run()
    for t in traders:
        print(f"  [{t['platform']}] {t.get('username')} → {t.get('niches')}")