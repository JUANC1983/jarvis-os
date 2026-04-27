from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


class TokenStore:
    """
    Secure per-user token storage.
    File: data/integrations/{user_id}.json

    Schema:
      {
        "<provider>": {
          "access_token":  str,
          "refresh_token": str | null,
          "expires_at":    ISO str | null,
          "scopes":        [str],
          "connected_at":  ISO str,
          "extra":         {}          # provider-specific metadata
        }
      }

    Tokens are never logged.  expires_at uses UTC ISO-8601.
    """

    def __init__(self, file_path: str | Path) -> None:
        self.path = Path(file_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write({})

    # ── persistence ──────────────────────────────────────────────────

    def _read(self) -> Dict[str, Any]:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _write(self, data: Dict[str, Any]) -> None:
        self.path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # ── public API ───────────────────────────────────────────────────

    def save(
        self,
        provider:      str,
        access_token:  str,
        refresh_token: Optional[str] = None,
        expires_at:    Optional[str] = None,
        scopes:        List[str] | None = None,
        extra:         Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        record = {
            "access_token":  access_token,
            "refresh_token": refresh_token,
            "expires_at":    expires_at,
            "scopes":        scopes or [],
            "connected_at":  datetime.now(timezone.utc).isoformat(),
            "extra":         extra or {},
        }
        data = self._read()
        data[provider] = record
        self._write(data)
        return self._public(provider, record)

    def load(self, provider: str) -> Optional[Dict[str, Any]]:
        """Returns full token record including access_token (internal use only)."""
        return self._read().get(provider)

    def status(self, provider: str) -> Dict[str, Any]:
        """Returns public-safe status (no access_token)."""
        record = self._read().get(provider)
        if not record:
            return {"provider": provider, "connected": False}
        return self._public(provider, record)

    def all_status(self) -> Dict[str, Dict[str, Any]]:
        data = self._read()
        return {p: self._public(p, r) for p, r in data.items()}

    def list_connected(self) -> List[str]:
        return list(self._read().keys())

    def delete(self, provider: str) -> bool:
        data = self._read()
        if provider not in data:
            return False
        del data[provider]
        self._write(data)
        return True

    def is_expired(self, provider: str) -> bool:
        record = self._read().get(provider)
        if not record or not record.get("expires_at"):
            return False
        try:
            exp = datetime.fromisoformat(record["expires_at"])
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            return datetime.now(timezone.utc) >= exp
        except Exception:
            return False

    # ── helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _public(provider: str, record: Dict[str, Any]) -> Dict[str, Any]:
        """Strip access_token before returning to callers."""
        return {
            "provider":     provider,
            "connected":    True,
            "scopes":       record.get("scopes", []),
            "connected_at": record.get("connected_at"),
            "expires_at":   record.get("expires_at"),
            "expired":      False,   # caller can check is_expired()
            "extra":        {k: v for k, v in record.get("extra", {}).items()
                             if k not in ("client_secret",)},
        }
