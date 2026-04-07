"""
Agent 5 — Chat Interface + Learning Loop
Lets users discuss which trader to copy, enriched by RAG data.
The learning loop tracks recommendations and updates trader scores over time.
"""
import uuid
import logging
import json
from core import chat, get_traders, get_history, save_message, get_learning_stats, log_recommendation, resolve_recommendation
from agents.research_agent import enrich, search_existing

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are CWT — CrowdWisdomTrading's AI analyst assistant.
You help users decide which predictions market trader to copy-trade.

You have access to:
1. A database of top traders on Polymarket and Kalshi with win rates, P&L, and niches
2. RAG research about specific prediction market events
3. A learning loop tracking which of your past recommendations won or lost

Your job:
- Help users find the best trader to copy for a given niche/event
- Explain WHY a trader is good or risky
- Reference research when relevant
- Be honest about uncertainty
- Keep responses concise and actionable

When recommending a trader, always mention:
- Platform (Polymarket / Kalshi)
- Win rate and P&L
- Their niche specialty
- Any relevant recent events from the RAG cache
"""


class ChatAgent:
    def __init__(self, session_id: str = None):
        self.session_id = session_id or str(uuid.uuid4())[:8]
        logger.info(f"Chat session started: {self.session_id}")

    def _build_context(self, user_msg: str) -> str:
        """Fetch relevant traders and RAG snippets to inject as context."""
        traders = get_traders(min_win_rate=0.55)
        trader_summary = json.dumps([{
            "platform": t["platform"],
            "username": t.get("username"),
            "win_rate": t.get("win_rate"),
            "profit_loss": t.get("profit_loss"),
            "niches": t.get("niches"),
        } for t in traders[:15]], indent=2)

        # Search RAG cache for relevant event data
        rag_hits = search_existing(user_msg)
        rag_text = ""
        if rag_hits:
            rag_text = "\n\nRelevant research from RAG cache:\n" + "\n---\n".join(
                f"[{r['query']}]: {r['summary']}" for r in rag_hits[:2]
            )

        # Learning loop stats
        stats = get_learning_stats()
        learning_text = f"\n\nLearning loop stats: {stats}" if stats.get("total_resolved") else ""

        return f"""Current trader database:
{trader_summary}
{rag_text}
{learning_text}"""

    def chat(self, user_input: str) -> str:
        """Process one user message and return agent response."""
        # Save user message
        save_message(self.session_id, "user", user_input)

        # Build context
        context = self._build_context(user_input)

        # Get conversation history (last 10 turns)
        history = get_history(self.session_id, limit=10)
        # Remove the message we just saved (it's the last one) to avoid duplication
        history = history[:-1] if history else []

        messages = history + [{
            "role": "user",
            "content": f"{user_input}\n\n[Context for your reference — do NOT repeat this verbatim to the user]:\n{context}"
        }]

        response = chat(messages, system=SYSTEM_PROMPT, temperature=0.4)

        # Save assistant response
        save_message(self.session_id, "assistant", response)
        return response

    def enrich_event(self, event_query: str) -> str:
        """Trigger RAG enrichment for a specific event and return summary."""
        result = enrich(event_query)
        return f"✅ Research complete{'(cached)' if result['cached'] else ''}:\n\n{result['summary']}"

    def record_outcome(self, event_id: str, outcome: str, pnl: float):
        """Feed actual trade outcome back into the learning loop."""
        resolve_recommendation(event_id, outcome, pnl)
        stats = get_learning_stats()
        return f"✅ Outcome recorded. Updated stats: {stats}"


def run_interactive():
    """Run an interactive CLI chat session."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Prompt

    console = Console()
    agent = ChatAgent()

    console.print(Panel.fit(
        "[bold cyan]CrowdWisdomTrading Agent[/bold cyan]\n"
        "Ask me which trader to copy, or type [bold]'enrich: <event>'[/bold] to research a topic.\n"
        "Type [bold]'quit'[/bold] to exit.",
        title="🎯 CWT Chat"
    ))

    while True:
        try:
            user_input = Prompt.ask("\n[bold green]You[/bold green]")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Goodbye![/dim]")
            break

        if user_input.lower() in ("quit", "exit", "q"):
            console.print("[dim]Session ended.[/dim]")
            break

        if user_input.lower().startswith("enrich:"):
            event = user_input[7:].strip()
            console.print("[dim]🔍 Scraping web research...[/dim]")
            result = agent.enrich_event(event)
            console.print(Panel(result, title="📚 RAG Research", border_style="blue"))
            continue

        console.print("[dim]⏳ Thinking...[/dim]")
        response = agent.chat(user_input)
        console.print(Panel(response, title="🤖 CWT Agent", border_style="cyan"))


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    from dotenv import load_dotenv; load_dotenv()
    from core.storage import init_db; init_db()
    run_interactive()