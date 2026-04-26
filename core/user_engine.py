from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

_FILE = Path("data/users.json")
_OWNER_EMAIL = "owner@jarvis.local"
_OWNER_NAME  = "Owner"


class UserEngine:
    def __init__(self, file_path: str | Path = _FILE) -> None:
        self.path = Path(file_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write({"users": []})
        self._seed_owner()

    # ── persistence ─────────────────────────────────────────────────

    def _read(self) -> Dict[str, Any]:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _write(self, data: Dict[str, Any]) -> None:
        self.path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # ── seed ────────────────────────────────────────────────────────

    def _seed_owner(self) -> None:
        import os
        data = self._read()
        if any(u.get("user_id") == "owner" for u in data["users"]):
            return
        owner_hash = _hash_password(os.getenv("JARVIS_OWNER_PASSWORD", "jarvis2026"))
        owner: Dict[str, Any] = {
            "user_id":      "owner",
            "name":         _OWNER_NAME,
            "email":        _OWNER_EMAIL,
            "role":         "owner",
            "password_hash": owner_hash,
            "preferences":  {},
            "created_at":   datetime.utcnow().isoformat(),
            "updated_at":   datetime.utcnow().isoformat(),
        }
        data["users"].insert(0, owner)
        self._write(data)

    # ── public API ───────────────────────────────────────────────────

    def get_user(self, user_id: str) -> Optional[Dict]:
        data = self._read()
        return next((u for u in data["users"] if u.get("user_id") == user_id), None)

    def get_user_by_email(self, email: str) -> Optional[Dict]:
        data = self._read()
        return next(
            (u for u in data["users"] if u.get("email", "").lower() == email.lower()),
            None,
        )

    def list_users(self) -> List[Dict]:
        return [_public(u) for u in self._read()["users"]]

    def create_user(
        self,
        name: str,
        email: str,
        password: str,
        role: str = "user",
    ) -> Dict:
        data = self._read()
        email_lc = email.strip().lower()
        if any(u.get("email", "").lower() == email_lc for u in data["users"]):
            raise ValueError(f"Email '{email}' already registered")
        now = datetime.utcnow().isoformat()
        user: Dict[str, Any] = {
            "user_id":       f"u_{uuid4().hex[:12]}",
            "name":          name.strip(),
            "email":         email_lc,
            "role":          role if role in ("owner", "admin", "user") else "user",
            "password_hash": _hash_password(password),
            "preferences":   {},
            "created_at":    now,
            "updated_at":    now,
        }
        data["users"].append(user)
        self._write(data)
        return _public(user)

    def update_user(self, user_id: str, updates: Dict[str, Any]) -> Dict:
        data = self._read()
        allowed = {"name", "email", "preferences"}
        for u in data["users"]:
            if u.get("user_id") == user_id:
                for k, v in updates.items():
                    if k in allowed:
                        u[k] = v
                u["updated_at"] = datetime.utcnow().isoformat()
                self._write(data)
                return _public(u)
        raise ValueError(f"User '{user_id}' not found")

    def verify_password(self, user_id: str, password: str) -> bool:
        user = self.get_user(user_id)
        if not user:
            return False
        return _verify_password(password, user.get("password_hash", ""))

    def verify_email_password(self, email: str, password: str) -> Optional[Dict]:
        user = self.get_user_by_email(email)
        if not user:
            return None
        if not _verify_password(password, user.get("password_hash", "")):
            return None
        return _public(user)


# ── password hashing (stdlib PBKDF2-SHA256) ──────────────────────────

def _hash_password(password: str) -> str:
    import base64, hashlib, os
    salt = os.urandom(32)
    dk   = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 260_000)
    return "pbkdf2:sha256:260000:" + base64.b64encode(salt).decode() + ":" + base64.b64encode(dk).decode()


def _verify_password(password: str, stored: str) -> bool:
    import base64, hashlib, hmac as _hmac
    try:
        _, algo, iters, salt_b64, dk_b64 = stored.split(":", 4)
        salt     = base64.b64decode(salt_b64)
        expected = base64.b64decode(dk_b64)
        actual   = hashlib.pbkdf2_hmac(algo, password.encode("utf-8"), salt, int(iters))
        return _hmac.compare_digest(actual, expected)
    except Exception:
        return False


def _public(user: Dict) -> Dict:
    """Return user dict without password_hash."""
    return {k: v for k, v in user.items() if k != "password_hash"}
