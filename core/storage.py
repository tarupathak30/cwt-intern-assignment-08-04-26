"""
SQLite storage for:
- Trader profiles (Polymarket + Kalshi)
- RAG event enrichment cache
- Learning loop: prediction outcomes for feedback
"""
import sqlite3
import json
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "cwt.db")


def get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create all tables if they don't exist."""
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS traders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL,          -- 'polymarket' or 'kalshi'
            wallet_address TEXT,
            username TEXT,
            win_rate REAL,
            total_trades INTEGER,
            total_volume REAL,
            profit_loss REAL,
            niches TEXT,                     -- JSON list e.g. ["NBA","Politics"]
            raw_data TEXT,                   -- full JSON from API
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS rag_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query TEXT UNIQUE,
            content TEXT,                    -- enriched text from APIFY/web
            source_urls TEXT,               -- JSON list
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS learning_loop (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trader_id INTEGER,
            platform TEXT,
            event_id TEXT,
            event_title TEXT,
            agent_recommendation TEXT,      -- 'copy' | 'skip'
            outcome TEXT,                   -- 'win' | 'loss' | 'pending'
            pnl REAL,
            created_at TEXT DEFAULT (datetime('now')),
            resolved_at TEXT
        );

        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            role TEXT,
            content TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
    """)
    conn.commit()
    conn.close()
    logger.info("DB initialized.")


# ── Trader CRUD ──────────────────────────────────────────────────────────────

def upsert_trader(platform: str, wallet: str, data: dict) -> int:
    conn = get_conn()
    existing = conn.execute(
        "SELECT id FROM traders WHERE platform=? AND wallet_address=?", (platform, wallet)
    ).fetchone()
    niches_json = json.dumps(data.get("niches", []))
    raw_json = json.dumps(data)
    if existing:
        conn.execute("""
            UPDATE traders SET username=?, win_rate=?, total_trades=?, total_volume=?,
            profit_loss=?, niches=?, raw_data=?, updated_at=datetime('now')
            WHERE id=?
        """, (data.get("username"), data.get("win_rate"), data.get("total_trades"),
              data.get("total_volume"), data.get("profit_loss"), niches_json, raw_json, existing["id"]))
        row_id = existing["id"]
    else:
        cur = conn.execute("""
            INSERT INTO traders (platform, wallet_address, username, win_rate, total_trades,
            total_volume, profit_loss, niches, raw_data)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (platform, wallet, data.get("username"), data.get("win_rate"), data.get("total_trades"),
              data.get("total_volume"), data.get("profit_loss"), niches_json, raw_json))
        row_id = cur.lastrowid
    conn.commit()
    conn.close()
    return row_id


def get_traders(platform: str = None, niche: str = None, min_win_rate: float = 0.0) -> list[dict]:
    conn = get_conn()
    query = "SELECT * FROM traders WHERE win_rate >= ?"
    params = [min_win_rate]
    if platform:
        query += " AND platform=?"
        params.append(platform)
    if niche:
        query += " AND niches LIKE ?"
        params.append(f'%{niche}%')
    query += " ORDER BY win_rate DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── RAG Cache ─────────────────────────────────────────────────────────────────

def save_rag(query: str, content: str, source_urls: list[str]):
    conn = get_conn()
    conn.execute("""
        INSERT OR REPLACE INTO rag_cache (query, content, source_urls)
        VALUES (?,?,?)
    """, (query, content, json.dumps(source_urls)))
    conn.commit()
    conn.close()


def get_rag(query: str) -> dict | None:
    conn = get_conn()
    row = conn.execute("SELECT * FROM rag_cache WHERE query=?", (query,)).fetchone()
    conn.close()
    return dict(row) if row else None


def search_rag(keywords: str) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM rag_cache WHERE query LIKE ? OR content LIKE ? ORDER BY created_at DESC LIMIT 10",
        (f"%{keywords}%", f"%{keywords}%")
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Learning Loop ─────────────────────────────────────────────────────────────

def log_recommendation(trader_id: int, platform: str, event_id: str,
                        event_title: str, recommendation: str):
    conn = get_conn()
    conn.execute("""
        INSERT INTO learning_loop (trader_id, platform, event_id, event_title, agent_recommendation)
        VALUES (?,?,?,?,?)
    """, (trader_id, platform, event_id, event_title, recommendation))
    conn.commit()
    conn.close()


def resolve_recommendation(event_id: str, outcome: str, pnl: float):
    conn = get_conn()
    conn.execute("""
        UPDATE learning_loop SET outcome=?, pnl=?, resolved_at=datetime('now')
        WHERE event_id=? AND outcome IS NULL
    """, (outcome, pnl, event_id))
    conn.commit()
    conn.close()


def get_learning_stats(trader_id: int = None) -> dict:
    conn = get_conn()
    q = "SELECT * FROM learning_loop WHERE outcome IS NOT NULL"
    params = []
    if trader_id:
        q += " AND trader_id=?"
        params.append(trader_id)
    rows = conn.execute(q, params).fetchall()
    conn.close()
    total = len(rows)
    wins = sum(1 for r in rows if r["outcome"] == "win")
    total_pnl = sum(r["pnl"] or 0 for r in rows)
    return {
        "total_resolved": total,
        "wins": wins,
        "losses": total - wins,
        "win_rate": round(wins / total, 3) if total else 0,
        "total_pnl": round(total_pnl, 2),
    }


# ── Chat history ──────────────────────────────────────────────────────────────

def save_message(session_id: str, role: str, content: str):
    conn = get_conn()
    conn.execute(
        "INSERT INTO chat_history (session_id, role, content) VALUES (?,?,?)",
        (session_id, role, content)
    )
    conn.commit()
    conn.close()


def get_history(session_id: str, limit: int = 20) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT role, content FROM chat_history WHERE session_id=? ORDER BY id DESC LIMIT ?",
        (session_id, limit)
    ).fetchall()
    conn.close()
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]