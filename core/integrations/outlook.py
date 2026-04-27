from __future__ import annotations

import os
import urllib.parse
import urllib.request
import json
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List

from .base import BaseIntegration, ConfigError
from .token_store import TokenStore

_TENANT      = "common"
_AUTH_URL    = f"https://login.microsoftonline.com/{_TENANT}/oauth2/v2.0/authorize"
_TOKEN_URL   = f"https://login.microsoftonline.com/{_TENANT}/oauth2/v2.0/token"
_EVENTS_URL  = "https://graph.microsoft.com/v1.0/me/calendarView"

_SCOPES = [
    "Calendars.Read",
    "User.Read",
    "offline_access",
]


class OutlookIntegration(BaseIntegration):
    provider     = "outlook"
    display_name = "Microsoft Outlook / Calendar"
    scopes       = _SCOPES

    def __init__(self, token_store: TokenStore) -> None:
        super().__init__(token_store)
        self._client_id     = os.getenv("MICROSOFT_CLIENT_ID", "")
        self._client_secret = os.getenv("MICROSOFT_CLIENT_SECRET", "")

    def _configured(self) -> bool:
        return bool(self._client_id and self._client_secret)

    def get_auth_url(self, redirect_uri: str, state: str = "") -> str:
        if not self._configured():
            raise ConfigError(
                "MICROSOFT_CLIENT_ID and MICROSOFT_CLIENT_SECRET env vars not set. "
                "Register an app at portal.azure.com."
            )
        params = {
            "client_id":     self._client_id,
            "response_type": "code",
            "redirect_uri":  redirect_uri,
            "response_mode": "query",
            "scope":         " ".join(_SCOPES),
        }
        if state:
            params["state"] = state
        return f"{_AUTH_URL}?{urllib.parse.urlencode(params)}"

    def exchange_code(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        if not self._configured():
            raise ConfigError("Microsoft credentials not configured")
        payload = urllib.parse.urlencode({
            "grant_type":    "authorization_code",
            "code":          code,
            "redirect_uri":  redirect_uri,
            "client_id":     self._client_id,
            "client_secret": self._client_secret,
            "scope":         " ".join(_SCOPES),
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
            "scope":         " ".join(_SCOPES),
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
        token = self._get_token()
        if not token:
            return {"synced": False, "reason": "not connected"}
        if self.tokens.is_expired(self.provider):
            if not self.refresh():
                return {"synced": False, "reason": "token expired, refresh failed"}
            token = self._get_token()

        try:
            now   = datetime.now(timezone.utc)
            end   = now + timedelta(days=14)
            params = urllib.parse.urlencode({
                "startDateTime": now.isoformat(),
                "endDateTime":   end.isoformat(),
                "$top":          20,
                "$orderby":      "start/dateTime",
            })
            req = urllib.request.Request(
                f"{_EVENTS_URL}?{params}",
                headers={"Authorization": f"Bearer {token}",
                         "Content-Type":  "application/json"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())

            items: List[Dict] = data.get("value", [])
            cal_engine = engines.get("calendar")
            imported   = 0
            for ev in items:
                start = ev.get("start", {}).get("dateTime", "")
                end_t = ev.get("end",   {}).get("dateTime", "")
                if cal_engine and start:
                    try:
                        cal_engine.create_event(
                            title       = ev.get("subject", "Outlook Event"),
                            start       = start[:16].replace("T", " "),
                            end         = end_t[:16].replace("T", " ") if end_t else "",
                            description = ev.get("bodyPreview", ""),
                        )
                        imported += 1
                    except Exception:
                        pass

            return {"synced": True, "imported": imported, "total_remote": len(items)}

        except Exception as e:
            return {"synced": False, "reason": str(e)}
