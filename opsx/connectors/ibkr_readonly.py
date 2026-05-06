"""
IBKR Client Portal Web API — READ-ONLY connector.

Connects to a locally running IBKR Client Portal Gateway.
Gateway default: https://localhost:5000

CRITICAL SAFETY RULE:
  IBKR_READ_ONLY=true is enforced at the class level.
  No order, trade, or mutation method is implemented.
  Any attempt to call blocked methods raises TradingBlockedError.
"""
from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

log = logging.getLogger("jarvis.ibkr")

_SNAPSHOT_PATH = Path("data/portfolio/ibkr_snapshot.json")


class TradingBlockedError(RuntimeError):
    """Raised when any live trading action is attempted."""
    def __init__(self, method: str = "unknown"):
        super().__init__(
            f"BLOCKED: live trading disabled. Method '{method}' is not permitted. "
            "Paper trading only (IBKR_READ_ONLY=true)."
        )


class IBKRReadOnly:
    """
    Read-only wrapper around the IBKR Client Portal Web API.

    All write/order methods are explicitly blocked and raise TradingBlockedError.
    """

    def __init__(self) -> None:
        self.gateway_url = os.getenv("IBKR_GATEWAY_URL", "https://localhost:5000").rstrip("/")
        self.account_id  = os.getenv("IBKR_ACCOUNT_ID", "")
        self.timeout     = float(os.getenv("IBKR_TIMEOUT_SECONDS", "10"))
        self.read_only   = os.getenv("IBKR_READ_ONLY", "true").lower() == "true"
        _SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)

    # ── Safety enforcement ────────────────────────────────────────────────────

    def _block(self, method: str) -> None:
        _log_blocked_attempt(method, "ibkr")
        raise TradingBlockedError(method)

    # ── HTTP helpers ──────────────────────────────────────────────────────────

    def _get(self, path: str, params: Optional[Dict] = None) -> Dict:
        url = f"{self.gateway_url}{path}"
        try:
            with httpx.Client(verify=False, timeout=self.timeout) as client:
                resp = client.get(url, params=params)
                resp.raise_for_status()
                return resp.json()
        except httpx.ConnectError:
            return {"_ibkr_error": "gateway_offline", "message": "IBKR gateway not reachable"}
        except Exception as exc:
            log.warning("IBKR GET %s failed: %s", path, exc)
            return {"_ibkr_error": str(exc)}

    # ── Read-only methods ─────────────────────────────────────────────────────

    def health_check(self) -> Dict:
        """Returns True if the gateway is reachable."""
        result = self._get("/v1/api/iserver/auth/status")
        if "_ibkr_error" in result:
            return {"status": "disconnected", "error": result.get("message", result["_ibkr_error"])}
        authenticated = result.get("authenticated", False)
        return {
            "status":        "connected" if authenticated else "unauthenticated",
            "authenticated": authenticated,
            "competing":     result.get("competing", False),
            "message":       result.get("message", ""),
        }

    def get_auth_status(self) -> Dict:
        return self.health_check()

    def get_accounts(self) -> List[str]:
        result = self._get("/v1/api/iserver/accounts")
        if "_ibkr_error" in result:
            return []
        return result.get("accounts", [])

    def get_account_summary(self, account_id: Optional[str] = None) -> Dict:
        aid = account_id or self.account_id
        if not aid:
            accounts = self.get_accounts()
            aid = accounts[0] if accounts else ""
        if not aid:
            return {"_ibkr_error": "no_account_id"}
        result = self._get(f"/v1/api/portfolio/{aid}/summary")
        if "_ibkr_error" in result:
            return result
        return self._normalise_summary(result, aid)

    def get_positions(self, account_id: Optional[str] = None) -> List[Dict]:
        aid = account_id or self.account_id
        if not aid:
            accounts = self.get_accounts()
            aid = accounts[0] if accounts else ""
        if not aid:
            return []
        result = self._get(f"/v1/api/portfolio/{aid}/positions/0")
        if isinstance(result, list):
            return [self._normalise_position(p, aid) for p in result]
        return []

    def get_pnl(self, account_id: Optional[str] = None) -> Dict:
        result = self._get("/v1/api/iserver/account/pnl/partitioned")
        if "_ibkr_error" in result:
            return {"daily_pnl": 0, "unrealized_pnl": 0, "error": result.get("_ibkr_error")}
        upnl = result.get("upnl", {})
        total_daily    = sum(v.get("dpl", 0) for v in upnl.values() if isinstance(v, dict))
        total_unrealized = sum(v.get("upl", 0) for v in upnl.values() if isinstance(v, dict))
        return {"daily_pnl": round(total_daily, 2), "unrealized_pnl": round(total_unrealized, 2)}

    def get_cash_balances(self, account_id: Optional[str] = None) -> Dict:
        aid = account_id or self.account_id
        if not aid:
            accounts = self.get_accounts()
            aid = accounts[0] if accounts else ""
        if not aid:
            return {"total_cash": 0}
        result = self._get(f"/v1/api/portfolio/{aid}/ledger")
        if "_ibkr_error" in result:
            return {"total_cash": 0, "error": result.get("_ibkr_error")}
        base = result.get("BASE", {})
        return {
            "total_cash":       round(base.get("cashbalance", 0), 2),
            "net_liquidation":  round(base.get("netliquidationvalue", 0), 2),
            "currency":         "USD",
        }

    def get_market_snapshot(self, conids: List[str]) -> List[Dict]:
        if not conids:
            return []
        conid_str = ",".join(str(c) for c in conids)
        result = self._get("/v1/api/md/snapshot", params={"conids": conid_str, "fields": "31,83,84,85,86,88"})
        if isinstance(result, list):
            return result
        return []

    def get_full_portfolio(self) -> Dict:
        """Fetch everything and return a unified broker snapshot."""
        auth = self.health_check()
        if auth["status"] not in ("connected",):
            stale = self._load_snapshot()
            if stale:
                stale["_stale"] = True
                stale["_stale_reason"] = auth.get("status", "disconnected")
                return stale
            return {
                "broker": "ibkr",
                "status": "disconnected",
                "positions": [],
                "summary": {},
                "pnl": {"daily_pnl": 0, "unrealized_pnl": 0},
                "cash": {"total_cash": 0},
                "_stale": False,
            }

        summary   = self.get_account_summary()
        positions = self.get_positions()
        pnl       = self.get_pnl()
        cash      = self.get_cash_balances()

        snapshot = {
            "broker":         "ibkr",
            "status":         "connected",
            "account_id":     self.account_id,
            "positions":      positions,
            "summary":        summary,
            "pnl":            pnl,
            "cash":           cash,
            "position_count": len(positions),
            "fetched_at":     _now(),
            "_stale":         False,
        }
        self._save_snapshot(snapshot)
        return snapshot

    # ── Normalisers ───────────────────────────────────────────────────────────

    def _normalise_position(self, raw: Dict, account_id: str) -> Dict:
        mkt_val  = float(raw.get("mktValue", raw.get("marketValue", 0)) or 0)
        avg_cost = float(raw.get("avgCost", raw.get("avgPrice", 0)) or 0)
        mkt_price = float(raw.get("mktPrice", raw.get("lastPrice", 0)) or 0)
        qty      = float(raw.get("position", 0) or 0)
        unrealized = float(raw.get("unrealizedPnl", 0) or 0)
        daily_pnl  = float(raw.get("dailyPnl", 0) or 0)

        return {
            "broker":         "ibkr",
            "account_id":     account_id,
            "symbol":         raw.get("ticker", raw.get("symbol", "")),
            "name":           raw.get("companyName", raw.get("name", "")),
            "asset_class":    _classify_asset(raw.get("assetClass", raw.get("secType", ""))),
            "quantity":       qty,
            "avg_cost":       round(avg_cost, 4),
            "market_price":   round(mkt_price, 4),
            "market_value":   round(mkt_val, 2),
            "daily_pnl":      round(daily_pnl, 2),
            "daily_pnl_pct":  round(daily_pnl / mkt_val * 100, 2) if mkt_val else 0,
            "unrealized_pnl": round(unrealized, 2),
            "weight_pct":     0,  # filled by unified engine
            "currency":       raw.get("currency", "USD"),
            "sector":         raw.get("sector", "unknown"),
            "theme":          "",
            "risk_flags":     [],
        }

    def _normalise_summary(self, raw: Dict, account_id: str) -> Dict:
        def _val(key: str) -> float:
            item = raw.get(key, {})
            return float(item.get("amount", item) if isinstance(item, dict) else item or 0)
        return {
            "account_id":       account_id,
            "net_liquidation":  round(_val("netliquidationvalue"), 2),
            "total_cash":       round(_val("totalcashvalue"), 2),
            "gross_position":   round(_val("grosspositionvalue"), 2),
            "buying_power":     round(_val("buyingpower"), 2),
            "unrealized_pnl":   round(_val("unrealizedpnl"), 2),
            "realized_pnl":     round(_val("realizedpnl"), 2),
        }

    # ── Snapshot persistence ──────────────────────────────────────────────────

    def _save_snapshot(self, data: Dict) -> None:
        try:
            _SNAPSHOT_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            log.warning("IBKR snapshot save failed: %s", exc)

    def _load_snapshot(self) -> Optional[Dict]:
        try:
            if _SNAPSHOT_PATH.exists():
                return json.loads(_SNAPSHOT_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
        return None

    # ── Blocked trading methods ───────────────────────────────────────────────

    def place_order(self, *_, **__):        self._block("place_order")
    def modify_order(self, *_, **__):       self._block("modify_order")
    def cancel_order(self, *_, **__):       self._block("cancel_order")
    def preview_order(self, *_, **__):      self._block("preview_order")
    def transmit_order(self, *_, **__):     self._block("transmit_order")
    def execute_trade(self, *_, **__):      self._block("execute_trade")
    def create_trade(self, *_, **__):       self._block("create_trade")
    def order_reply(self, *_, **__):        self._block("order_reply")
    def submit_order(self, *_, **__):       self._block("submit_order")


# ── Module-level helpers ──────────────────────────────────────────────────────

def _now() -> str:
    from datetime import datetime
    return datetime.utcnow().isoformat()


def _classify_asset(sec_type: str) -> str:
    mapping = {
        "STK": "stock", "OPT": "option", "FUT": "future",
        "CASH": "cash", "BOND": "bond", "FUND": "etf",
        "ETF": "etf", "CRYPTO": "crypto",
    }
    return mapping.get((sec_type or "").upper(), "unknown")


_GUARDRAIL_LOG = Path("data/portfolio/trading_guardrail_log.json")

def _log_blocked_attempt(method: str, broker: str) -> None:
    _GUARDRAIL_LOG.parent.mkdir(parents=True, exist_ok=True)
    try:
        log_data = []
        if _GUARDRAIL_LOG.exists():
            log_data = json.loads(_GUARDRAIL_LOG.read_text(encoding="utf-8"))
        log_data.append({
            "timestamp": _now(),
            "broker": broker,
            "method": method,
            "blocked": True,
            "reason": "IBKR_READ_ONLY=true — live trading disabled",
        })
        _GUARDRAIL_LOG.write_text(json.dumps(log_data[-500:], ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
    log.critical("[GUARDRAIL] BLOCKED live trading attempt: broker=%s method=%s", broker, method)


# Singleton
ibkr = IBKRReadOnly()
