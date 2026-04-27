from __future__ import annotations

import os
import urllib.parse
import urllib.request
import json
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List

from .base import BaseIntegration, ConfigError
from .token_store import TokenStore

_AUTH_URL    = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_URL   = "https://oauth2.googleapis.com/token"
_REVOKE_URL  = "https://oauth2.googleapis.com/revoke"
_EVENTS_URL  = "https://www.googleapis.com/calendar/v3/calendars/primary/events"

_SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
]


class GoogleCalendarIntegration(BaseIntegration):
    provider     = "google_calendar"
    display_name = "Google Calendar"
    scopes       = _SCOPES

    def __init__(self, token_store: TokenStore) -> None:
        super().__init__(token_store)
        self._client_id     = os.getenv("GOOGLE_CLIENT_ID", "")
        self._client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "")

    def _configured(self) -> bool:
        return bool(self._client_id and self._client_secret)

    # ── OAuth flow ───────────────────────────────────────────────────

    def get_auth_url(self, redirect_uri: str, state: str = "") -> str:
        if not self._configured():
            raise ConfigError(
                "GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET env vars not set. "
                "Create credentials at console.cloud.google.com."
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
        token = self._get_token()
        if token:
            try:
                url = f"{_REVOKE_URL}?token={urllib.parse.quote(token)}"
                urllib.request.urlopen(url, timeout=5)
            except Exception:
                pass
        return self.tokens.delete(self.provider)

    # ── sync ─────────────────────────────────────────────────────────

    def sync(self, **engines: Any) -> Dict[str, Any]:
        token = self._get_token()
        if not token:
            return {"synced": False, "reason": "not connected"}
        if self.tokens.is_expired(self.provider):
            if not self.refresh():
                return {"synced": False, "reason": "token expired, refresh failed"}
            token = self._get_token()

        try:
            now = datetime.now(timezone.utc)
            params = urllib.parse.urlencode({
                "timeMin":    now.isoformat(),
                "maxResults": 20,
                "singleEvents": "true",
                "orderBy":    "startTime",
            })
            req = urllib.request.Request(
                f"{_EVENTS_URL}?{params}",
                headers={"Authorization": f"Bearer {token}"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())

            items: List[Dict] = data.get("items", [])
            cal_engine = engines.get("calendar")
            imported   = 0
            for ev in items:
                start = (ev.get("start", {}).get("dateTime")
                         or ev.get("start", {}).get("date", ""))
                end   = (ev.get("end",   {}).get("dateTime")
                         or ev.get("end",   {}).get("date", ""))
                if cal_engine and start:
                    try:
                        cal_engine.create_event(
                            title       = ev.get("summary", "Google Event"),
                            start       = start[:16].replace("T", " "),
                            end         = end[:16].replace("T", " ") if end else "",
                            description = ev.get("description", ""),
                        )
                        imported += 1
                    except Exception:
                        pass

            return {"synced": True, "imported": imported, "total_remote": len(items)}

        except Exception as e:
            return {"synced": False, "reason": str(e)}
