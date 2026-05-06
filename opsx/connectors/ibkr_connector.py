"""
IBKR TWS / IB Gateway Connector — Phase 1.

Read-only connection to Interactive Brokers via the TWS socket API (ib_insync).
All trade-execution methods are HARD BLOCKED and raise SecurityViolationError.

Connection targets:
  - IB Gateway (paper): localhost:4002
  - IB Gateway (live):  localhost:4001
  - TWS (paper):        localhost:7497
  - TWS (live):         localhost:7496

Rules:
  - NO live trading. NO order placement. ALL operations read-only.
  - real_trade: False in every response dict.
  - Blocked attempts logged to data/portfolio/trading_guardrail_log.json.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger("jarvis.ibkr_connector")

_GUARDRAIL_LOG = Path("data/portfolio/trading_guardrail_log.json")
_SNAPSHOT_PATH = Path("data/portfolio/ibkr_tws_snapshot.json")

# ── Ports ─────────────────────────────────────────────────────────────────────
_DEFAULT_HOST = os.getenv("IBKR_HOST", "127.0.0.1")
_DEFAULT_PORT = int(os.getenv("IBKR_PORT", "4002"))   # IB Gateway paper
_DEFAULT_CLIENT_ID = int(os.getenv("IBKR_CLIENT_ID", "1"))

_BLOCKED_METHODS = frozenset({
    "placeOrder", "cancelOrder", "modifyOrder",
    "place_order", "cancel_order", "modify_order",
    "reqGlobalCancel", "reqOpenOrders", "execDetails",
    "transmit_order", "execute_trade", "create_trade",
    "preview_order", "order_reply",
})


# ── Exceptions ────────────────────────────────────────────────────────────────

class SecurityViolationError(Exception):
    """Raised when any trade-execution method is called."""

    def __init__(self, method: str, caller: str = "unknown"):
        self.method = method
        self.caller = caller
        super().__init__(
            f"SECURITY VIOLATION: '{method}' is blocked — JARVIS operates in READ-ONLY mode. "
            f"Caller: {caller}"
        )


class IBKRConnectionError(Exception):
    """Raised when TWS/Gateway is unreachable."""


# ── Connector ─────────────────────────────────────────────────────────────────

class IBKRConnector:
    """
    Read-only IBKR connector using ib_insync (TWS socket API).

    All methods that would place, modify, or cancel orders raise
    SecurityViolationError before touching the network.
    """

    def __init__(
        self,
        host: str = _DEFAULT_HOST,
        port: int = _DEFAULT_PORT,
        client_id: int = _DEFAULT_CLIENT_ID,
        timeout: float = 10.0,
    ):
        self.host = host
        self.port = port
        self.client_id = client_id
        self.timeout = timeout
        self._ib: Optional[Any] = None
        self._connected = False
        self._account: str = ""

    # ── Connection lifecycle ───────────────────────────────────────────────────

    def connect(self, readonly: bool = True) -> Dict:
        """
        Connect to TWS/IB Gateway.
        Always connects in read-only mode.
        """
        try:
            from ib_insync import IB
        except ImportError:
            return {
                "status": "error",
                "error": "ib_insync not installed — run: pip install ib_insync",
                "real_trade": False,
            }

        try:
            ib = IB()
            ib.connect(
                self.host,
                self.port,
                clientId=self.client_id,
                readonly=True,
                timeout=self.timeout,
            )
            self._ib = ib
            self._connected = True

            accounts = ib.managedAccounts()
            self._account = accounts[0] if accounts else ""

            log.info("IBKR TWS connected — account=%s port=%s", self._account, self.port)
            return {
                "status": "connected",
                "host": self.host,
                "port": self.port,
                "account": self._account,
                "readonly": True,
                "real_trade": False,
                "connected_at": datetime.utcnow().isoformat(),
            }
        except Exception as exc:
            self._connected = False
            log.warning("IBKR TWS connect failed: %s", exc)
            return {
                "status": "error",
                "error": str(exc),
                "host": self.host,
                "port": self.port,
                "real_trade": False,
            }

    def disconnect(self) -> Dict:
        """Disconnect from TWS/IB Gateway."""
        if self._ib and self._connected:
            try:
                self._ib.disconnect()
            except Exception:
                pass
        self._ib = None
        self._connected = False
        log.info("IBKR TWS disconnected")
        return {"status": "disconnected", "real_trade": False}

    # ── Health ────────────────────────────────────────────────────────────────

    def health_check(self) -> Dict:
        """Check TWS/Gateway connectivity without requiring authentication."""
        if not self._connected or not self._ib:
            return {
                "status": "disconnected",
                "connected": False,
                "real_trade": False,
            }
        try:
            server_time = self._ib.reqCurrentTime()
            return {
                "status": "ok",
                "connected": True,
                "server_time": str(server_time),
                "account": self._account,
                "port": self.port,
                "real_trade": False,
            }
        except Exception as exc:
            return {
                "status": "error",
                "connected": False,
                "error": str(exc),
                "real_trade": False,
            }

    # ── Read-only data methods ─────────────────────────────────────────────────

    def get_account_summary(self) -> Dict:
        """Fetch account-level financial summary (equity, buying power, etc.)."""
        if not self._require_connection():
            return self._disconnected_response("get_account_summary")

        try:
            summary_items = self._ib.accountSummary(self._account)
            fields = {}
            for item in summary_items:
                if item.tag in (
                    "NetLiquidation", "TotalCashValue", "UnrealizedPnL",
                    "RealizedPnL", "GrossPositionValue", "BuyingPower",
                    "AvailableFunds", "ExcessLiquidity", "MaintMarginReq",
                    "InitMarginReq", "DayTradesRemaining", "Currency",
                ):
                    fields[item.tag] = item.value

            result = {
                "status": "ok",
                "account": self._account,
                "net_liquidation": float(fields.get("NetLiquidation", 0) or 0),
                "total_cash": float(fields.get("TotalCashValue", 0) or 0),
                "unrealized_pnl": float(fields.get("UnrealizedPnL", 0) or 0),
                "realized_pnl": float(fields.get("RealizedPnL", 0) or 0),
                "gross_position_value": float(fields.get("GrossPositionValue", 0) or 0),
                "buying_power": float(fields.get("BuyingPower", 0) or 0),
                "available_funds": float(fields.get("AvailableFunds", 0) or 0),
                "excess_liquidity": float(fields.get("ExcessLiquidity", 0) or 0),
                "currency": fields.get("Currency", "USD"),
                "real_trade": False,
                "fetched_at": datetime.utcnow().isoformat(),
            }
            self._save_snapshot({"account_summary": result})
            return result
        except Exception as exc:
            log.error("get_account_summary failed: %s", exc)
            return {"status": "error", "error": str(exc), "real_trade": False}

    def get_positions(self) -> Dict:
        """Fetch all open positions."""
        if not self._require_connection():
            return self._disconnected_response("get_positions")

        try:
            raw_positions = self._ib.positions(self._account)
            positions = []
            for pos in raw_positions:
                contract = pos.contract
                avg_cost  = float(pos.avgCost or 0)
                quantity  = float(pos.position or 0)
                mkt_price = 0.0
                mkt_value = 0.0

                # Attempt to get market price from ticker
                try:
                    ticker = self._ib.reqMktData(contract, "", True, False)
                    self._ib.sleep(1)
                    mkt_price = float(ticker.last or ticker.close or avg_cost or 0)
                    mkt_value = round(mkt_price * quantity, 2)
                    self._ib.cancelMktData(contract)
                except Exception:
                    mkt_value = round(avg_cost * quantity, 2)
                    mkt_price = avg_cost

                unrealized = round(mkt_value - (avg_cost * quantity), 2)
                positions.append({
                    "symbol":        contract.symbol,
                    "sec_type":      contract.secType,
                    "exchange":      contract.exchange or contract.primaryExch,
                    "currency":      contract.currency,
                    "quantity":      quantity,
                    "avg_cost":      round(avg_cost, 4),
                    "market_price":  round(mkt_price, 4),
                    "market_value":  mkt_value,
                    "unrealized_pnl": unrealized,
                    "daily_pnl":     0.0,
                    "daily_pnl_pct": 0.0,
                    "sector":        "unknown",
                    "asset_class":   _classify_asset(contract.secType),
                    "real_trade":    False,
                })

            result = {
                "status":     "ok",
                "account":    self._account,
                "positions":  positions,
                "count":      len(positions),
                "real_trade": False,
                "fetched_at": datetime.utcnow().isoformat(),
            }
            self._save_snapshot({"positions": result})
            return result
        except Exception as exc:
            log.error("get_positions failed: %s", exc)
            return {"status": "error", "error": str(exc), "real_trade": False}

    def get_pnl(self) -> Dict:
        """Fetch daily and cumulative P&L."""
        if not self._require_connection():
            return self._disconnected_response("get_pnl")

        try:
            pnl_items = self._ib.reqPnL(self._account)
            self._ib.sleep(1)

            daily_pnl     = float(getattr(pnl_items, "dailyPnL", 0) or 0)
            unrealized    = float(getattr(pnl_items, "unrealizedPnL", 0) or 0)
            realized      = float(getattr(pnl_items, "realizedPnL", 0) or 0)

            self._ib.cancelPnL(self._account)

            return {
                "status":          "ok",
                "account":         self._account,
                "daily_pnl":       round(daily_pnl, 2),
                "unrealized_pnl":  round(unrealized, 2),
                "realized_pnl":    round(realized, 2),
                "real_trade":      False,
                "fetched_at":      datetime.utcnow().isoformat(),
            }
        except Exception as exc:
            log.error("get_pnl failed: %s", exc)
            return {"status": "error", "error": str(exc), "real_trade": False}

    def get_cash_balance(self) -> Dict:
        """Fetch available cash and settled cash balances."""
        if not self._require_connection():
            return self._disconnected_response("get_cash_balance")

        try:
            values = self._ib.accountValues(self._account)
            cash_fields: Dict[str, float] = {}
            for v in values:
                if v.tag in ("CashBalance", "TotalCashBalance", "AvailableFunds"):
                    cash_fields[v.tag] = float(v.value or 0)

            return {
                "status":            "ok",
                "account":           self._account,
                "cash_balance":      cash_fields.get("CashBalance", 0),
                "total_cash":        cash_fields.get("TotalCashBalance", 0),
                "available_funds":   cash_fields.get("AvailableFunds", 0),
                "currency":          "USD",
                "real_trade":        False,
                "fetched_at":        datetime.utcnow().isoformat(),
            }
        except Exception as exc:
            log.error("get_cash_balance failed: %s", exc)
            return {"status": "error", "error": str(exc), "real_trade": False}

    def get_full_portfolio(self) -> Dict:
        """
        Aggregate account summary + positions + P&L into one snapshot.
        Used by UnifiedPortfolioEngine.
        Falls back to cached snapshot if disconnected.
        """
        if not self._connected:
            cached = self._load_cached_snapshot()
            if cached:
                cached["_stale"] = True
                cached["_stale_reason"] = "IBKR TWS not connected — cached data"
                return cached
            return {
                "status":        "not_connected",
                "positions":     [],
                "pnl":           {"daily_pnl": 0, "unrealized_pnl": 0},
                "cash":          {"total_cash": 0},
                "summary":       {},
                "real_trade":    False,
            }

        summary   = self.get_account_summary()
        positions = self.get_positions()
        pnl       = self.get_pnl()
        cash      = self.get_cash_balance()

        result = {
            "status":     "ok",
            "account_id": self._account,
            "summary":    summary,
            "positions":  positions.get("positions", []),
            "pnl": {
                "daily_pnl":       pnl.get("daily_pnl", 0),
                "unrealized_pnl":  pnl.get("unrealized_pnl", 0),
                "realized_pnl":    pnl.get("realized_pnl", 0),
            },
            "cash": {
                "total_cash":     cash.get("total_cash", 0),
                "available_funds": cash.get("available_funds", 0),
            },
            "real_trade": False,
            "fetched_at": datetime.utcnow().isoformat(),
        }
        self._save_snapshot(result)
        return result

    # ── HARD BLOCKED methods ───────────────────────────────────────────────────

    def placeOrder(self, *args, **kwargs):
        return self._block("placeOrder")

    def cancelOrder(self, *args, **kwargs):
        return self._block("cancelOrder")

    def modifyOrder(self, *args, **kwargs):
        return self._block("modifyOrder")

    def place_order(self, *args, **kwargs):
        return self._block("place_order")

    def cancel_order(self, *args, **kwargs):
        return self._block("cancel_order")

    def modify_order(self, *args, **kwargs):
        return self._block("modify_order")

    def transmit_order(self, *args, **kwargs):
        return self._block("transmit_order")

    def execute_trade(self, *args, **kwargs):
        return self._block("execute_trade")

    def reqGlobalCancel(self, *args, **kwargs):
        return self._block("reqGlobalCancel")

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _block(self, method: str) -> None:
        """Log and raise SecurityViolationError for any blocked method call."""
        import traceback
        caller = "".join(traceback.format_stack()[-3:-1]).strip()
        self._log_guardrail(method, caller)
        raise SecurityViolationError(method, caller)

    def _log_guardrail(self, method: str, caller: str) -> None:
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "method":    method,
            "caller":    caller[:300],
            "account":   self._account,
            "blocked":   True,
        }
        try:
            _GUARDRAIL_LOG.parent.mkdir(parents=True, exist_ok=True)
            entries: List[Dict] = []
            if _GUARDRAIL_LOG.exists():
                entries = json.loads(_GUARDRAIL_LOG.read_text(encoding="utf-8"))
            entries.append(entry)
            _GUARDRAIL_LOG.write_text(
                json.dumps(entries[-500:], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            log.error("Guardrail log write failed: %s", exc)

        log.critical(
            "SECURITY VIOLATION BLOCKED — method=%s account=%s",
            method, self._account,
        )

    def _require_connection(self) -> bool:
        return self._connected and self._ib is not None

    def _disconnected_response(self, method: str) -> Dict:
        return {
            "status":   "disconnected",
            "method":   method,
            "message":  "IBKR TWS not connected — call connect() first",
            "real_trade": False,
        }

    def _save_snapshot(self, data: Dict) -> None:
        try:
            _SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
            existing: Dict = {}
            if _SNAPSHOT_PATH.exists():
                existing = json.loads(_SNAPSHOT_PATH.read_text(encoding="utf-8"))
            existing.update(data)
            existing["saved_at"] = datetime.utcnow().isoformat()
            _SNAPSHOT_PATH.write_text(
                json.dumps(existing, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            log.warning("Snapshot save failed: %s", exc)

    def _load_cached_snapshot(self) -> Optional[Dict]:
        try:
            if _SNAPSHOT_PATH.exists():
                return json.loads(_SNAPSHOT_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
        return None


def _classify_asset(sec_type: str) -> str:
    mapping = {
        "STK":  "equity",
        "OPT":  "options",
        "FUT":  "futures",
        "CASH": "forex",
        "BOND": "fixed_income",
        "FUND": "fund",
        "CRYPTO": "crypto",
        "CFD":  "cfd",
    }
    return mapping.get(sec_type.upper(), "other")


# Singleton
ibkr = IBKRConnector()
