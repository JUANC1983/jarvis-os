"""
Microsoft Identity Platform OAuth2 authentication.
Manages token acquisition, storage, and transparent refresh.
Structured for in-memory-now / DB-later swap.
"""
from __future__ import annotations

import logging
import os
import secrets
import time
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlencode

import httpx

log = logging.getLogger("jarvis.outlook_auth")

# ── Config from environment ───────────────────────────────────────────────────

_CLIENT_ID     = os.getenv("OUTLOOK_CLIENT_ID", "")
_TENANT_ID     = os.getenv("OUTLOOK_TENANT_ID", "common")
_CLIENT_SECRET = os.getenv("OUTLOOK_CLIENT_SECRET", "")
_REDIRECT_URI  = os.getenv(
    "REDIRECT_URI",
    "https://jarvis-os-production.up.railway.app/auth/microsoft/callback",
)

_AUTHORITY  = f"https://login.microsoftonline.com/{_TENANT_ID}"
_AUTH_URL   = f"{_AUTHORITY}/oauth2/v2.0/authorize"
_TOKEN_URL  = f"{_AUTHORITY}/oauth2/v2.0/token"

_SCOPES: List[str] = [
    "openid",
    "profile",
    "email",
    "offline_access",
    "Mail.Read",
    "Mail.Send",
    "Mail.ReadWrite",
    "Calendars.ReadWrite",
    "Tasks.ReadWrite",
]


# ── Token store ───────────────────────────────────────────────────────────────

class TokenStore:
    """
    In-memory token store. Replace `save` / `get` with DB calls to persist.
    Each user maps to: {access_token, refresh_token, expires_in, saved_at, ...}
    """

    def __init__(self) -> None:
        self._tokens: Dict[str, Dict] = {}
        self._states: Dict[str, str]  = {}   # CSRF state → user_id

    # ── Token CRUD ────────────────────────────────────────────────────────

    def save(self, user_id: str, token_data: Dict) -> None:
        token_data = dict(token_data)
        token_data["saved_at"] = time.time()
        self._tokens[user_id] = token_data
        log.info("Token saved for user=%s (expires_in=%s)", user_id, token_data.get("expires_in"))

    def get(self, user_id: str) -> Optional[Dict]:
        return self._tokens.get(user_id)

    def clear(self, user_id: str) -> None:
        self._tokens.pop(user_id, None)

    def all_users(self) -> List[str]:
        return list(self._tokens.keys())

    # ── Expiry check ──────────────────────────────────────────────────────

    def is_expired(self, user_id: str, buffer_seconds: int = 300) -> bool:
        """Returns True if the access token has expired or will expire within buffer."""
        t = self._tokens.get(user_id)
        if not t:
            return True
        expires_in = t.get("expires_in", 3600)
        saved_at   = t.get("saved_at", 0.0)
        return time.time() >= saved_at + expires_in - buffer_seconds

    def get_access_token(self, user_id: str) -> Optional[str]:
        t = self._tokens.get(user_id)
        return t.get("access_token") if t else None

    def is_authenticated(self, user_id: str) -> bool:
        return user_id in self._tokens

    # ── CSRF state management ─────────────────────────────────────────────

    def register_state(self, state: str, user_id: str = "owner") -> None:
        self._states[state] = user_id

    def consume_state(self, state: str) -> Optional[str]:
        """Pop and return the user_id for a given state. Returns None if invalid."""
        return self._states.pop(state, None)


# Singleton
token_store = TokenStore()


# ── Auth flow helpers ─────────────────────────────────────────────────────────

def get_login_url() -> Tuple[str, str]:
    """
    Build the Microsoft OAuth2 login URL.
    Returns (url, state) — store the state to validate on callback.
    """
    state = secrets.token_urlsafe(32)
    token_store.register_state(state)
    params = {
        "client_id":     _CLIENT_ID,
        "response_type": "code",
        "redirect_uri":  _REDIRECT_URI,
        "scope":         " ".join(_SCOPES),
        "state":         state,
        "response_mode": "query",
        "prompt":        "select_account",
    }
    url = f"{_AUTH_URL}?{urlencode(params)}"
    log.info("Login URL generated (state=%s...)", state[:8])
    return url, state


async def exchange_code(code: str) -> Dict:
    """Exchange an authorization code for tokens. Raises on failure."""
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(_TOKEN_URL, data={
            "client_id":     _CLIENT_ID,
            "client_secret": _CLIENT_SECRET,
            "code":          code,
            "redirect_uri":  _REDIRECT_URI,
            "grant_type":    "authorization_code",
            "scope":         " ".join(_SCOPES),
        })
        resp.raise_for_status()
        return resp.json()


async def refresh_token(user_id: str) -> bool:
    """
    Refresh the access token using the stored refresh_token.
    Returns True on success, False on failure.
    """
    t = token_store.get(user_id)
    if not t or not t.get("refresh_token"):
        log.warning("No refresh token available for user=%s", user_id)
        return False

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(_TOKEN_URL, data={
                "client_id":     _CLIENT_ID,
                "client_secret": _CLIENT_SECRET,
                "refresh_token": t["refresh_token"],
                "grant_type":    "refresh_token",
                "scope":         " ".join(_SCOPES),
            })
            resp.raise_for_status()
            new_tokens = resp.json()
            # Preserve refresh_token if the new response doesn't include one
            if "refresh_token" not in new_tokens:
                new_tokens["refresh_token"] = t["refresh_token"]
            token_store.save(user_id, new_tokens)
            log.info("Token refreshed for user=%s", user_id)
            return True
    except httpx.HTTPStatusError as exc:
        log.error("Token refresh HTTP error %d for user=%s: %s",
                  exc.response.status_code, user_id, exc.response.text[:200])
        return False
    except Exception as exc:
        log.error("Token refresh error for user=%s: %s", user_id, exc)
        return False


async def get_valid_token(user_id: str = "owner") -> Optional[str]:
    """
    Return a valid access token, transparently refreshing if needed.
    Returns None if authentication is required.
    """
    if not token_store.is_authenticated(user_id):
        log.debug("User %s not authenticated", user_id)
        return None
    if token_store.is_expired(user_id):
        log.info("Token expired for user=%s — refreshing", user_id)
        if not await refresh_token(user_id):
            return None
    return token_store.get_access_token(user_id)


def is_configured() -> bool:
    """Returns True if environment variables are set for Microsoft auth."""
    return bool(_CLIENT_ID and _CLIENT_SECRET)
