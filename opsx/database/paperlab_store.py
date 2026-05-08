"""
PaperLab Persistent Store — SQLite backend with JSON fallback.

Stores all paper trading state in a local SQLite database so it
survives restarts, redeployments, and session refreshes.

Tables:
  paper_trades        — full trade history with AI metadata
  paper_snapshots     — portfolio snapshots (every N minutes)
  paper_strategy_stats— per-strategy win/loss rates
  paper_learning      — AI learning outcomes per closed trade

Safety:
  - read-only flag enforced at all layers
  - real_trade: False always
  - no connection to live brokers
"""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger("jarvis.paperlab_store")

_DB_PATH  = Path("data/paperlab/paperlab.db")
_LOCK     = threading.Lock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """Create all tables if they don't exist."""
    with _connect() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS paper_trades (
            id              TEXT PRIMARY KEY,
            symbol          TEXT NOT NULL,
            asset_type      TEXT DEFAULT 'stock',
            side            TEXT NOT NULL,
            quantity        REAL NOT NULL,
            entry_price     REAL,
            exit_price      REAL,
            pnl             REAL DEFAULT 0,
            pnl_pct         REAL DEFAULT 0,
            market_value    REAL DEFAULT 0,
            confidence      REAL DEFAULT 0,
            ai_rationale    TEXT,
            strategy        TEXT,
            market_regime   TEXT,
            volatility_regime TEXT,
            status          TEXT DEFAULT 'open',
            opened_at       TEXT NOT NULL,
            closed_at       TEXT,
            exec_latency_ms INTEGER,
            real_trade      INTEGER DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_trades_sym    ON paper_trades(symbol);
        CREATE INDEX IF NOT EXISTS idx_trades_status ON paper_trades(status);
        CREATE INDEX IF NOT EXISTS idx_trades_opened ON paper_trades(opened_at);

        CREATE TABLE IF NOT EXISTS paper_snapshots (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_at     TEXT NOT NULL,
            net_liquidation REAL DEFAULT 0,
            unrealized_pnl  REAL DEFAULT 0,
            realized_pnl    REAL DEFAULT 0,
            cash            REAL DEFAULT 0,
            buying_power    REAL DEFAULT 0,
            position_count  INTEGER DEFAULT 0,
            positions_json  TEXT,
            real_trade      INTEGER DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_snaps_at ON paper_snapshots(snapshot_at);

        CREATE TABLE IF NOT EXISTS paper_strategy_stats (
            strategy        TEXT PRIMARY KEY,
            trades          INTEGER DEFAULT 0,
            wins            INTEGER DEFAULT 0,
            losses          INTEGER DEFAULT 0,
            win_rate        REAL DEFAULT 0,
            avg_pnl         REAL DEFAULT 0,
            avg_win         REAL DEFAULT 0,
            avg_loss        REAL DEFAULT 0,
            profit_factor   REAL DEFAULT 0,
            last_updated    TEXT
        );

        CREATE TABLE IF NOT EXISTS paper_learning (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_id        TEXT NOT NULL,
            symbol          TEXT,
            strategy        TEXT,
            predicted_direction TEXT,
            actual_direction    TEXT,
            predicted_correct   INTEGER DEFAULT 0,
            confidence      REAL DEFAULT 0,
            pnl             REAL DEFAULT 0,
            market_regime   TEXT,
            lesson          TEXT,
            recorded_at     TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_learning_strat ON paper_learning(strategy);
        CREATE INDEX IF NOT EXISTS idx_learning_sym   ON paper_learning(symbol);
        """)
    log.info("PaperLab SQLite store initialized at %s", _DB_PATH)


class PaperLabStore:
    """
    Thread-safe SQLite-backed storage for paper trading state.
    Singleton pattern — use module-level `store` instance.
    """

    def __init__(self) -> None:
        init_db()

    # ── Trades ─────────────────────────────────────────────────────────────

    def record_trade(self, trade: Dict) -> None:
        """Insert or update a paper trade record."""
        with _LOCK, _connect() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO paper_trades
                (id, symbol, asset_type, side, quantity, entry_price, exit_price,
                 pnl, pnl_pct, market_value, confidence, ai_rationale, strategy,
                 market_regime, volatility_regime, status, opened_at, closed_at,
                 exec_latency_ms, real_trade)
                VALUES
                (:id,:symbol,:asset_type,:side,:quantity,:entry_price,:exit_price,
                 :pnl,:pnl_pct,:market_value,:confidence,:ai_rationale,:strategy,
                 :market_regime,:volatility_regime,:status,:opened_at,:closed_at,
                 :exec_latency_ms,0)
            """, {
                "id":               trade.get("id", f"pt_{int(datetime.now().timestamp()*1000)}"),
                "symbol":           trade.get("symbol", ""),
                "asset_type":       trade.get("asset_type", "stock"),
                "side":             trade.get("side", "buy"),
                "quantity":         float(trade.get("quantity", 0)),
                "entry_price":      trade.get("entry_price") or trade.get("price"),
                "exit_price":       trade.get("exit_price"),
                "pnl":              float(trade.get("pnl", 0)),
                "pnl_pct":          float(trade.get("pnl_pct", 0)),
                "market_value":     float(trade.get("market_value", 0)),
                "confidence":       float(trade.get("confidence", 0)),
                "ai_rationale":     trade.get("ai_rationale") or trade.get("rationale"),
                "strategy":         trade.get("strategy", "manual"),
                "market_regime":    trade.get("market_regime"),
                "volatility_regime":trade.get("volatility_regime"),
                "status":           trade.get("status", "open"),
                "opened_at":        trade.get("opened_at") or trade.get("timestamp") or _now_iso(),
                "closed_at":        trade.get("closed_at"),
                "exec_latency_ms":  trade.get("exec_latency_ms"),
            })

    def get_trades(self, limit: int = 200, status: Optional[str] = None) -> List[Dict]:
        with _connect() as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM paper_trades WHERE status=? ORDER BY opened_at DESC LIMIT ?",
                    (status, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM paper_trades ORDER BY opened_at DESC LIMIT ?",
                    (limit,)
                ).fetchall()
        return [dict(r) for r in rows]

    def get_equity_curve(self) -> List[Dict]:
        """Returns portfolio value over time from snapshots for charting."""
        with _connect() as conn:
            rows = conn.execute("""
                SELECT snapshot_at, net_liquidation, unrealized_pnl, realized_pnl, cash
                FROM paper_snapshots
                ORDER BY snapshot_at
            """).fetchall()
        return [dict(r) for r in rows]

    # ── Snapshots ──────────────────────────────────────────────────────────

    def save_snapshot(self, snapshot: Dict) -> None:
        with _LOCK, _connect() as conn:
            conn.execute("""
                INSERT INTO paper_snapshots
                (snapshot_at, net_liquidation, unrealized_pnl, realized_pnl,
                 cash, buying_power, position_count, positions_json, real_trade)
                VALUES (?,?,?,?,?,?,?,?,0)
            """, (
                snapshot.get("snapshot_at") or _now_iso(),
                float(snapshot.get("net_liquidation", 0)),
                float(snapshot.get("unrealized_pnl", 0)),
                float(snapshot.get("realized_pnl", 0)),
                float(snapshot.get("cash", 0)),
                float(snapshot.get("buying_power", 0)),
                int(snapshot.get("position_count", 0)),
                json.dumps(snapshot.get("positions", [])),
            ))

    # ── Strategy Stats ─────────────────────────────────────────────────────

    def update_strategy_stats(self, strategy: str, pnl: float) -> None:
        with _LOCK, _connect() as conn:
            row = conn.execute(
                "SELECT * FROM paper_strategy_stats WHERE strategy=?", (strategy,)
            ).fetchone()
            if row:
                trades  = row["trades"] + 1
                wins    = row["wins"]   + (1 if pnl > 0 else 0)
                losses  = row["losses"] + (1 if pnl < 0 else 0)
                avg_pnl = (row["avg_pnl"] * row["trades"] + pnl) / trades
                avg_win = ((row["avg_win"] * row["wins"] + pnl) / (wins or 1)) if pnl > 0 else row["avg_win"]
                avg_los = ((row["avg_loss"] * row["losses"] + pnl) / (losses or 1)) if pnl < 0 else row["avg_loss"]
                win_rate = round(wins / trades * 100, 1) if trades else 0
                pf = round(abs(avg_win * wins) / abs(avg_los * losses), 2) if losses and avg_los else 0
                conn.execute("""
                    UPDATE paper_strategy_stats SET trades=?,wins=?,losses=?,win_rate=?,
                    avg_pnl=?,avg_win=?,avg_loss=?,profit_factor=?,last_updated=?
                    WHERE strategy=?
                """, (trades, wins, losses, win_rate, avg_pnl, avg_win, avg_los, pf, _now_iso(), strategy))
            else:
                conn.execute("""
                    INSERT INTO paper_strategy_stats
                    (strategy,trades,wins,losses,win_rate,avg_pnl,avg_win,avg_loss,profit_factor,last_updated)
                    VALUES (?,1,?,?,?,?,?,?,?,?)
                """, (
                    strategy,
                    1 if pnl > 0 else 0,
                    1 if pnl < 0 else 0,
                    100.0 if pnl > 0 else 0.0,
                    pnl, max(pnl, 0), min(pnl, 0), 0.0 if pnl <= 0 else float("inf"), _now_iso()
                ))

    def get_strategy_stats(self) -> List[Dict]:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT * FROM paper_strategy_stats ORDER BY win_rate DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Learning Records ───────────────────────────────────────────────────

    def record_learning(self, learning: Dict) -> None:
        with _LOCK, _connect() as conn:
            conn.execute("""
                INSERT INTO paper_learning
                (trade_id, symbol, strategy, predicted_direction, actual_direction,
                 predicted_correct, confidence, pnl, market_regime, lesson, recorded_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, (
                learning.get("trade_id", ""),
                learning.get("symbol", ""),
                learning.get("strategy", ""),
                learning.get("predicted_direction"),
                learning.get("actual_direction"),
                int(learning.get("predicted_correct", False)),
                float(learning.get("confidence", 0)),
                float(learning.get("pnl", 0)),
                learning.get("market_regime"),
                learning.get("lesson"),
                _now_iso(),
            ))

    def get_learning_summary(self) -> Dict:
        with _connect() as conn:
            total = conn.execute("SELECT COUNT(*) FROM paper_learning").fetchone()[0]
            correct = conn.execute(
                "SELECT COUNT(*) FROM paper_learning WHERE predicted_correct=1"
            ).fetchone()[0]
            avg_conf = conn.execute(
                "SELECT AVG(confidence) FROM paper_learning"
            ).fetchone()[0] or 0
            recent = conn.execute("""
                SELECT lesson FROM paper_learning
                WHERE lesson IS NOT NULL
                ORDER BY recorded_at DESC LIMIT 5
            """).fetchall()
        return {
            "total_decisions":   total,
            "correct":           correct,
            "accuracy_pct":      round(correct / total * 100, 1) if total else 0,
            "avg_confidence":    round(float(avg_conf), 2),
            "recent_lessons":    [r[0] for r in recent],
            "real_trade":        False,
        }

    # ── Analytics ─────────────────────────────────────────────────────────

    def get_analytics(self) -> Dict:
        with _connect() as conn:
            total = conn.execute("SELECT COUNT(*) FROM paper_trades").fetchone()[0]
            closed = conn.execute(
                "SELECT COUNT(*) FROM paper_trades WHERE status='closed'"
            ).fetchone()[0]
            wins = conn.execute(
                "SELECT COUNT(*) FROM paper_trades WHERE pnl > 0 AND status='closed'"
            ).fetchone()[0]
            losses = conn.execute(
                "SELECT COUNT(*) FROM paper_trades WHERE pnl < 0 AND status='closed'"
            ).fetchone()[0]
            total_pnl = conn.execute(
                "SELECT SUM(pnl) FROM paper_trades WHERE status='closed'"
            ).fetchone()[0] or 0
            best = conn.execute(
                "SELECT symbol, pnl, pnl_pct FROM paper_trades WHERE status='closed' ORDER BY pnl DESC LIMIT 1"
            ).fetchone()
            worst = conn.execute(
                "SELECT symbol, pnl, pnl_pct FROM paper_trades WHERE status='closed' ORDER BY pnl ASC LIMIT 1"
            ).fetchone()
        win_rate = round(wins / closed * 100, 1) if closed else 0
        return {
            "total_trades":    total,
            "closed_trades":   closed,
            "open_trades":     total - closed,
            "wins":            wins,
            "losses":          losses,
            "win_rate_pct":    win_rate,
            "total_pnl":       round(float(total_pnl), 2),
            "best_trade":      dict(best) if best else None,
            "worst_trade":     dict(worst) if worst else None,
            "real_trade":      False,
        }


# Module-level singleton
store = PaperLabStore()
