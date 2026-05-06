"""
Hapi Broker API — READ-ONLY connector.

CRITICAL SAFETY RULE:
  HAPI_READ_ONLY=true is enforced at the class level.
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

log = logging.getLogger("jarvis.hapi")

_SNAPSHOT_PATH = Path("data/portfolio/hapi_snapshot.json")


class TradingBlockedError(RuntimeError):
    """Raised when any live trading action is attempted."""
    def __init__(self, method: str = "unknown"):
        super().__init__(
            f"BLOCKED: live trading disabled. Method '{method}' is not permitted. "
            "Paper trading only (HAPI_READ_ONLY=true)."
        )


class HapiReadOnly:
    """
    Read-only wrapper around the Hapi broker REST API.

    All write/order methods are blocked and raise TradingBlockedError.
    """

    def __init__(self) -> None:
        self.api_key    = os.getenv("HAPI_API_KEY", "")
        self.account_id = os.getenv("HAPI_ACCOUNT_ID", "")
        self.base_url   = os.getenv("HAPI_BASE_URL", "").rstrip("/")
        self.timeout    = float(os.getenv("HAPI_TIMEOUT_SECONDS", "10"))
        self.read_only  = os.getenv("HAPI_READ_ONLY", "true").lower() == "true"
        _SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)

    # ── Safety enforcement ────────────────────────────────────────────────────

    def _block(self, method: str) -> None:
        _log_blocked_attempt(method, "hapi")
        raise TradingBlockedError(method)

    # ── Config validation ─────────────────────────────────────────────────────

    def is_configured(self) -> bool:
        return bool(self.api_key and self.base_url)

    # ── HTTP helpers ──────────────────────────────────────────────────────────

    def _get(self, path: str, params: Optional[Dict] = None) -> Dict:
        if not self.is_configured():
            return {"_hapi_error": "not_configured", "message": "HAPI_API_KEY or HAPI_BASE_URL not set"}
        url = f"{self.base_url}{path}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept":        "application/json",
            "X-Read-Only":   "true",
        }
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(url, params=params, headers=headers)
                resp.raise_for_status()
                return resp.json()
        except httpx.ConnectError:
            return {"_hapi_error": "connection_failed", "message": "Hapi API not reachable"}
        except httpx.HTTPStatusError as exc:
            return {"_hapi_error": f"http_{exc.response.status_code}", "message": str(exc)}
        except Exception as exc:
            log.warning("Hapi GET %s failed: %s", path, exc)
            return {"_hapi_error": str(exc)}

    # ── Read-only methods ─────────────────────────────────────────────────────

    def health_check(self) -> Dict:
        if not self.is_configured():
            return {"status": "not_configured", "message": "Set HAPI_API_KEY and HAPI_BASE_URL"}
        result = self._get("/api/v1/health")
        if "_hapi_error" in result:
            return {"status": "disconnected", "error": result.get("message", result["_hapi_error"])}
        return {"status": "connected", "detail": result}

    def get_auth_status(self) -> Dict:
        return self.health_check()

    def get_accounts(self) -> List[Dict]:
        result = self._get("/api/v1/accounts")
        if "_hapi_error" in result:
            return []
        return result.get("accounts", result if isinstance(result, list) else [])

    def get_positions(self, account_id: Optional[str] = None) -> List[Dict]:
        aid = account_id or self.account_id
        path = f"/api/v1/portfolio/{aid}/positions" if aid else "/api/v1/portfolio/positions"
        result = self._get(path)
        if "_hapi_error" in result:
            return []
        raw_positions = result.get("positions", result if isinstance(result, list) else [])
        return [self._normalise_position(p, aid or "") for p in raw_positions]

    def get_portfolio_summary(self, account_id: Optional[str] = None) -> Dict:
        aid = account_id or self.account_id
        path = f"/api/v1/portfolio/{aid}/summary" if aid else "/api/v1/portfolio/summary"
        result = self._get(path)
        if "_hapi_error" in result:
            return {"error": result.get("_hapi_error")}
        return self._normalise_summary(result, aid or "")

    def get_cash_balances(self, account_id: Optional[str] = None) -> Dict:
        aid = account_id or self.account_id
        path = f"/api/v1/portfolio/{aid}/cash" if aid else "/api/v1/portfolio/cash"
        result = self._get(path)
        if "_hapi_error" in result:
            return {"total_cash": 0, "error": result.get("_hapi_error")}
        return {
            "total_cash": round(float(result.get("cash", result.get("cashBalance", 0)) or 0), 2),
            "currency":   result.get("currency", "USD"),
        }

    def get_daily_pnl(self, account_id: Optional[str] = None) -> Dict:
        aid = account_id or self.account_id
        path = f"/api/v1/portfolio/{aid}/pnl" if aid else "/api/v1/portfolio/pnl"
        result = self._get(path)
        if "_hapi_error" in result:
            return {"daily_pnl": 0, "unrealized_pnl": 0, "error": result.get("_hapi_error")}
        return {
            "daily_pnl":      round(float(result.get("dailyPnl", result.get("daily_pnl", 0)) or 0), 2),
            "unrealized_pnl": round(float(result.get("unrealizedPnl", result.get("unrealized_pnl", 0)) or 0), 2),
        }

    def get_market_snapshot(self, symbols: List[str]) -> List[Dict]:
        if not symbols:
            return []
        result = self._get("/api/v1/quotes", params={"symbols": ",".join(symbols)})
        if "_hapi_error" in result:
            return []
        return result.get("quotes", result if isinstance(result, list) else [])

    def get_full_portfolio(self) -> Dict:
        """Fetch everything and return a unified broker snapshot."""
        if not self.is_configured():
            stale = self._load_snapshot()
            if stale:
                stale["_stale"] = True
                stale["_stale_reason"] = "not_configured"
                return stale
            return {
                "broker": "hapi",
                "status": "not_configured",
                "positions": [],
                "summary": {},
                "pnl": {"daily_pnl": 0, "unrealized_pnl": 0},
                "cash": {"total_cash": 0},
                "_stale": False,
            }

        health = self.health_check()
        if health["status"] != "connected":
            stale = self._load_snapshot()
            if stale:
                stale["_stale"] = True
                stale["_stale_reason"] = health.get("status", "disconnected")
                return stale
            return {
                "broker": "hapi",
                "status": "disconnected",
                "positions": [],
                "summary": {},
                "pnl": {"daily_pnl": 0, "unrealized_pnl": 0},
                "cash": {"total_cash": 0},
                "_stale": False,
            }

        positions = self.get_positions()
        summary   = self.get_portfolio_summary()
        pnl       = self.get_daily_pnl()
        cash      = self.get_cash_balances()

        snapshot = {
            "broker":         "hapi",
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
        mkt_val   = float(raw.get("marketValue", raw.get("market_value", 0)) or 0)
        avg_cost  = float(raw.get("avgCost", raw.get("avg_cost", raw.get("averageCost", 0))) or 0)
        mkt_price = float(raw.get("marketPrice", raw.get("lastPrice", raw.get("price", 0))) or 0)
        qty       = float(raw.get("quantity", raw.get("qty", raw.get("shares", 0))) or 0)
        unrealized = float(raw.get("unrealizedPnl", raw.get("unrealized_pnl", 0)) or 0)
        daily_pnl  = float(raw.get("dailyPnl", raw.get("daily_pnl", 0)) or 0)

        return {
            "broker":         "hapi",
            "account_id":     account_id,
            "symbol":         raw.get("symbol", raw.get("ticker", "")),
            "name":           raw.get("name", raw.get("description", "")),
            "asset_class":    _classify_asset(raw.get("assetClass", raw.get("type", ""))),
            "quantity":       qty,
            "avg_cost":       round(avg_cost, 4),
            "market_price":   round(mkt_price, 4),
            "market_value":   round(mkt_val, 2),
            "daily_pnl":      round(daily_pnl, 2),
            "daily_pnl_pct":  round(daily_pnl / mkt_val * 100, 2) if mkt_val else 0,
            "unrealized_pnl": round(unrealized, 2),
            "weight_pct":     0,
            "currency":       raw.get("currency", "USD"),
            "sector":         raw.get("sector", "unknown"),
            "theme":          raw.get("theme", ""),
            "risk_flags":     [],
        }

    def _normalise_summary(self, raw: Dict, account_id: str) -> Dict:
        def _v(key: str) -> float:
            return float(raw.get(key, 0) or 0)
        return {
            "account_id":      account_id,
            "net_liquidation": round(_v("netLiquidationValue") or _v("net_liquidation"), 2),
            "total_cash":      round(_v("cashBalance") or _v("total_cash"), 2),
            "gross_position":  round(_v("grossPositionValue") or _v("gross_position"), 2),
            "unrealized_pnl":  round(_v("unrealizedPnl") or _v("unrealized_pnl"), 2),
            "realized_pnl":    round(_v("realizedPnl") or _v("realized_pnl"), 2),
        }

    # ── Snapshot persistence ──────────────────────────────────────────────────

    def _save_snapshot(self, data: Dict) -> None:
        try:
            _SNAPSHOT_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            log.warning("Hapi snapshot save failed: %s", exc)

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
    def execute_trade(self, *_, **__):      self._block("execute_trade")
    def create_trade(self, *_, **__):       self._block("create_trade")
    def submit_order(self, *_, **__):       self._block("submit_order")


# ── Module-level helpers ──────────────────────────────────────────────────────

def _now() -> str:
    from datetime import datetime
    return datetime.utcnow().isoformat()


def _classify_asset(asset_type: str) -> str:
    t = (asset_type or "").upper()
    if t in ("STK", "STOCK", "EQUITY"):    return "stock"
    if t in ("ETF", "FUND"):               return "etf"
    if t in ("OPT", "OPTION"):             return "option"
    if t in ("FUT", "FUTURE"):             return "future"
    if t in ("CRYPTO", "DIGITAL"):         return "crypto"
    if t in ("CASH", "CURRENCY", "FX"):    return "cash"
    if t in ("BOND", "FI", "FIXED"):       return "bond"
    return "unknown"


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
            "reason": "HAPI_READ_ONLY=true — live trading disabled",
        })
        _GUARDRAIL_LOG.write_text(json.dumps(log_data[-500:], ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
    log.critical("[GUARDRAIL] BLOCKED live trading attempt: broker=%s method=%s", broker, method)


# Singleton
hapi = HapiReadOnly()
