"""
Microsoft Identity Platform OAuth2 authentication.
Manages token acquisition, storage, and transparent refresh.
Structured for in-memory-now / DB-later swap.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import secrets
import time
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlencode

import httpx

log = logging.getLogger("jarvis.outlook_auth")


def _decode_jwt_payload(token: str) -> Dict:
    """Decode JWT payload without verifying signature (for debug logging only)."""
    try:
        parts = token.split(".")
        if len(parts) < 2:
            return {}
        # Add padding and decode base64url
        payload_b64 = parts[1] + "=" * (4 - len(parts[1]) % 4)
        payload_bytes = base64.urlsafe_b64decode(payload_b64)
        return json.loads(payload_bytes)
    except Exception:
        return {}

# ── Config from environment ───────────────────────────────────────────────────
# Support multiple env var name conventions with explicit priority order.

def _env_first(*names: str, default: str = "") -> str:
    """Return first non-empty env var from the provided names."""
    for name in names:
        val = os.getenv(name, "").strip()
        if val:
            return val
    return default


_CLIENT_ID     = _env_first("OUTLOOK_CLIENT_ID", "OUTLOOK_APPLICATION")
_TENANT_ID     = _env_first("OUTLOOK_TENANT_ID", "OUTLOOK_DIRECTORY", default="common")
_CLIENT_SECRET = _env_first("OUTLOOK_CLIENT_SECRET")
_REDIRECT_URI  = _env_first(
    "OUTLOOK_REDIRECT_URI",
    "REDIRECT_URI",
    default="https://jarvis-os-production.up.railway.app/auth/microsoft/callback",
)

_AUTHORITY  = f"https://login.microsoftonline.com/{_TENANT_ID}"
_AUTH_URL   = f"{_AUTHORITY}/oauth2/v2.0/authorize"
_TOKEN_URL  = f"{_AUTHORITY}/oauth2/v2.0/token"

_SCOPES: List[str] = [
    "https://graph.microsoft.com/Mail.Read",
    "https://graph.microsoft.com/Mail.ReadWrite",
    "https://graph.microsoft.com/Mail.Send",
    "offline_access",
    "User.Read",
]

def config_status() -> Dict:
    """Return a safe config status dict (no secrets exposed)."""
    return {
        "configured":    bool(_CLIENT_ID and _CLIENT_SECRET),
        "client_id_set": bool(_CLIENT_ID),
        "secret_set":    bool(_CLIENT_SECRET),
        "tenant_id":     _TENANT_ID,
        "redirect_uri":  _REDIRECT_URI,
        "reason":        None if (_CLIENT_ID and _CLIENT_SECRET)
                         else "OUTLOOK_CLIENT_ID or OUTLOOK_CLIENT_SECRET not set",
    }


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
        access = token_data.get("access_token", "")
        print(f"[AUTH] Token stored for {user_id} | prefix={access[:20]}... | expires_in={token_data.get('expires_in')}")
        # Decode JWT payload — validate audience and log scopes
        payload = _decode_jwt_payload(access)
        aud    = payload.get("aud", "unknown")
        scopes = payload.get("scp", payload.get("roles", "unknown"))
        print(f"[AUTH] aud: {aud}")
        print(f"[AUTH] scopes: {scopes}")
        if aud and aud != "unknown" and "graph.microsoft.com" not in str(aud):
            raise Exception(
                f"Token audience invalid — must be Graph, got: {aud}. "
                "Re-authenticate to get a Graph-scoped token."
            )
        log.info("Token saved for user=%s (expires_in=%s, aud=%s, scopes=%s)",
                 user_id, token_data.get("expires_in"), aud, scopes)

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
    Raises ValueError if client_id is not configured.
    """
    if not _CLIENT_ID:
        raise ValueError(
            "OUTLOOK_CLIENT_ID is not set. Configure the environment variable before connecting."
        )
    state = secrets.token_urlsafe(32)
    token_store.register_state(state)
    params = {
        "client_id":     _CLIENT_ID,
        "response_type": "code",
        "redirect_uri":  _REDIRECT_URI,
        "scope":         " ".join(_SCOPES),
        "state":         state,
        "response_mode": "query",
        "prompt":        "consent",
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
        print(f"[AUTH] No refresh_token stored for user={user_id}")
        log.warning("No refresh token available for user=%s", user_id)
        return False

    print(f"[AUTH] Refreshing token for user={user_id} via {_TOKEN_URL}")
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(_TOKEN_URL, data={
                "client_id":     _CLIENT_ID,
                "client_secret": _CLIENT_SECRET,
                "refresh_token": t["refresh_token"],
                "grant_type":    "refresh_token",
                "scope":         " ".join(_SCOPES),
            })
        print(f"[AUTH] Refresh STATUS: {resp.status_code}")
        if resp.status_code != 200:
            print(f"[AUTH] Refresh FAILED: {resp.text[:400]}")
            log.error("Token refresh HTTP %d for user=%s: %s",
                      resp.status_code, user_id, resp.text[:300])
            return False
        new_tokens = resp.json()
        # Preserve refresh_token if the new response doesn't include one
        if "refresh_token" not in new_tokens:
            new_tokens["refresh_token"] = t["refresh_token"]
        token_store.save(user_id, new_tokens)
        print(f"[AUTH] Token refreshed for user={user_id}")
        log.info("Token refreshed for user=%s", user_id)
        return True
    except Exception as exc:
        print(f"[AUTH] Refresh exception for user={user_id}: {exc}")
        log.error("Token refresh error for user=%s: %s", user_id, exc)
        return False


async def get_valid_token(user_id: str = "owner") -> Optional[str]:
    """
    Return a valid access token, transparently refreshing if needed.
    Returns None if authentication is required.
    """
    if not token_store.is_authenticated(user_id):
        print(f"[AUTH] No token stored for user={user_id} — re-auth required")
        log.warning("User %s not authenticated — token store empty", user_id)
        return None
    if token_store.is_expired(user_id):
        print(f"[AUTH] Token expired for user={user_id} — refreshing")
        log.info("Token expired for user=%s — refreshing", user_id)
        if not await refresh_token(user_id):
            print(f"[AUTH] Token refresh FAILED for user={user_id}")
            return None
    token = token_store.get_access_token(user_id)
    if token:
        print(f"[GRAPH] Using token: {token[:20]}...")
    return token


def is_configured() -> bool:
    """Returns True if environment variables are set for Microsoft auth."""
    return bool(_CLIENT_ID and _CLIENT_SECRET)
