from __future__ import annotations

import os
import urllib.parse
import urllib.request
import json
from datetime import datetime, timezone
from typing import Any, Dict, List

from .base import BaseIntegration, ConfigError
from .token_store import TokenStore

_AUTH_URL   = "https://slack.com/oauth/v2/authorize"
_TOKEN_URL  = "https://slack.com/api/oauth.v2.access"
_MSG_URL    = "https://slack.com/api/conversations.history"
_POST_URL   = "https://slack.com/api/chat.postMessage"

_SCOPES = ["channels:history", "channels:read", "chat:write", "users:read"]


class SlackIntegration(BaseIntegration):
    provider     = "slack"
    display_name = "Slack"
    scopes       = _SCOPES

    def __init__(self, token_store: TokenStore) -> None:
        super().__init__(token_store)
        self._client_id     = os.getenv("SLACK_CLIENT_ID", "")
        self._client_secret = os.getenv("SLACK_CLIENT_SECRET", "")

    def _configured(self) -> bool:
        return bool(self._client_id and self._client_secret)

    def get_auth_url(self, redirect_uri: str, state: str = "") -> str:
        if not self._configured():
            raise ConfigError(
                "SLACK_CLIENT_ID and SLACK_CLIENT_SECRET env vars not set. "
                "Create a Slack App at api.slack.com/apps."
            )
        params = {
            "client_id":    self._client_id,
            "scope":        ",".join(_SCOPES),
            "redirect_uri": redirect_uri,
        }
        if state:
            params["state"] = state
        return f"{_AUTH_URL}?{urllib.parse.urlencode(params)}"

    def exchange_code(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        if not self._configured():
            raise ConfigError("Slack credentials not configured")
        payload = urllib.parse.urlencode({
            "code":          code,
            "client_id":     self._client_id,
            "client_secret": self._client_secret,
            "redirect_uri":  redirect_uri,
        }).encode()
        req = urllib.request.Request(
            _TOKEN_URL, data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())

        if not data.get("ok"):
            raise ValueError(f"Slack error: {data.get('error')}")

        access_token = data.get("access_token") or data.get("authed_user", {}).get("access_token", "")
        team         = data.get("team", {})

        self.tokens.save(
            provider     = self.provider,
            access_token = access_token,
            scopes       = _SCOPES,
            extra        = {"team_id": team.get("id"), "team_name": team.get("name")},
        )
        return {"connected": True, "provider": self.provider,
                "team": team.get("name", "")}

    def refresh(self) -> bool:
        # Slack tokens don't expire — no refresh needed
        return True

    def revoke(self) -> bool:
        token = self._get_token()
        if token:
            try:
                payload = urllib.parse.urlencode({"token": token}).encode()
                req = urllib.request.Request(
                    "https://slack.com/api/auth.revoke",
                    data=payload,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                urllib.request.urlopen(req, timeout=5)
            except Exception:
                pass
        return self.tokens.delete(self.provider)

    def send_message(self, channel: str, text: str) -> Dict[str, Any]:
        """Post a message to a Slack channel (used by automation actions)."""
        token = self._get_token()
        if not token:
            return {"ok": False, "error": "not connected"}
        payload = json.dumps({"channel": channel, "text": text}).encode()
        req = urllib.request.Request(
            _POST_URL, data=payload,
            headers={"Authorization": f"Bearer {token}",
                     "Content-Type":  "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read())
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def sync(self, **engines: Any) -> Dict[str, Any]:
        """
        Pull last 20 messages from default channel,
        save important ones as memory entries.
        """
        token = self._get_token()
        if not token:
            return {"synced": False, "reason": "not connected"}

        record  = self.tokens.load(self.provider) or {}
        channel = record.get("extra", {}).get("default_channel", "general")

        try:
            params = urllib.parse.urlencode({
                "channel": channel,
                "limit":   20,
            })
            req = urllib.request.Request(
                f"{_MSG_URL}?{params}",
                headers={"Authorization": f"Bearer {token}"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())

            if not data.get("ok"):
                return {"synced": False, "reason": data.get("error", "unknown")}

            messages   = data.get("messages", [])
            mem_engine = engines.get("memory")
            saved      = 0
            for msg in messages[:10]:
                text = msg.get("text", "").strip()
                if text and len(text) > 20 and mem_engine:
                    mem_engine.save(
                        content    = f"Slack #{channel}: {text[:200]}",
                        entry_type = "event",
                        importance = 3,
                        tags       = ["slack", "message"],
                    )
                    saved += 1

            return {"synced": True, "processed": len(messages), "saved_to_memory": saved}

        except Exception as e:
            return {"synced": False, "reason": str(e)}
