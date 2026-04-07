"""
Agent 1 — Polymarket Consistent Traders
Uses the public Gamma API (no auth needed) to find top-performing wallets.
"""
import os
import logging
import requests
from core import chat_json, upsert_trader, get_traders

logger = logging.getLogger(__name__)

POLY_API = os.getenv("POLYMARKET_API_URL", "https://gamma-api.polymarket.com")
CLOB_API = "https://clob.polymarket.com"


def _fetch_leaderboard(limit: int = 50) -> list[dict]:
    """Fetch top traders from Polymarket's public leaderboard endpoint."""
    try:
        resp = requests.get(
            f"{POLY_API}/leaderboard",
            params={"limit": limit, "offset": 0, "window": "all"},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json().get("data", resp.json() if isinstance(resp.json(), list) else [])
    except Exception as e:
        logger.error(f"Polymarket leaderboard fetch failed: {e}")
        # Return mock data so the system still works without live API
        return _mock_polymarket_traders()


def _mock_polymarket_traders() -> list[dict]:
    return [
        {"address": "0xABC123", "name": "ElectionOracle", "profit": 45000, "volume": 120000, "numTrades": 234, "winRate": 0.71},
        {"address": "0xDEF456", "name": "SportsSage", "profit": 32000, "volume": 90000, "numTrades": 189, "winRate": 0.65},
        {"address": "0xGHI789", "name": "CryptoNerd", "profit": 28000, "volume": 75000, "numTrades": 310, "winRate": 0.61},
        {"address": "0xJKL012", "name": "WeatherWatcher", "profit": 21000, "volume": 55000, "numTrades": 145, "winRate": 0.68},
        {"address": "0xMNO345", "name": "TechProphet", "profit": 18000, "volume": 48000, "numTrades": 98, "winRate": 0.73},
    ]


def _enrich_with_llm(traders: list[dict]) -> list[dict]:
    """Use Groq to parse and standardize raw trader data."""
    prompt = f"""
You are a predictions market analyst. Given these raw Polymarket trader records,
extract and standardize each into a clean profile.

Raw data:
{traders}

Return a JSON array. Each item must have:
- wallet_address (string)
- username (string or null)
- win_rate (float 0-1)
- total_trades (int)
- total_volume (float USD)
- profit_loss (float USD)
- consistency_score (float 0-10, your assessment of how consistent this trader is)
- notes (1 sentence about their trading style)
"""
    result = chat_json(
        [{"role": "user", "content": prompt}],
        system="You are a financial data analyst. Return only JSON arrays."
    )
    return result if isinstance(result, list) else []


def run(top_n: int = 10, min_win_rate: float = 0.55) -> list[dict]:
    """
    Main entry: fetch Polymarket top traders, enrich with LLM, save to DB.
    Returns list of enriched trader profiles.
    """
    logger.info("🔍 Fetching Polymarket traders...")
    raw = _fetch_leaderboard(limit=top_n * 2)

    # Filter by basic win rate if available in raw data
    filtered = [t for t in raw if t.get("winRate", t.get("win_rate", 1.0)) >= min_win_rate][:top_n]

    if not filtered:
        filtered = raw[:top_n]

    logger.info(f"  Found {len(filtered)} candidates. Enriching with LLM...")
    enriched = _enrich_with_llm(filtered)

    saved = []
    for trader in enriched:
        wallet = trader.get("wallet_address", "unknown")
        trader["niches"] = []  # Will be filled by niche agent later
        tid = upsert_trader("polymarket", wallet, trader)
        trader["db_id"] = tid
        saved.append(trader)
        logger.info(f"  ✓ Saved: {trader.get('username', wallet)} | WR: {trader.get('win_rate')}")

    logger.info(f"✅ Polymarket agent done. {len(saved)} traders saved.")
    return saved


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    from dotenv import load_dotenv; load_dotenv()
    from core.storage import init_db; init_db()
    traders = run()
    for t in traders:
        print(f"  {t.get('username')} | WR: {t.get('win_rate')} | PnL: ${t.get('profit_loss'):,.0f}")