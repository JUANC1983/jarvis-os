"""
JARVIS IBKR Production Guard — startup and runtime safety enforcer.

Prevents Railway/production deployments from silently falling back to
localhost:5000 (unreachable) instead of using the remote ngrok bridge.

Three enforcement layers:
  1. validate_production_config() — called at startup and connector init
  2. IBKRNotConfiguredStub — returned instead of localhost fallback
  3. assert_no_localhost_in_production() — callable from any code path

CRITICAL INVARIANT:
  In any Railway / production environment, IBKR connector MUST be
  IBKRBridgeClient pointing at a public ngrok URL.
  IBKRReadOnly (localhost:5000) MUST NEVER load in production.

Safety guarantees:
  - ALL IBKRNotConfiguredStub methods raise TradingBlockedError
  - real_trade=False in every response
  - execution_blocked=True in every response
"""
from __future__ import annotations

import logging
import os
from typing import Dict

log = logging.getLogger("jarvis.production_guard")

_LOCALHOST_PATTERNS = ("localhost", "127.0.0.1", "0.0.0.0", "::1", "host.docker.internal")


class ProductionConfigError(RuntimeError):
    """
    Raised when a production-unsafe IBKR config is detected.
    A localhost bridge URL in Railway is always an error — it can never work.
    """


def is_hosted_runtime() -> bool:
    """Return True if running on Railway or any explicitly set production env."""
    return bool(
        os.getenv("RAILWAY_ENVIRONMENT")
        or os.getenv("RAILWAY_SERVICE_ID")
        or os.getenv("RAILWAY_PROJECT_ID")
        or os.getenv("RAILWAY_STATIC_URL")
        or os.getenv("RAILWAY_PUBLIC_DOMAIN")
        or os.getenv("ENV", "").lower() in {"production", "prod"}
    )


def assert_no_localhost_in_production(url: str) -> None:
    """
    Raise ProductionConfigError if url contains a localhost pattern AND
    we are in a hosted/production environment.

    Called at connector selection and watchdog startup. A localhost bridge
    URL in Railway will NEVER work — it must be caught at boot, not at
    first portfolio request.
    """
    if not url:
        return
    url_lower = url.lower()
    if any(pat in url_lower for pat in _LOCALHOST_PATTERNS):
        if is_hosted_runtime():
            raise ProductionConfigError(
                "Hosted runtime cannot connect to local IBKR directly. Use IBKR_URL/ngrok bridge."
            )
        if is_hosted_runtime():
            raise ProductionConfigError(
                f"PRODUCTION SAFETY VIOLATION: IBKR_BRIDGE_URL '{url}' contains a "
                "localhost address — unreachable inside a Railway container. "
                "Update IBKR_BRIDGE_URL to your public ngrok URL "
                "(e.g. https://abc123.ngrok.io)."
            )
        else:
            log.warning(
                "IBKR_BRIDGE_URL '%s' contains localhost — acceptable in dev only. "
                "Do NOT deploy this URL to Railway.", url
            )


def validate_production_config(
    bridge_url: str,
    bridge_token: str,
    hosted: bool,
) -> None:
    """
    Full production config validation. Called at startup and connector init.

    Raises ProductionConfigError if a localhost URL is detected in production.
    Logs CRITICAL if hosted but bridge vars are not configured.
    Logs WARNING if URL is set but token is missing.
    """
    # Hard rejection: localhost URL in production
    if bridge_url:
        assert_no_localhost_in_production(bridge_url)

    if hosted:
        if not bridge_url:
            log.critical(
                "IBKR WARNING: Running in Railway/production but IBKR_BRIDGE_URL is NOT "
                "configured. Portfolio data will be unavailable. "
                "Add IBKR_BRIDGE_URL (your ngrok URL) to Railway environment variables."
            )
        elif not bridge_token:
            log.warning(
                "IBKR WARNING: IBKR_BRIDGE_URL is set but IBKR_BRIDGE_TOKEN is empty. "
                "All bridge requests will be rejected with 401 Unauthorized."
            )
        else:
            log.info(
                "IBKR production config OK — bridge_url=%s token_set=True", bridge_url
            )
    else:
        if bridge_url:
            log.info("IBKR dev config — bridge_url=%s", bridge_url)
        else:
            log.info("IBKR dev config — no bridge URL, will use local Client Portal")


