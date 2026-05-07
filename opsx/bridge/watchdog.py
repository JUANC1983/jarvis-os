"""
JARVIS Bridge Reconnect Watchdog.

Monitors the secure bridge health from the Railway side:
  - Detects stale snapshots (no fresh data > stale_threshold_secs)
  - Exposes /api/bridge/watchdog for dashboard status display
  - Provides heartbeat verification
  - Triggers automatic retry on stale detection
  - Graceful degradation: returns last known state when bridge unreachable

Architecture:
  Railway FastAPI background task → polls /api/debug/ibkr
  State cached in _watchdog_state dict (in-process, no external DB)

Safety:
  - Read-only: never calls bridge execution endpoints
  - real_trade: False in all outputs
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from datetime import datetime
from typing import Dict, Optional

import httpx

log = logging.getLogger("jarvis.watchdog")

_STALE_THRESHOLD_SECS      = int(os.getenv("WATCHDOG_STALE_THRESHOLD",    "120"))
_POLL_INTERVAL_SECS        = int(os.getenv("WATCHDOG_POLL_INTERVAL",       "60"))
_HEARTBEAT_TIMEOUT         = int(os.getenv("WATCHDOG_HEARTBEAT_TIMEOUT",    "8"))
_MAX_BACKOFF_SECS          = int(os.getenv("WATCHDOG_MAX_BACKOFF",          "120"))
_CIRCUIT_BREAKER_THRESHOLD = int(os.getenv("WATCHDOG_CIRCUIT_THRESHOLD",    "5"))
_CIRCUIT_RESET_SECS        = int(os.getenv("WATCHDOG_CIRCUIT_RESET",        "300"))

_watchdog_state: Dict = {
    "running":              False,
    "bridge_reachable":     False,
    "ibkr_connected":       False,
    "account_mode":         "UNKNOWN",
    "last_checked_at":      None,
    "last_healthy_at":      None,
    "stale_detected":       False,
    "cache_age_seconds":    None,
    "consecutive_failures": 0,
    "check_count":          0,
    "circuit_open":         False,
    "circuit_open_since":   None,
    "current_backoff_secs": _POLL_INTERVAL_SECS,
    "next_check_in_secs":   _POLL_INTERVAL_SECS,
    "real_trade":           False,
}


def get_watchdog_state() -> Dict:
    """Return current watchdog state (safe to call from any thread/coroutine)."""
    return {**_watchdog_state}


async def watchdog_loop(bridge_url: str, bridge_token: str) -> None:
    """
    Async loop that runs as a FastAPI background task.
    Polls the bridge /health endpoint and updates _watchdog_state.

    Backoff strategy:
      - Healthy: poll at _POLL_INTERVAL_SECS (default 60s)
      - 1 failure: 1s backoff
      - N failures: min(2^(N-1), _MAX_BACKOFF_SECS) exponential backoff
      - >= _CIRCUIT_BREAKER_THRESHOLD failures: circuit open, _MAX_BACKOFF_SECS wait
      - After _CIRCUIT_RESET_SECS with open circuit: attempt half-open reset
    """
    global _watchdog_state
    _watchdog_state["running"] = True
    log.info(
        "Watchdog started — bridge=%s  poll=%ds  stale_threshold=%ds  "
        "circuit_threshold=%d  max_backoff=%ds",
        bridge_url, _POLL_INTERVAL_SECS, _STALE_THRESHOLD_SECS,
        _CIRCUIT_BREAKER_THRESHOLD, _MAX_BACKOFF_SECS,
    )

    _circuit_open_since: Optional[float] = None

    while True:
        await _check_bridge(bridge_url, bridge_token)
        failures = _watchdog_state["consecutive_failures"]

        if failures == 0:
            # Healthy — normal cadence, reset circuit
            _circuit_open_since = None
            _watchdog_state["circuit_open"]         = False
            _watchdog_state["circuit_open_since"]   = None
            backoff = float(_POLL_INTERVAL_SECS)

        elif failures >= _CIRCUIT_BREAKER_THRESHOLD:
            # Circuit breaker logic
            if _circuit_open_since is None:
                _circuit_open_since = time.monotonic()
                _watchdog_state["circuit_open_since"] = datetime.utcnow().isoformat()
                log.error(
                    "Watchdog: circuit breaker OPEN after %d consecutive failures — "
                    "will retry in %ds, attempting reset after %ds",
                    failures, _MAX_BACKOFF_SECS, _CIRCUIT_RESET_SECS,
                )
            _watchdog_state["circuit_open"] = True

            elapsed = time.monotonic() - _circuit_open_since
            if elapsed >= _CIRCUIT_RESET_SECS:
                # Half-open: try a quick reset
                log.info(
                    "Watchdog: circuit half-open reset attempt after %ds", int(elapsed)
                )
                _circuit_open_since = None
                backoff = 1.0
            else:
                backoff = float(_MAX_BACKOFF_SECS)

        else:
            # Exponential backoff: 1s → 2s → 4s → 8s → 16s → cap at _MAX_BACKOFF_SECS
            _circuit_open_since = None
            _watchdog_state["circuit_open"] = False
            _watchdog_state["circuit_open_since"] = None
            backoff = min(float(2 ** (failures - 1)), float(_MAX_BACKOFF_SECS))
            log.warning(
                "Watchdog: failure %d — exponential backoff, next check in %ds",
                failures, int(backoff),
            )

        _watchdog_state["current_backoff_secs"] = int(backoff)
        _watchdog_state["next_check_in_secs"]   = int(backoff)
        await asyncio.sleep(backoff)


async def _check_bridge(bridge_url: str, bridge_token: str) -> None:
    global _watchdog_state
    now = datetime.utcnow().isoformat()
    _watchdog_state["check_count"] += 1
    _watchdog_state["last_checked_at"] = now

    try:
        url = f"{bridge_url.rstrip('/')}/health"
        async with httpx.AsyncClient(timeout=_HEARTBEAT_TIMEOUT) as client:
            resp = await client.get(url, headers={"Authorization": f"Bearer {bridge_token}"})

        if resp.status_code == 401:
            log.warning("Watchdog: bridge auth failed (401)")
            _watchdog_state.update({
                "bridge_reachable": True,
                "ibkr_connected":   False,
                "consecutive_failures": _watchdog_state["consecutive_failures"] + 1,
            })
            return

        data = resp.json()
        ibkr = data.get("ibkr", {})
        connected    = ibkr.get("connected", False)
        account      = ibkr.get("account",   "")
        account_mode = "PAPER" if account.startswith("DU") else ("LIVE" if account else "UNKNOWN")
        cache_age    = data.get("cache", {}).get("cache_age_seconds", None)
        stale        = bool(cache_age and cache_age > _STALE_THRESHOLD_SECS)

        _watchdog_state.update({
            "bridge_reachable":     True,
            "ibkr_connected":       connected,
            "account":              account,
            "account_mode":         account_mode,
            "stale_detected":       stale,
            "cache_age_seconds":    cache_age,
            "consecutive_failures": 0,
            "last_healthy_at":      now if connected else _watchdog_state.get("last_healthy_at"),
        })

        if stale:
            log.warning("Watchdog: snapshot stale — age=%ss (threshold=%ss)",
                        cache_age, _STALE_THRESHOLD_SECS)
        elif connected:
            log.debug("Watchdog: bridge healthy — account=%s mode=%s", account, account_mode)

    except httpx.ConnectError:
        log.warning("Watchdog: bridge unreachable at %s", bridge_url)
        _watchdog_state.update({
            "bridge_reachable":     False,
            "ibkr_connected":       False,
            "consecutive_failures": _watchdog_state["consecutive_failures"] + 1,
        })
    except Exception as exc:
        log.error("Watchdog check failed: %s", exc)
        _watchdog_state["consecutive_failures"] += 1


def is_bridge_healthy() -> bool:
    """Quick boolean: bridge reachable and IBKR connected and snapshot fresh."""
    s = _watchdog_state
    return (
        s["bridge_reachable"]
        and s["ibkr_connected"]
        and not s["stale_detected"]
    )


def get_stale_warning() -> Optional[str]:
    """Return a human-readable stale warning string, or None if healthy."""
    s = _watchdog_state
    if not s["bridge_reachable"]:
        failures = s["consecutive_failures"]
        return f"Bridge unreachable ({failures} consecutive failures)"
    if not s["ibkr_connected"]:
        return "Bridge reachable but IBKR not connected"
    if s["stale_detected"]:
        age = s.get("cache_age_seconds", "?")
        return f"Snapshot stale — {age}s since last update"
    return None
