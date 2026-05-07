"""
IBKR Remote Bridge Client — reads live data from the local secure bridge
via an ngrok HTTPS tunnel. For Railway deployments where localhost:4001 is
unreachable; the correct data path is:

    Railway FastAPI
      └─► HTTPS (ngrok)
            └─► secure_bridge.py (localhost:7755)
                  └─► IB Gateway LIVE (localhost:4001, readonly=True)

Required env vars (set in Railway dashboard):
  IBKR_BRIDGE_URL             e.g. https://abc123.ngrok.io
  IBKR_BRIDGE_TOKEN           token printed by secure_bridge on startup
  ENABLE_REMOTE_IBKR_BRIDGE   must be "true" to activate this client

Safety:
  - ALL execution methods raise TradingBlockedError immediately.
  - real_trade: False in every response.
  - Never connects directly to IB Gateway — bridge handles that.
"""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

log = logging.getLogger("jarvis.ibkr_bridge")

_SNAPSHOT_PATH = Path("data/portfolio/ibkr_bridge_snapshot.json")


class TradingBlockedError(RuntimeError):
    def __init__(self, method: str = "unknown"):
        super().__init__(
            f"BLOCKED: live trading disabled. Method '{method}' is not permitted. "
            "Paper trading only."
        )


class IBKRBridgeClient:
    """
    HTTP client that reads IBKR portfolio data from the local secure bridge.
    Drop-in replacement for IBKRReadOnly when ENABLE_REMOTE_IBKR_BRIDGE=true.
    """

    def __init__(self) -> None:
        self.bridge_url   = os.getenv("IBKR_BRIDGE_URL", "").rstrip("/")
        self.bridge_token = os.getenv("IBKR_BRIDGE_TOKEN", "")
        self.timeout      = float(os.getenv("IBKR_BRIDGE_TIMEOUT", "8"))
        _SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)

    def _headers(self) -> Dict:
        return {"Authorization": f"Bearer {self.bridge_token}"}

    def _get(self, path: str) -> Dict:
        if not self.bridge_url:
            return {"_bridge_error": "no_url", "message": "IBKR_BRIDGE_URL not configured"}
        if not self.bridge_token:
            return {"_bridge_error": "no_token", "message": "IBKR_BRIDGE_TOKEN not configured"}
        try:
            import httpx
            url = f"{self.bridge_url}{path}"
            t0  = time.monotonic()
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(url, headers=self._headers())
            latency_ms = round((time.monotonic() - t0) * 1000, 1)
            if resp.status_code == 401:
                return {"_bridge_error": "auth_failed", "message": "Bridge token rejected",
                        "_latency_ms": latency_ms}
            resp.raise_for_status()
            data = resp.json()
            data["_latency_ms"] = latency_ms
            return data
        except Exception as exc:
            log.warning("IBKRBridgeClient GET %s failed: %s", path, exc)
            return {"_bridge_error": str(exc)}

    # ── Health / status ────────────────────────────────────────────────────────

    def health_check(self) -> Dict:
        """Returns bridge reachability + IBKR connection state."""
        if not self.bridge_url:
            return {"status": "not_configured", "connected": False,
                    "message": "IBKR_BRIDGE_URL not set", "real_trade": False}

        data = self._get("/health")
        if "_bridge_error" in data:
            return {
                "status":    "bridge_offline",
                "connected": False,
                "error":     data.get("message", data["_bridge_error"]),
                "real_trade": False,
            }

        ibkr_section = data.get("ibkr", {})
        connected    = ibkr_section.get("connected", False)
        return {
            "status":       "connected" if connected else "bridge_ok_ibkr_offline",
            "bridge_ok":    True,
            "ibkr_connected": connected,
            "account":      ibkr_section.get("account", ""),
            "readonly":     ibkr_section.get("readonly", True),
            "latency_ms":   data.get("_latency_ms"),
            "cache_stale":  data.get("cache", {}).get("portfolio_stale", True),
            "real_trade":   False,
        }

    # ── Full portfolio ─────────────────────────────────────────────────────────

    def get_full_portfolio(self) -> Dict:
        """
        Fetch portfolio data from the bridge and return in unified format.
        Falls back to disk snapshot on bridge error.
        """
        health = self.health_check()

        if not health.get("bridge_ok"):
            stale = self._load_snapshot()
            if stale:
                stale["_stale"]        = True
                stale["_stale_reason"] = health.get("error", "bridge_offline")
                return stale
            return {
                "broker":     "ibkr",
                "status":     "disconnected",
                "positions":  [],
                "pnl":        {"daily_pnl": 0, "unrealized_pnl": 0},
                "cash":       {"total_cash": 0},
                "summary":    {},
                "_stale":     False,
                "real_trade": False,
            }

        summary   = self._get("/portfolio/summary")
        positions = self._get("/portfolio/positions")
        pnl       = self._get("/portfolio/pnl")

        bridge_connected = health.get("ibkr_connected", False)
        is_stale         = summary.get("_stale", not bridge_connected)

        pos_list = positions.get("positions", [])
        # Normalise position keys to what unified_portfolio_engine expects
        normalised = [self._normalise_position(p) for p in pos_list]

        account_id   = summary.get("account", health.get("account", ""))
        account_type = "PAPER" if account_id.startswith("DU") else ("LIVE" if account_id else "UNKNOWN")
        data_origin  = "ibkr_live" if account_type == "LIVE" else ("ibkr_paper" if account_type == "PAPER" else "unknown")

        snapshot = {
            "broker":      "ibkr",
            "status":      "connected" if bridge_connected else "disconnected",
            "account_id":  account_id,
            # ── Account separation metadata ──────────────────────────────
            "account_type":      account_type,
            "data_origin":       data_origin,
            "readonly_mode":     True,
            "execution_blocked": True,
            # ────────────────────────────────────────────────────────────
            "positions":   normalised,
            "pnl": {
                "daily_pnl":      pnl.get("daily_pnl", 0),
                "unrealized_pnl": pnl.get("unrealized_pnl", 0),
                "realized_pnl":   pnl.get("realized_pnl", 0),
            },
            "cash": {
                "total_cash":      summary.get("total_cash", 0),
                "net_liquidation": summary.get("net_liquidation", 0),
            },
            "summary": {
                "net_liquidation":     summary.get("net_liquidation", 0),
                "total_cash":          summary.get("total_cash", 0),
                "gross_position":      summary.get("gross_position", 0),
                "buying_power":        summary.get("buying_power", 0),
                "unrealized_pnl":      summary.get("unrealized_pnl", 0),
                "realized_pnl":        summary.get("realized_pnl", 0),
                "daily_pnl":           pnl.get("daily_pnl", 0),
            },
            "position_count": len(normalised),
            "_stale":         is_stale,
            "_stale_reason":  ("IBKR disconnected via bridge" if not bridge_connected else ""),
            "fetched_at":     datetime.utcnow().isoformat(),
            "real_trade":     False,
        }
        # Audit log
        try:
            from opsx.bridge.account_separation import audit_broker_interaction
            audit_broker_interaction(
                account_id, "get_full_portfolio",
                account_type=account_type, data_origin=data_origin,
                success=bridge_connected,
            )
        except Exception:
            pass
        self._save_snapshot(snapshot)
        return snapshot

    # ── Normalise bridge position format → unified format ──────────────────────

    def _normalise_position(self, raw: Dict) -> Dict:
        mkt_val   = float(raw.get("market_value",  raw.get("mktValue",   0)) or 0)
        avg_cost  = float(raw.get("avg_cost",      raw.get("avgCost",    0)) or 0)
        mkt_price = float(raw.get("market_price",  raw.get("mktPrice",   0)) or avg_cost)
        qty       = float(raw.get("quantity",      raw.get("position",   0)) or 0)
        unrealized = float(raw.get("unrealized_pnl", raw.get("unrealizedPnl", 0)) or 0)
        daily_pnl  = float(raw.get("daily_pnl",       raw.get("dailyPnl",     0)) or 0)
        return {
            "symbol":         raw.get("symbol",  raw.get("ticker",  "")),
            "name":           raw.get("name",    raw.get("companyName", "")),
            "asset_class":    raw.get("asset_class", _classify_asset(raw.get("sec_type", ""))),
            "quantity":       qty,
            "avg_cost":       round(avg_cost, 4),
            "market_price":   round(mkt_price, 4),
            "market_value":   round(mkt_val, 2),
            "daily_pnl":      round(daily_pnl, 2),
            "daily_pnl_pct":  round(daily_pnl / mkt_val * 100, 2) if mkt_val else 0,
            "unrealized_pnl": round(unrealized, 2),
            "weight_pct":     0,
            "currency":       raw.get("currency", "USD"),
            "sector":         raw.get("sector",   "unknown"),
            "theme":          raw.get("theme",    ""),
            "risk_flags":     raw.get("risk_flags", []),
            "broker":         "ibkr",
        }

    # ── Snapshot persistence ───────────────────────────────────────────────────

    def _save_snapshot(self, data: Dict) -> None:
        try:
            import json
            _SNAPSHOT_PATH.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception as exc:
            log.warning("IBKRBridgeClient snapshot save failed: %s", exc)

    def _load_snapshot(self) -> Optional[Dict]:
        try:
            import json
            if _SNAPSHOT_PATH.exists():
                return json.loads(_SNAPSHOT_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
        return None

    # ── HARD BLOCKED trading methods ───────────────────────────────────────────

    def place_order(self, *_, **__):      raise TradingBlockedError("place_order")
    def modify_order(self, *_, **__):     raise TradingBlockedError("modify_order")
    def cancel_order(self, *_, **__):     raise TradingBlockedError("cancel_order")
    def preview_order(self, *_, **__):    raise TradingBlockedError("preview_order")
    def transmit_order(self, *_, **__):   raise TradingBlockedError("transmit_order")
    def execute_trade(self, *_, **__):    raise TradingBlockedError("execute_trade")
    def placeOrder(self, *_, **__):       raise TradingBlockedError("placeOrder")
    def cancelOrder(self, *_, **__):      raise TradingBlockedError("cancelOrder")
    def modifyOrder(self, *_, **__):      raise TradingBlockedError("modifyOrder")
    def reqGlobalCancel(self, *_, **__):  raise TradingBlockedError("reqGlobalCancel")


def _classify_asset(sec_type: str) -> str:
    return {
        "STK": "stock", "OPT": "option", "FUT": "future",
        "CASH": "forex", "BOND": "bond", "FUND": "etf",
        "ETF": "etf", "CRYPTO": "crypto",
    }.get((sec_type or "").upper(), "unknown")


# Singleton — only active when ENABLE_REMOTE_IBKR_BRIDGE=true
ibkr_bridge = IBKRBridgeClient()
