# CrowdWisdomTrading — Predictions Market Agent System

A multi-agent Python backend for researching and copy-trading on **Polymarket** and **Kalshi** using **Groq (free LLM)** and **APIFY** for web scraping.

---

## Architecture

```
main.py (orchestrator)
│
├── Agent 1: polymarket_agent.py   → Finds top wallets on Polymarket
├── Agent 2: kalshi_agent.py       → Finds top wallets on Kalshi
├── Agent 3: niche_agent.py        → Maps traders to NBA/Politics/Weather etc.
├── Agent 4: research_agent.py     → APIFY scraping → RAG enrichment cache
└── Agent 5: chat_agent.py         → Interactive chat + learning loop

core/
├── llm.py      → Groq client (llama3-70b, mixtral — all free)
├── storage.py  → SQLite: traders, RAG cache, learning loop, chat history
└── scraper.py  → APIFY wrapper (web-scraper + google-search-scraper actors)
```

---

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure API keys
```bash
cp .env.example .env
# Edit .env and fill in:
# GROQ_API_KEY=   → https://console.groq.com (free)
# APIFY_API_TOKEN= → https://console.apify.com (free tier)
```

### 3. Run

```bash
# Full pipeline + interactive chat
python main.py

# Demo mode (no API keys needed, uses mock data)
python main.py --demo

# Skip pipeline, go straight to chat
python main.py --chat-only

# Just enrich one specific event
python main.py --enrich "NBA Finals 2024 Polymarket odds"
```

---

## Agent Flow

```
1. Polymarket Agent
   └─ Fetches leaderboard → LLM enrichment → SQLite

2. Kalshi Agent
   └─ Fetches markets / trader data → LLM enrichment → SQLite

3. Niche Mapping Agent
   └─ Reads all traders → LLM classifies niches → Updates DB
      Niches: Politics, NBA, NFL, Crypto, Weather, Finance...

4. Research Agent (APIFY RAG)
   └─ Query → APIFY Google Search → Scrape pages → LLM summary → Cache

5. Chat Agent
   └─ User asks question
      → Injects: top traders + RAG snippets + learning loop stats
      → Groq LLM answers
      → History saved to DB
      → Recommendations tracked in learning loop
```

---

## Learning Loop

Every time the agent recommends copying a trader on an event, it logs:
- `trader_id`, `event_id`, `recommendation` (copy/skip)

When the event resolves, call:
```python
from core.storage import resolve_recommendation
resolve_recommendation("event_id", outcome="win", pnl=+350.0)
```

The chat agent reads these stats and improves recommendations over time.

---

## Chat Commands

Inside the interactive chat:

| Input | Action |
|-------|--------|
| `"Which NBA trader should I copy?"` | Get trader recommendations |
| `"enrich: NBA Finals 2024 odds"` | Trigger APIFY research |
| `"Who has the best win rate on Kalshi?"` | Query trader DB |
| `quit` | Exit |

---

## Sample Output

```
Agent 1 — Polymarket Trader Search
  ✅ Found 10 Polymarket traders

Agent 2 — Kalshi Trader Search
  ✅ Found 10 Kalshi traders

Agent 3 — Niche Mapping
  ElectionOracle → ['Politics', 'Elections']
  SportsSage → ['NBA', 'Sports (General)']
  WeatherBet → ['Weather', 'Climate']
  ✅ Classified 20 traders

Agent 4 — RAG Enrichment
  🔍 Enriching: US Presidential Election 2024...
  ✅ 2 events cached

┌─────────────┬──────────────────┬──────────┬────────────┬─────────────────────┐
│ Platform    │ Username         │ Win Rate │ P&L (USD)  │ Niches              │
├─────────────┼──────────────────┼──────────┼────────────┼─────────────────────┤
│ polymarket  │ TechProphet      │ 73%      │ $18,000    │ Technology, AI      │
│ kalshi      │ WeatherBet       │ 70%      │ $15,000    │ Weather, Climate    │
│ polymarket  │ ElectionOracle   │ 71%      │ $45,000    │ Politics, Elections │
└─────────────┴──────────────────┴──────────┴────────────┴─────────────────────┘

You: Which trader should I copy for the upcoming election?

🤖 CWT Agent:
Based on the current data, I recommend copying ElectionOracle on Polymarket.

Here's why:
- Win Rate: 71% (one of the highest on the platform)
- P&L: $45,000 total profit — proven consistency
- Niche: Politics & Elections — exactly what you're targeting

From the RAG research cache, the current election markets on Polymarket are heavily
traded with strong liquidity. ElectionOracle has been active in this space.

Risk note: Political markets can swing fast around news events. Copy-trade with
position sizing of 5–10% of your bankroll per trade.
```

---

## Tech Stack

| Component | Choice | Why |
|-----------|--------|-----|
| LLM | Groq (llama3-70b) | Free, fast, 70B quality |
| Scraping | APIFY | Free tier, reliable actors |
| DB | SQLite | Zero-setup, runs on your laptop |
| APIs | Polymarket Gamma API, Kalshi v2 | Public, no auth needed |
| UI | Rich (terminal) | Clean CLI, no web server needed |

---

## File Structure

```
cwt_agent/
├── main.py                  # Orchestrator
├── requirements.txt
├── .env.example
├── agents/
│   ├── polymarket_agent.py  # Agent 1
│   ├── kalshi_agent.py      # Agent 2
│   ├── niche_agent.py       # Agent 3
│   ├── research_agent.py    # Agent 4 (RAG + APIFY)
│   └── chat_agent.py        # Agent 5 (Chat + Learning Loop)
├── core/
│   ├── llm.py               # Groq client
│   ├── storage.py           # SQLite helpers
│   └── scraper.py           # APIFY wrapper
├── data/
│   └── cwt.db               # Auto-created SQLite DB
└── logs/
    └── cwt.log              # Auto-created log file
```