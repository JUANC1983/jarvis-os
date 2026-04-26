from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import jwt

from core.user_engine import UserEngine, _public

_SECRET_FILE = Path("data/jwt_secret.key")
_ALGORITHM   = "HS256"


def _load_secret() -> str:
    env_secret = os.getenv("JWT_SECRET", "").strip()
    if env_secret:
        return env_secret
    if _SECRET_FILE.exists():
        s = _SECRET_FILE.read_text(encoding="utf-8").strip()
        if s:
            return s
    import secrets
    s = secrets.token_hex(64)
    _SECRET_FILE.parent.mkdir(parents=True, exist_ok=True)
    _SECRET_FILE.write_text(s, encoding="utf-8")
    return s


_JWT_SECRET: str = _load_secret()
_EXPIRE_HOURS: int = int(os.getenv("JWT_EXPIRE_HOURS", "720"))  # 30 days default


class AuthEngine:
    def __init__(self, user_engine: UserEngine | None = None) -> None:
        self.users = user_engine or UserEngine()

    # ── token ops ───────────────────────────────────────────────────

    def create_token(self, user_id: str, role: str) -> str:
        exp = datetime.now(tz=timezone.utc) + timedelta(hours=_EXPIRE_HOURS)
        payload = {"sub": user_id, "role": role, "exp": exp}
        return jwt.encode(payload, _JWT_SECRET, algorithm=_ALGORITHM)

    def decode_token(self, token: str) -> Optional[Dict[str, Any]]:
        try:
            payload = jwt.decode(token, _JWT_SECRET, algorithms=[_ALGORITHM])
            return {"user_id": payload["sub"], "role": payload.get("role", "user")}
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None

    # ── auth ops ────────────────────────────────────────────────────

    def register(
        self, name: str, email: str, password: str, role: str = "user"
    ) -> Dict[str, Any]:
        if len(password) < 6:
            raise ValueError("Password must be at least 6 characters")
        user = self.users.create_user(name, email, password, role)
        token = self.create_token(user["user_id"], user["role"])
        return {"token": token, "user": user}

    def login(self, email: str, password: str) -> Optional[Dict[str, Any]]:
        user = self.users.verify_email_password(email, password)
        if not user:
            return None
        token = self.create_token(user["user_id"], user["role"])
        return {"token": token, "user": user}

    def get_me(self, user_id: str) -> Optional[Dict]:
        raw = self.users.get_user(user_id)
        return _public(raw) if raw else None

    def update_me(self, user_id: str, updates: Dict[str, Any]) -> Dict:
        return self.users.update_user(user_id, updates)
