from __future__ import annotations

import os
import urllib.parse
import urllib.request
import json
import base64
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List

from .base import BaseIntegration, ConfigError
from .token_store import TokenStore

_AUTH_URL   = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_URL  = "https://oauth2.googleapis.com/token"
_MSGS_URL   = "https://gmail.googleapis.com/gmail/v1/users/me/messages"

_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
]


class GmailIntegration(BaseIntegration):
    provider     = "gmail"
    display_name = "Gmail"
    scopes       = _SCOPES

    def __init__(self, token_store: TokenStore) -> None:
        super().__init__(token_store)
        # Reuses Google credentials (same project, different scopes)
        self._client_id     = os.getenv("GOOGLE_CLIENT_ID", "")
        self._client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "")

    def _configured(self) -> bool:
        return bool(self._client_id and self._client_secret)

    def get_auth_url(self, redirect_uri: str, state: str = "") -> str:
        if not self._configured():
            raise ConfigError(
                "GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET env vars not set. "
                "Enable Gmail API at console.cloud.google.com."
            )
        params = {
            "client_id":     self._client_id,
            "redirect_uri":  redirect_uri,
            "response_type": "code",
            "scope":         " ".join(_SCOPES),
            "access_type":   "offline",
            "prompt":        "consent",
        }
        if state:
            params["state"] = state
        return f"{_AUTH_URL}?{urllib.parse.urlencode(params)}"

    def exchange_code(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        if not self._configured():
            raise ConfigError("Google credentials not configured")
        payload = urllib.parse.urlencode({
            "code":          code,
            "client_id":     self._client_id,
            "client_secret": self._client_secret,
            "redirect_uri":  redirect_uri,
            "grant_type":    "authorization_code",
        }).encode()
        req = urllib.request.Request(
            _TOKEN_URL, data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())

        expires_at = None
        if "expires_in" in data:
            exp = datetime.now(timezone.utc) + timedelta(seconds=int(data["expires_in"]))
            expires_at = exp.isoformat()

        self.tokens.save(
            provider      = self.provider,
            access_token  = data["access_token"],
            refresh_token = data.get("refresh_token"),
            expires_at    = expires_at,
            scopes        = _SCOPES,
        )
        return {"connected": True, "provider": self.provider}

    def refresh(self) -> bool:
        record = self.tokens.load(self.provider)
        if not record or not record.get("refresh_token"):
            return False
        if not self._configured():
            return False
        payload = urllib.parse.urlencode({
            "grant_type":    "refresh_token",
            "refresh_token": record["refresh_token"],
            "client_id":     self._client_id,
            "client_secret": self._client_secret,
        }).encode()
        try:
            req = urllib.request.Request(
                _TOKEN_URL, data=payload,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
            expires_at = None
            if "expires_in" in data:
                exp = datetime.now(timezone.utc) + timedelta(seconds=int(data["expires_in"]))
                expires_at = exp.isoformat()
            self.tokens.save(
                provider      = self.provider,
                access_token  = data["access_token"],
                refresh_token = record.get("refresh_token"),
                expires_at    = expires_at,
                scopes        = _SCOPES,
            )
            return True
        except Exception:
            return False

    def revoke(self) -> bool:
        return self.tokens.delete(self.provider)

    def sync(self, **engines: Any) -> Dict[str, Any]:
        """
        Pull last 10 unread emails, extract subject+snippet,
        save high-value ones as memory insights.
        """
        token = self._get_token()
        if not token:
            return {"synced": False, "reason": "not connected"}
        if self.tokens.is_expired(self.provider):
            if not self.refresh():
                return {"synced": False, "reason": "token expired"}
            token = self._get_token()

        try:
            params = urllib.parse.urlencode({
                "q":          "is:unread",
                "maxResults": 10,
            })
            req = urllib.request.Request(
                f"{_MSGS_URL}?{params}",
                headers={"Authorization": f"Bearer {token}"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                list_data = json.loads(resp.read())

            messages   = list_data.get("messages", [])
            mem_engine = engines.get("memory")
            saved      = 0

            for msg_ref in messages[:5]:
                try:
                    req2 = urllib.request.Request(
                        f"{_MSGS_URL}/{msg_ref['id']}?format=metadata"
                        "&metadataHeaders=Subject&metadataHeaders=From",
                        headers={"Authorization": f"Bearer {token}"},
                    )
                    with urllib.request.urlopen(req2, timeout=10) as resp2:
                        msg = json.loads(resp2.read())

                    headers = {h["name"]: h["value"]
                               for h in msg.get("payload", {}).get("headers", [])}
                    subject = headers.get("Subject", "(no subject)")
                    sender  = headers.get("From", "")
                    snippet = msg.get("snippet", "")

                    if mem_engine:
                        mem_engine.save(
                            content    = f"Email from {sender}: {subject}. {snippet[:150]}",
                            entry_type = "event",
                            importance = 4,
                            tags       = ["email", "gmail"],
                        )
                        saved += 1
                except Exception:
                    pass

            return {"synced": True, "processed": len(messages), "saved_to_memory": saved}

        except Exception as e:
            return {"synced": False, "reason": str(e)}
