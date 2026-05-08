"""
JARVIS AI Memory Store — shared SQLite foundation for all memory modules.

Single database at data/memory/ai_memory.db with tables partitioned by
responsibility. Each memory module reads/writes its own table(s); this
module owns schema creation and low-level I/O only.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

_DB_PATH = Path("data/memory/ai_memory.db")
_LOCK    = threading.Lock()

# In-memory activity feed (hot path — no DB read needed for polling)
_ACTIVITY_DEQUE: deque = deque(maxlen=150)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _conn() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA synchronous=NORMAL")
    return c


def init_memory_db() -> None:
    with _conn() as c:
        c.executescript("""
        -- Live AI activity feed ──────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS activity_feed (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            category    TEXT    NOT NULL DEFAULT 'general',
            message     TEXT    NOT NULL,
            symbol      TEXT,
            asset_class TEXT,
            strategy    TEXT,
            confidence  REAL,
            severity    TEXT    DEFAULT 'info',
            recorded_at TEXT    NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_feed_at  ON activity_feed(recorded_at DESC);
        CREATE INDEX IF NOT EXISTS idx_feed_cat ON activity_feed(category);

        -- Training decisions (pending scoring) ──────────────────────────────────
        CREATE TABLE IF NOT EXISTS training_decisions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol          TEXT    NOT NULL,
            asset_class     TEXT    DEFAULT 'equity',
            strategy_style  TEXT    DEFAULT 'momentum',
            direction       TEXT    NOT NULL,
            confidence      REAL    NOT NULL,
            entry_price     REAL,
            scored          INTEGER DEFAULT 0,
            actual_direction TEXT,
            outcome_pnl_pct REAL,
            quality_score   REAL,
            decided_at      TEXT    NOT NULL,
            scored_at       TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_td_scored ON training_decisions(scored, decided_at);

        -- Strategy performance by style ──────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS strategy_style_perf (
            style           TEXT    PRIMARY KEY,
            decisions       INTEGER DEFAULT 0,
            correct         INTEGER DEFAULT 0,
            accuracy_pct    REAL    DEFAULT 0,
            avg_quality     REAL    DEFAULT 0,
            last_decision   TEXT,
            confidence_ema  REAL    DEFAULT 0.5,
            updated_at      TEXT
        );

        -- Asset class performance ────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS asset_class_perf (
            asset_class     TEXT    PRIMARY KEY,
            decisions       INTEGER DEFAULT 0,
            correct         INTEGER DEFAULT 0,
            accuracy_pct    REAL    DEFAULT 0,
            avg_quality     REAL    DEFAULT 0,
            updated_at      TEXT
        );

        -- Market regime history ──────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS regime_history (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            regime      TEXT    NOT NULL,
            vix         REAL,
            spy_ret_5d  REAL,
            spy_ret_20d REAL,
            confidence  REAL    DEFAULT 0.7,
            source      TEXT    DEFAULT 'autonomous',
            recorded_at TEXT    NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_regime_at ON regime_history(recorded_at DESC);

        -- Historical replay results ──────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS replay_results (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            scenario    TEXT    NOT NULL,
            symbols     TEXT,
            start_date  TEXT,
            end_date    TEXT,
            win_rate    REAL,
            total_return_pct REAL,
            max_drawdown REAL,
            sharpe_approx REAL,
            decisions   INTEGER DEFAULT 0,
            lessons     TEXT,
            run_at      TEXT    NOT NULL
        );

        -- Behavioral events ──────────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS behavioral_events (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type  TEXT    NOT NULL,
            description TEXT,
            severity    TEXT    DEFAULT 'info',
            recorded_at TEXT    NOT NULL
        );

        -- Crypto performance ─────────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS crypto_performance (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol      TEXT    NOT NULL,
            decisions   INTEGER DEFAULT 1,
            correct     INTEGER DEFAULT 0,
            accuracy    REAL    DEFAULT 0,
            last_signal TEXT,
            recorded_at TEXT    NOT NULL
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_crypto_sym ON crypto_performance(symbol);

        -- Futures performance ────────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS futures_performance (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            contract    TEXT    NOT NULL,
            proxy       TEXT,
            decisions   INTEGER DEFAULT 1,
            correct     INTEGER DEFAULT 0,
            accuracy    REAL    DEFAULT 0,
            recorded_at TEXT    NOT NULL
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_futures_contract ON futures_performance(contract);
        """)


# ── Activity Feed ──────────────────────────────────────────────────────────────

def post_activity(
    message: str,
    category: str = "general",
    symbol: Optional[str] = None,
    asset_class: Optional[str] = None,
    strategy: Optional[str] = None,
    confidence: Optional[float] = None,
    severity: str = "info",
) -> None:
    """Post a new AI activity event. Written to both in-memory deque and SQLite."""
    ts = _now_iso()
    entry = {
        "category":    category,
        "message":     message,
        "symbol":      symbol,
        "asset_class": asset_class,
        "strategy":    strategy,
        "confidence":  round(float(confidence), 2) if confidence is not None else None,
        "severity":    severity,
        "recorded_at": ts,
    }
    _ACTIVITY_DEQUE.appendleft(entry)
    try:
        with _LOCK, _conn() as c:
            c.execute("""
                INSERT INTO activity_feed
                (category,message,symbol,asset_class,strategy,confidence,severity,recorded_at)
                VALUES (?,?,?,?,?,?,?,?)
            """, (category, message, symbol, asset_class, strategy,
                  confidence, severity, ts))
    except Exception:
        pass  # deque is always available


def get_activity_feed(limit: int = 50, category: Optional[str] = None) -> List[Dict]:
    """Return recent activity events from the hot in-memory deque."""
    items = list(_ACTIVITY_DEQUE)
    if category:
        items = [i for i in items if i.get("category") == category]
    return items[:limit]


# ── Training Decisions ─────────────────────────────────────────────────────────

def record_decision(
    symbol: str, asset_class: str, strategy_style: str,
    direction: str, confidence: float, entry_price: float,
) -> int:
    with _LOCK, _conn() as c:
        cur = c.execute("""
            INSERT INTO training_decisions
            (symbol, asset_class, strategy_style, direction, confidence, entry_price, decided_at)
            VALUES (?,?,?,?,?,?,?)
        """, (symbol, asset_class, strategy_style, direction,
              round(confidence, 4), round(entry_price, 4), _now_iso()))
        return cur.lastrowid


def get_pending_decisions(limit: int = 100) -> List[Dict]:
    with _conn() as c:
        rows = c.execute("""
            SELECT * FROM training_decisions
            WHERE scored=0
            ORDER BY decided_at ASC LIMIT ?
        """, (limit,)).fetchall()
    return [dict(r) for r in rows]


def score_decision(
    decision_id: int, actual_direction: str,
    outcome_pnl_pct: float, quality_score: float,
) -> None:
    with _LOCK, _conn() as c:
        c.execute("""
            UPDATE training_decisions
            SET scored=1, actual_direction=?, outcome_pnl_pct=?, quality_score=?,
                scored_at=?
            WHERE id=?
        """, (actual_direction, round(outcome_pnl_pct, 4),
              round(quality_score, 2), _now_iso(), decision_id))


# ── Strategy Style Performance ─────────────────────────────────────────────────

def update_strategy_style(style: str, correct: bool, quality: float) -> None:
    alpha = 0.15
    with _LOCK, _conn() as c:
        row = c.execute(
            "SELECT * FROM strategy_style_perf WHERE style=?", (style,)
        ).fetchone()
        ts = _now_iso()
        if row:
            n    = row["decisions"] + 1
            corr = row["correct"] + (1 if correct else 0)
            acc  = round(corr / n * 100, 1)
            avg_q = round((row["avg_quality"] * row["decisions"] + quality) / n, 2)
            ema  = round(row["confidence_ema"] * (1 - alpha) + quality / 100 * alpha, 4)
            c.execute("""
                UPDATE strategy_style_perf
                SET decisions=?,correct=?,accuracy_pct=?,avg_quality=?,
                    confidence_ema=?,last_decision=?,updated_at=?
                WHERE style=?
            """, (n, corr, acc, avg_q, ema, ts, ts, style))
        else:
            c.execute("""
                INSERT INTO strategy_style_perf
                (style,decisions,correct,accuracy_pct,avg_quality,confidence_ema,
                 last_decision,updated_at)
                VALUES (?,1,?,?,?,?,?,?)
            """, (style, 1 if correct else 0,
                  100.0 if correct else 0.0,
                  round(quality, 2),
                  quality / 100, ts, ts))


def get_strategy_style_perf() -> List[Dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM strategy_style_perf ORDER BY accuracy_pct DESC"
        ).fetchall()
    return [dict(r) for r in rows]


# ── Asset Class Performance ────────────────────────────────────────────────────

def update_asset_perf(asset_class: str, correct: bool, quality: float) -> None:
    with _LOCK, _conn() as c:
        row = c.execute(
            "SELECT * FROM asset_class_perf WHERE asset_class=?", (asset_class,)
        ).fetchone()
        ts = _now_iso()
        if row:
            n    = row["decisions"] + 1
            corr = row["correct"] + (1 if correct else 0)
            acc  = round(corr / n * 100, 1)
            avg_q = round((row["avg_quality"] * row["decisions"] + quality) / n, 2)
            c.execute("""
                UPDATE asset_class_perf
                SET decisions=?,correct=?,accuracy_pct=?,avg_quality=?,updated_at=?
                WHERE asset_class=?
            """, (n, corr, acc, avg_q, ts, asset_class))
        else:
            c.execute("""
                INSERT INTO asset_class_perf
                (asset_class,decisions,correct,accuracy_pct,avg_quality,updated_at)
                VALUES (?,1,?,?,?,?)
            """, (asset_class, 1 if correct else 0,
                  100.0 if correct else 0.0, round(quality, 2), ts))


def get_asset_class_perf() -> List[Dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM asset_class_perf ORDER BY accuracy_pct DESC"
        ).fetchall()
    return [dict(r) for r in rows]


# ── Regime History ─────────────────────────────────────────────────────────────

def record_regime(regime: str, vix: Optional[float] = None,
                  spy_ret_5d: float = 0, spy_ret_20d: float = 0) -> None:
    with _LOCK, _conn() as c:
        c.execute("""
            INSERT INTO regime_history (regime,vix,spy_ret_5d,spy_ret_20d,recorded_at)
            VALUES (?,?,?,?,?)
        """, (regime, vix, round(spy_ret_5d, 3), round(spy_ret_20d, 3), _now_iso()))


def get_regime_history(limit: int = 20) -> List[Dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM regime_history ORDER BY recorded_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


# ── Replay Results ─────────────────────────────────────────────────────────────

def save_replay_result(scenario: str, symbols: List[str], start: str, end: str,
                       win_rate: float, total_return: float, max_dd: float,
                       decisions: int, lessons: str) -> None:
    sharpe = round(total_return / max(abs(max_dd), 1) * 0.5, 2) if max_dd != 0 else 0
    with _LOCK, _conn() as c:
        c.execute("""
            INSERT INTO replay_results
            (scenario,symbols,start_date,end_date,win_rate,total_return_pct,
             max_drawdown,sharpe_approx,decisions,lessons,run_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (scenario, json.dumps(symbols), start, end,
              round(win_rate, 1), round(total_return, 2),
              round(max_dd, 2), sharpe, decisions, lessons, _now_iso()))


def get_replay_results(limit: int = 10) -> List[Dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM replay_results ORDER BY run_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


# ── Behavioral Events ──────────────────────────────────────────────────────────

def record_behavioral_event(event_type: str, description: str,
                            severity: str = "info") -> None:
    with _LOCK, _conn() as c:
        c.execute("""
            INSERT INTO behavioral_events (event_type, description, severity, recorded_at)
            VALUES (?,?,?,?)
        """, (event_type, description, severity, _now_iso()))


# ── Initialize on import ───────────────────────────────────────────────────────
try:
    init_memory_db()
except Exception as _exc:
    import logging
    logging.getLogger("jarvis.ai_memory").warning("Memory store init failed: %s", _exc)
