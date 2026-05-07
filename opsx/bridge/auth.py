"""
Bridge Authentication — encrypted token validation.

Token lifecycle:
  1. Check BRIDGE_API_TOKEN env var.
  2. If absent, auto-generate with secrets.token_urlsafe(48) and persist to
     data/bridge/bridge_token.key (chmod 600 on POSIX).
  3. All requests must supply the token via:
       Authorization: Bearer <token>
     OR
       X-Bridge-Token: <token>
  4. Comparison uses hmac.compare_digest (constant-time, immune to timing attacks).
  5. Rate limiter: max BRIDGE_RATE_LIMIT req/min per IP (default 60).

This module has NO knowledge of IBKR — it only validates callers.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets
import stat
import time
from collections import defaultdict
from pathlib import Path
from threading import Lock
from typing import Dict, Optional, Tuple

from fastapi import Header, HTTPException, Request, status

log = logging.getLogger("jarvis.bridge.auth")

_TOKEN_FILE  = Path("data/bridge/bridge_token.key")
_RATE_LIMIT  = int(os.getenv("BRIDGE_RATE_LIMIT", "60"))   # requests per minute
_WINDOW_SEC  = 60

# ── Token management ──────────────────────────────────────────────────────────

class TokenStore:
    """Thread-safe token store with auto-generation."""

    def __init__(self) -> None:
        self._token: Optional[str] = None
        self._lock = Lock()

    def get_token(self) -> str:
        with self._lock:
            if self._token:
                return self._token
            self._token = self._load_or_generate()
            return self._token

    def _load_or_generate(self) -> str:
        # 1. Environment variable takes precedence
        env_token = os.getenv("BRIDGE_API_TOKEN", "").strip()
        if env_token:
            log.info("Bridge token loaded from BRIDGE_API_TOKEN env var")
            return env_token

        # 2. Persisted token file
        if _TOKEN_FILE.exists():
            try:
                token = _TOKEN_FILE.read_text(encoding="utf-8").strip()
                if len(token) >= 32:
                    log.info("Bridge token loaded from %s", _TOKEN_FILE)
                    return token
            except Exception as exc:
                log.warning("Token file read failed: %s", exc)

        # 3. Generate new token
        token = secrets.token_urlsafe(48)
        try:
            _TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
            _TOKEN_FILE.write_text(token, encoding="utf-8")
            # Restrict to owner-only on POSIX
            try:
                _TOKEN_FILE.chmod(stat.S_IRUSR | stat.S_IWUSR)
            except Exception:
                pass
            log.info(
                "Bridge token GENERATED and saved to %s — copy this token for Railway env vars",
                _TOKEN_FILE,
            )
            print(f"\n{'='*60}")
            print(f"  BRIDGE TOKEN GENERATED")
            print(f"  Set in Railway: BRIDGE_API_TOKEN={token[:12]}...")
            print(f"  Full token in: {_TOKEN_FILE}")
            print(f"{'='*60}\n")
        except Exception as exc:
            log.error("Token file write failed: %s", exc)
        return token

    def rotate_token(self) -> str:
        """Generate a new token, invalidating the old one."""
        with self._lock:
            new_token = secrets.token_urlsafe(48)
            try:
                _TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
                _TOKEN_FILE.write_text(new_token, encoding="utf-8")
            except Exception as exc:
                log.error("Token rotation write failed: %s", exc)
            self._token = new_token
            log.warning("Bridge token rotated")
            return new_token


_token_store = TokenStore()


def get_bridge_token() -> str:
    return _token_store.get_token()


def verify_token_value(provided: str) -> bool:
    """Constant-time token comparison."""
    expected = _token_store.get_token()
    # Hash both sides to equalise length before compare_digest
    h_provided = hashlib.sha256(provided.encode()).hexdigest()
    h_expected  = hashlib.sha256(expected.encode()).hexdigest()
    return hmac.compare_digest(h_provided, h_expected)


# ── Rate limiter ──────────────────────────────────────────────────────────────

class RateLimiter:
    """
    Sliding-window rate limiter (thread-safe, in-memory).
    Stores timestamps of recent requests per IP.
    """

    def __init__(self, max_requests: int = _RATE_LIMIT, window: int = _WINDOW_SEC) -> None:
        self._max    = max_requests
        self._window = window
        self._store: Dict[str, list] = defaultdict(list)
        self._lock   = Lock()

    def is_allowed(self, ip: str) -> Tuple[bool, int]:
        """
        Returns (allowed, remaining_requests).
        Cleans up expired timestamps on each call.
        """
        now = time.monotonic()
        cutoff = now - self._window

        with self._lock:
            timestamps = self._store[ip]
            # Remove requests outside the window
            timestamps[:] = [t for t in timestamps if t > cutoff]

            if len(timestamps) >= self._max:
                return False, 0

            timestamps.append(now)
            return True, self._max - len(timestamps)


_rate_limiter = RateLimiter()


# ── FastAPI dependency ─────────────────────────────────────────────────────────

async def verify_token(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    x_bridge_token: Optional[str] = Header(default=None, alias="X-Bridge-Token"),
) -> str:
    """
    FastAPI dependency — validates Bearer token + rate limit.
    Raises 401 / 429 on failure; returns the validated token on success.
    """
    # Rate limit check
    client_ip = (
        request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        or (request.client.host if request.client else "unknown")
    )
    allowed, remaining = _rate_limiter.is_allowed(client_ip)
    if not allowed:
        log.warning("Rate limit exceeded from %s", client_ip)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded — max 60 requests/minute",
            headers={"Retry-After": "60"},
        )

    # Extract token
    token: Optional[str] = None
    if authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]
    if not token and x_bridge_token:
        token = x_bridge_token

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token — supply Authorization: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not verify_token_value(token):
        log.warning("Invalid bridge token from %s", client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return token
