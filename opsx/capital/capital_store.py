"""
JARVIS Capital SQLite Store.

Tables:
  jarvis_capital_vault  — single-row capital vault state (upserted)
  capital_readiness     — readiness score + full change history
  capital_transfers     — immutable audit trail of profit transfers
  capital_risk_log      — risk temperature / mode change history
"""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

_DB_PATH = Path("data/capital/jarvis_capital.db")
_LOCK    = threading.Lock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _conn() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA foreign_keys=ON")
    return c


def init_db() -> None:
    with _conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS jarvis_capital_vault (
            id                INTEGER PRIMARY KEY CHECK (id = 1),
            sandbox_capital   REAL    DEFAULT 0,
            sandbox_value     REAL    DEFAULT 0,
            realized_profit   REAL    DEFAULT 0,
            unrealized_profit REAL    DEFAULT 0,
            total_transfers   REAL    DEFAULT 0,
            deployment_phase  INTEGER DEFAULT 1,
            risk_mode         TEXT    DEFAULT 'balanced',
            is_active         INTEGER DEFAULT 0,
            max_allocation    REAL    DEFAULT 500,
            allocated_at      TEXT,
            updated_at        TEXT
        );
        INSERT OR IGNORE INTO jarvis_capital_vault (id) VALUES (1);

        CREATE TABLE IF NOT EXISTS capital_readiness (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            score         REAL    NOT NULL,
            level         INTEGER NOT NULL,
            level_name    TEXT    NOT NULL,
            delta         REAL    DEFAULT 0,
            reason        TEXT,
            trade_quality REAL    DEFAULT 0,
            drawdown_pct  REAL    DEFAULT 0,
            recorded_at   TEXT    NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_readiness_at ON capital_readiness(recorded_at);

        CREATE TABLE IF NOT EXISTS capital_transfers (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            amount           REAL    NOT NULL,
            source           TEXT    NOT NULL DEFAULT 'jarvis_capital',
            destination      TEXT    NOT NULL DEFAULT 'human_portfolio',
            approved_by      TEXT    NOT NULL DEFAULT 'user',
            vault_before     REAL    DEFAULT 0,
            vault_after      REAL    DEFAULT 0,
            performance_snap TEXT,
            reason           TEXT,
            transferred_at   TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS capital_risk_log (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            mode         TEXT    NOT NULL,
            prev_mode    TEXT,
            trigger      TEXT,
            vix_at_time  REAL,
            recorded_at  TEXT    NOT NULL
        );
        """)


class CapitalStore:
    def __init__(self) -> None:
        init_db()

    # ── Vault ──────────────────────────────────────────────────────────────

    def get_vault(self) -> Dict:
        with _conn() as c:
            row = c.execute("SELECT * FROM jarvis_capital_vault WHERE id=1").fetchone()
        return dict(row) if row else {}

    def update_vault(self, updates: Dict) -> None:
        allowed = {
            "sandbox_capital", "sandbox_value", "realized_profit",
            "unrealized_profit", "total_transfers", "deployment_phase",
            "risk_mode", "is_active", "max_allocation", "allocated_at",
        }
        safe = {k: v for k, v in updates.items() if k in allowed}
        if not safe:
            return
        safe["updated_at"] = _now_iso()
        cols = ", ".join(f"{k}=:{k}" for k in safe)
        with _LOCK, _conn() as c:
            c.execute(f"UPDATE jarvis_capital_vault SET {cols} WHERE id=1", safe)

    def allocate_capital(self, amount: float) -> Dict:
        vault = self.get_vault()
        max_alloc = float(vault.get("max_allocation", 500))
        current   = float(vault.get("sandbox_capital", 0))
        if amount <= 0:
            return {"ok": False, "error": "Amount must be positive"}
        if amount > max_alloc:
            return {"ok": False, "error": f"Exceeds max allocation ${max_alloc:,.0f}"}
        if current > 0:
            return {"ok": False, "error": "Capital already allocated — transfer profits first to reallocate"}
        self.update_vault({
            "sandbox_capital":   round(amount, 2),
            "sandbox_value":     round(amount, 2),
            "realized_profit":   0,
            "unrealized_profit": 0,
            "is_active":         1,
            "allocated_at":      _now_iso(),
        })
        return {"ok": True, "allocated": amount}

    # ── Readiness ──────────────────────────────────────────────────────────

    def record_readiness(self, score: float, delta: float, reason: str,
                         trade_quality: float = 0, drawdown_pct: float = 0) -> None:
        level, level_name = _level_from_score(score)
        with _LOCK, _conn() as c:
            c.execute("""
                INSERT INTO capital_readiness
                (score, level, level_name, delta, reason, trade_quality, drawdown_pct, recorded_at)
                VALUES (?,?,?,?,?,?,?,?)
            """, (round(score, 2), level, level_name, round(delta, 2), reason,
                  round(trade_quality, 2), round(drawdown_pct, 2), _now_iso()))

    def get_latest_readiness(self) -> Optional[Dict]:
        with _conn() as c:
            row = c.execute(
                "SELECT * FROM capital_readiness ORDER BY recorded_at DESC LIMIT 1"
            ).fetchone()
        return dict(row) if row else None

    def get_readiness_history(self, limit: int = 60) -> List[Dict]:
        with _conn() as c:
            rows = c.execute(
                "SELECT * FROM capital_readiness ORDER BY recorded_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Transfers ──────────────────────────────────────────────────────────

    def record_transfer(self, amount: float, reason: str, perf_snap: Dict) -> Dict:
        vault = self.get_vault()
        profit = float(vault.get("realized_profit", 0))
        if amount > profit:
            return {"ok": False, "error": f"Only ${profit:,.2f} profit available"}
        vault_before = float(vault.get("sandbox_value", 0))
        vault_after  = round(vault_before - amount, 2)
        with _LOCK, _conn() as c:
            c.execute("""
                INSERT INTO capital_transfers
                (amount, source, destination, approved_by,
                 vault_before, vault_after, performance_snap, reason, transferred_at)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, (
                round(amount, 2), "jarvis_capital", "human_portfolio", "user",
                vault_before, vault_after,
                json.dumps(perf_snap),
                reason, _now_iso(),
            ))
        self.update_vault({
            "realized_profit": round(profit - amount, 2),
            "total_transfers": round(float(vault.get("total_transfers", 0)) + amount, 2),
            "sandbox_value":   vault_after,
        })
        return {"ok": True, "transferred": amount, "vault_after": vault_after}

    def get_transfers(self) -> List[Dict]:
        with _conn() as c:
            rows = c.execute(
                "SELECT * FROM capital_transfers ORDER BY transferred_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Risk log ───────────────────────────────────────────────────────────

    def log_risk_mode(self, mode: str, prev_mode: str, trigger: str,
                      vix: Optional[float] = None) -> None:
        with _LOCK, _conn() as c:
            c.execute(
                "INSERT INTO capital_risk_log (mode, prev_mode, trigger, vix_at_time, recorded_at) VALUES (?,?,?,?,?)",
                (mode, prev_mode, trigger, vix, _now_iso())
            )

    def get_risk_log(self, limit: int = 20) -> List[Dict]:
        with _conn() as c:
            rows = c.execute(
                "SELECT * FROM capital_risk_log ORDER BY recorded_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]


# ── Level mapping ──────────────────────────────────────────────────────────────

READINESS_LEVELS = [
    (0,  1, "Observer"),
    (15, 2, "Pattern Learner"),
    (30, 3, "Risk Aware"),
    (45, 4, "Consistent Simulator"),
    (60, 5, "Disciplined Operator"),
    (75, 6, "Capital Candidate"),
    (90, 7, "Micro Allocation Approved"),
]


def _level_from_score(score: float):
    level, name = 1, "Observer"
    for threshold, lvl, n in READINESS_LEVELS:
        if score >= threshold:
            level, name = lvl, n
    return level, name


# Singleton
capital_store = CapitalStore()
