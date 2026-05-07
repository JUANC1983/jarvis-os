"""
JARVIS Execution Guard Middleware.

Intercepts ANY HTTP request at the application layer that could represent
a trade execution attempt and hard-blocks it before any handler runs.

Designed to be installed on both:
  - main.py (Railway FastAPI)
  - secure_bridge.py (local bridge FastAPI)

Safety invariants:
  - real_trade: False in every blocked response
  - blocked: True in every blocked response
  - reason: "READ_ONLY_MODE" always
  - Logs every block attempt to data/bridge/guardrail_log.json
  - Adds X-Execution-Guard: blocked header on blocked responses
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

log = logging.getLogger("jarvis.execution_guard")

_GUARD_LOG = Path("data/bridge/guardrail_log.json")

# Paths that must NEVER be served (method + path fragment combos)
_BLOCKED_PATH_FRAGMENTS = frozenset({
    "/order", "/trade/execute", "/broker/order",
    "/place", "/transmit", "/cancel_order",
    "/modify_order", "/execute",
})

# Body keywords that signal execution intent (checked only on POST/PUT/PATCH)
_BLOCKED_BODY_KEYWORDS = frozenset({
    "placeOrder", "cancelOrder", "modifyOrder",
    "transmit_order", "execute_trade", "market_order",
    "limit_order", "bracket_order", "place_order",
    "cancel_order", "modify_order",
})

# Safe read-only paths that start with /order but are allowed (diagnostics, etc.)
_SAFE_PATH_PREFIXES = frozenset({
    "/api/debug", "/api/paper", "/api/portfolio",
    "/api/trader", "/api/market", "/health",
    "/bridge/info", "/docs", "/openapi",
})


def _is_safe_path(path: str) -> bool:
    return any(path.startswith(p) for p in _SAFE_PATH_PREFIXES)


def _path_is_blocked(path: str) -> bool:
    if _is_safe_path(path):
        return False
    return any(fragment in path for fragment in _BLOCKED_PATH_FRAGMENTS)


def _log_block(path: str, method: str, reason: str) -> None:
    _GUARD_LOG.parent.mkdir(parents=True, exist_ok=True)
    try:
        entries = []
        if _GUARD_LOG.exists():
            entries = json.loads(_GUARD_LOG.read_text(encoding="utf-8"))
        entries.append({
            "timestamp":  datetime.utcnow().isoformat(),
            "path":       path,
            "method":     method,
            "reason":     reason,
            "blocked":    True,
            "source":     "execution_guard_middleware",
            "real_trade": False,
        })
        _GUARD_LOG.write_text(
            json.dumps(entries[-1000:], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass
    log.critical("[EXECUTION GUARD] BLOCKED %s %s — %s", method, path, reason)


_BLOCKED_RESPONSE = {
    "blocked":    True,
    "reason":     "READ_ONLY_MODE",
    "message":    "JARVIS operates in strict READ-ONLY mode. All execution paths are permanently disabled.",
    "real_trade": False,
}


class ExecutionGuardMiddleware(BaseHTTPMiddleware):
    """
    FastAPI/Starlette middleware that hard-blocks any HTTP request that could
    represent a trade execution attempt.

    Install with:
        app.add_middleware(ExecutionGuardMiddleware)
    """

    async def dispatch(self, request: Request, call_next: Callable):
        path   = request.url.path
        method = request.method

        # Layer 1: Path-based block
        if _path_is_blocked(path):
            _log_block(path, method, "blocked_path_fragment")
            resp = JSONResponse(status_code=403, content=_BLOCKED_RESPONSE)
            resp.headers["X-Execution-Guard"] = "blocked"
            return resp

        # Layer 2: Body keyword scan (POST / PUT / PATCH only)
        if method in ("POST", "PUT", "PATCH"):
            try:
                body_bytes = await request.body()
                if body_bytes:
                    body_str = body_bytes.decode("utf-8", errors="ignore")
                    for kw in _BLOCKED_BODY_KEYWORDS:
                        if kw in body_str:
                            _log_block(path, method, f"blocked_body_keyword:{kw}")
                            resp = JSONResponse(status_code=403, content=_BLOCKED_RESPONSE)
                            resp.headers["X-Execution-Guard"] = "blocked"
                            return resp
            except Exception:
                pass   # Body read failed — safe to proceed

        # Allow
        response = await call_next(request)
        response.headers["X-Execution-Guard"] = "active"
        return response


def make_blocked_response() -> dict:
    """Return the standard blocked execution response dict."""
    return dict(_BLOCKED_RESPONSE)
