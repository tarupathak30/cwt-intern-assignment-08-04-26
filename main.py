#!/usr/bin/env python3
"""
CrowdWisdomTrading — Predictions Market Agent System
Main orchestrator: runs all agents in sequence and starts the chat interface.

Usage:
    python main.py               # Full pipeline + interactive chat
    python main.py --chat-only   # Skip data fetching, go straight to chat
    python main.py --enrich "2024 US Election"   # Just enrich one event
    python main.py --demo        # Run demo with sample output
"""
import io
import os
import sys
import logging
import argparse
from dotenv import load_dotenv

load_dotenv()

# Set up logging
os.makedirs("logs", exist_ok=True)
import io
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")),
        logging.FileHandler("logs/cwt.log", encoding="utf-8"),
    ]
)
logger = logging.getLogger("cwt.main")

from core.storage import init_db
from agents import run_polymarket, run_kalshi, run_niche, enrich, run_interactive, ChatAgent


def run_full_pipeline():
    """Execute all agents in order."""
    from rich.console import Console
    from rich.progress import track
    from rich.table import Table

    console = Console()

    console.rule("[bold cyan]CrowdWisdomTrading Agent Pipeline[/bold cyan]")

    # Init DB
    init_db()

    # Agent 1: Polymarket
    console.print("\n[bold]Agent 1[/bold] — Polymarket Trader Search")
    poly_traders = run_polymarket(top_n=10)
    console.print(f"  ✅ Found [green]{len(poly_traders)}[/green] Polymarket traders")

    # Agent 2: Kalshi
    console.print("\n[bold]Agent 2[/bold] — Kalshi Trader Search")
    kalshi_traders = run_kalshi(top_n=10)
    console.print(f"  ✅ Found [green]{len(kalshi_traders)}[/green] Kalshi traders")

    # Agent 3: Niche Mapping
    console.print("\n[bold]Agent 3[/bold] — Niche Mapping")
    all_traders = run_niche()
    console.print(f"  ✅ Classified [green]{len(all_traders)}[/green] traders into niches")

    # Agent 4: RAG Enrichment (sample events)
    console.print("\n[bold]Agent 4[/bold] — RAG Event Enrichment")
    sample_events = [
        "US Presidential Election 2024 prediction market odds",
        "NBA Finals 2024 Polymarket markets",
    ]
    for event in sample_events:
        console.print(f"  🔍 Enriching: {event}")
        enrich(event)
    console.print(f"  ✅ {len(sample_events)} events cached in RAG")

    # Print summary table — re-fetch from DB so niches are populated
    from core.storage import get_traders as _get_traders
    console.rule("[bold]Trader Summary[/bold]")
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Platform", style="cyan")
    table.add_column("Username")
    table.add_column("Win Rate", justify="right")
    table.add_column("P&L (USD)", justify="right")
    table.add_column("Niches")

    import json as _json
    all_from_db = sorted(_get_traders(), key=lambda x: x.get("win_rate") or 0, reverse=True)
    for t in all_from_db[:15]:
        raw_niches = t.get("niches", "[]")
        if isinstance(raw_niches, str):
            try:
                raw_niches = _json.loads(raw_niches)
            except Exception:
                raw_niches = []
        niches_str = ", ".join(raw_niches[:2]) if raw_niches else "—"
        table.add_row(
            t.get("platform", ""),
            t.get("username") or "unknown",
            f"{t.get('win_rate') or 0:.0%}",
            f"${t.get('profit_loss') or 0:,.0f}",
            niches_str,
        )
    console.print(table)
    console.print()


def run_demo():
    """Show sample input/output without needing API keys."""
    from rich.console import Console
    from rich.panel import Panel

    console = Console()
    init_db()

    console.rule("[bold yellow]CWT Demo Mode[/bold yellow]")
    console.print("[dim]Running with mock data (no API keys required)[/dim]\n")

    # Run pipeline with mock data
    run_full_pipeline()

    # Demo chat session
    console.print("\n[bold]Agent 5[/bold] — Chat Demo")
    agent = ChatAgent(session_id="demo")

    demo_queries = [
        "Which trader should I copy for NBA predictions?",
        "Who is the most consistent political trader across both platforms?",
        "What is the win rate of the top Kalshi trader?",
    ]

    for q in demo_queries:
        console.print(f"\n[bold green]User:[/bold green] {q}")
        response = agent.chat(q)
        console.print(Panel(response, title="🤖 CWT Agent", border_style="cyan", width=80))

    console.print("\n[bold green]✅ Demo complete![/bold green]")
    console.print("[dim]Set GROQ_API_KEY and APIFY_API_TOKEN in .env for live data[/dim]")


def main():
    parser = argparse.ArgumentParser(description="CrowdWisdomTrading Predictions Market Agent")
    parser.add_argument("--chat-only", action="store_true", help="Skip pipeline, go to chat")
    parser.add_argument("--enrich", type=str, help="Enrich a specific event query")
    parser.add_argument("--demo", action="store_true", help="Run demo with sample output")
    args = parser.parse_args()

    init_db()

    if args.demo:
        run_demo()
    elif args.enrich:
        result = enrich(args.enrich)
        print(f"\n{'='*60}")
        print(f"Query: {result['query']}")
        print(f"Cached: {result['cached']}")
        print(f"\nSummary:\n{result['summary']}")
        print(f"\nSources: {result['sources']}")
    elif args.chat_only:
        run_interactive()
    else:
        run_full_pipeline()
        print("\nStarting chat interface...")
        run_interactive()


if __name__ == "__main__":
    main()