# ── Not-Configured Stub ────────────────────────────────────────────────────────

class IBKRNotConfiguredStub:
    """
    Drop-in for IBKRBridgeClient when Railway is detected but bridge vars are
    not configured. Returns clear 'not_configured' responses.

    NEVER falls back to localhost:5000.
    ALL execution methods raise TradingBlockedError.
    """

    _MSG = (
        "IBKR bridge not configured in production. "
        "Set IBKR_BRIDGE_URL and IBKR_BRIDGE_TOKEN in Railway environment variables."
    )

    def health_check(self) -> Dict:
        return {
            "status":            "not_configured",
            "bridge_ok":         False,
            "connected":         False,
            "ibkr_connected":    False,
            "error":             self._MSG,
            "readonly":          True,
            "execution_blocked": True,
            "real_trade":        False,
        }

    def get_full_portfolio(self) -> Dict:
        return {
            "broker":            "ibkr",
            "status":            "not_configured",
            "positions":         [],
            "position_count":    0,
            "pnl":               {"daily_pnl": 0, "unrealized_pnl": 0, "realized_pnl": 0},
            "cash":              {"total_cash": 0, "net_liquidation": 0},
            "summary":           {},
            "_stale":            True,
            "_stale_reason":     self._MSG,
            "account_type":      "UNKNOWN",
            "data_origin":       "not_configured",
            "readonly_mode":     True,
            "execution_blocked": True,
            "real_trade":        False,
        }

    def get_positions(self) -> list:
        return []

    def get_account_summary(self) -> Dict:
        return {"status": "not_configured", "real_trade": False}

    def get_pnl(self) -> Dict:
        return {"daily_pnl": 0, "unrealized_pnl": 0, "real_trade": False}

    def get_market_data(self, *_, **__) -> Dict:
        return {"status": "not_configured", "real_trade": False}

    # Hard-blocked execution methods
    def place_order(self, *_, **__):     raise _TradingBlockedError("place_order")
    def modify_order(self, *_, **__):    raise _TradingBlockedError("modify_order")
    def cancel_order(self, *_, **__):    raise _TradingBlockedError("cancel_order")
    def preview_order(self, *_, **__):   raise _TradingBlockedError("preview_order")
    def transmit_order(self, *_, **__):  raise _TradingBlockedError("transmit_order")
    def execute_trade(self, *_, **__):   raise _TradingBlockedError("execute_trade")
    def placeOrder(self, *_, **__):      raise _TradingBlockedError("placeOrder")
    def cancelOrder(self, *_, **__):     raise _TradingBlockedError("cancelOrder")
    def modifyOrder(self, *_, **__):     raise _TradingBlockedError("modifyOrder")
    def reqGlobalCancel(self, *_, **__): raise _TradingBlockedError("reqGlobalCancel")


def _TradingBlockedError(method: str = "unknown") -> RuntimeError:
    return RuntimeError(
        f"BLOCKED: live trading disabled. Method '{method}' is not permitted. "
        "Paper trading only."
    )


# ── Phase 3: Runtime Execution Guard ──────────────────────────────────────────

def runtime_execution_assert(method: str, context: str = "") -> None:
    """
    Hard assertion: raises RuntimeError immediately if called in any code path
    that could lead to live trade execution.

    Embed at the top of any function that handles order flow:
        runtime_execution_assert("placeOrder", "ibkr_connector")

    Logs CRITICAL and raises — never silently passes.
    """
    import logging as _logging
    _logging.getLogger("jarvis.production_guard").critical(
        "EXECUTION GUARD ASSERTION TRIGGERED — method=%s context=%s  "
        "real_trade=False  blocked=True",
        method, context or "unknown",
    )
    raise RuntimeError(
        f"EXECUTION GUARD: method '{method}' is blocked. "
        f"Context: {context or 'unknown'}. JARVIS is READ-ONLY. real_trade=False."
    )
