from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from .token_store import TokenStore


class BaseIntegration(ABC):
    """
    Standard interface all JARVIS integrations implement.

    Lifecycle:
      get_auth_url()  → user visits URL → redirected with ?code=...
      exchange_code() → trades code for tokens → stores in TokenStore
      sync()          → pulls data into JARVIS engines
      revoke()        → deletes stored tokens

    When env credentials are missing, get_auth_url() raises ConfigError
    so the UI can display a clear "not configured" message.
    """

    provider:    str = ""
    display_name: str = ""
    scopes:      List[str] = []

    def __init__(self, token_store: TokenStore) -> None:
        self.tokens = token_store

    # ── abstract ──────────────────────────────────────────────────────

    @abstractmethod
    def get_auth_url(self, redirect_uri: str, state: str = "") -> str:
        """Return OAuth authorisation URL. Raises ConfigError if not configured."""

    @abstractmethod
    def exchange_code(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        """Exchange auth code for tokens; persist to TokenStore. Returns status dict."""

    @abstractmethod
    def refresh(self) -> bool:
        """Refresh access token using stored refresh token. Returns success bool."""

    @abstractmethod
    def sync(self, **engines: Any) -> Dict[str, Any]:
        """Pull remote data into JARVIS. engines = {calendar, memory, ...}"""

    # ── common helpers ────────────────────────────────────────────────

    def status(self) -> Dict[str, Any]:
        st = self.tokens.status(self.provider)
        st["display_name"] = self.display_name
        st["expired"]      = self.tokens.is_expired(self.provider)
        return st

    def revoke(self) -> bool:
        return self.tokens.delete(self.provider)

    def is_connected(self) -> bool:
        return bool(self.tokens.load(self.provider))

    def _get_token(self) -> Optional[str]:
        record = self.tokens.load(self.provider)
        return record.get("access_token") if record else None


class ConfigError(Exception):
    """Raised when required env vars / credentials are missing."""
