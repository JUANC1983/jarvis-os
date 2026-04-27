"""Family Engine — Members, Events, Notes per user.

Persisted as JSON under data/family/{user_id}/
Thread-safe; all public methods return dicts ready for JSON serialisation.
"""
from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional


def _now() -> str:
    return datetime.utcnow().isoformat()

def _gen_id() -> str:
    return hashlib.sha256(datetime.utcnow().isoformat().encode()).hexdigest()[:10]

def _days_until(date_str: str) -> Optional[int]:
    """Days from today until a date (ignoring year — birthday/anniversary logic)."""
    try:
        dt = datetime.fromisoformat(date_str[:10])
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        # Same month/day this year
        this_year = dt.replace(year=today.year)
        if this_year < today:
            this_year = this_year.replace(year=today.year + 1)
        return (this_year - today).days
    except Exception:
        return None


_RELATIONS = ("spouse", "child", "parent", "sibling", "friend", "other")
_EVENT_TYPES = ("birthday", "anniversary", "school", "appointment", "family", "other")


class FamilyEngine:
    MODULES = ("members", "events", "notes")

    def __init__(self, base_dir: str, user_id: str = "owner") -> None:
        self._base = Path(base_dir)
        self._user = user_id
        self._lock = threading.Lock()
        self._base.mkdir(parents=True, exist_ok=True)
        for module in self.MODULES:
            p = self._path(module)
            if not p.exists():
                self._write(module, {"items": []})

    # ── Members ─────────────────────────────────────────────────────────

    def add_member(self, name: str, relation: str = "other",
                   birthday: str = "", phone: str = "",
                   email: str = "", notes: str = "") -> Dict:
        return self._append("members", {
            "id": _gen_id(), "name": name, "relation": relation,
            "birthday": birthday, "phone": phone, "email": email,
            "notes": notes, "created_at": _now(),
        })

    def get_members(self) -> List[Dict]:
        items = self._read("members")["items"]
        # Annotate with days_until_birthday
        for m in items:
            if m.get("birthday"):
                m["birthday_in_days"] = _days_until(m["birthday"])
        return sorted(items, key=lambda x: x.get("name", ""))

    def update_member(self, member_id: str, **kwargs) -> Optional[Dict]:
        with self._lock:
            d = self._read("members")
            for item in d["items"]:
                if item["id"] == member_id:
                    for k, v in kwargs.items():
                        if k in ("name", "relation", "birthday", "phone", "email", "notes"):
                            item[k] = v
                    item["updated_at"] = _now()
                    self._write("members", d)
                    return item
        return None

    def delete_member(self, member_id: str) -> bool:
        return self._delete("members", member_id)

    # ── Events ──────────────────────────────────────────────────────────

    def add_event(self, title: str, date: str, event_type: str = "family",
                  members: Optional[List[str]] = None, notes: str = "",
                  repeat_yearly: bool = False) -> Dict:
        return self._append("events", {
            "id": _gen_id(), "title": title, "date": date,
            "type": event_type, "members": members or [],
            "notes": notes, "repeat_yearly": repeat_yearly,
            "done": False, "created_at": _now(),
        })

    def get_events(self, upcoming_days: int = 90) -> List[Dict]:
        items = self._read("events")["items"]
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        result = []
        for ev in items:
            if ev.get("done"):
                continue
            try:
                dt = datetime.fromisoformat(ev["date"][:10])
                if ev.get("repeat_yearly"):
                    dt = dt.replace(year=today.year)
                    if dt < today:
                        dt = dt.replace(year=today.year + 1)
                ev["days_away"] = (dt - today).days
                if ev["days_away"] <= upcoming_days:
                    result.append(ev)
            except Exception:
                result.append(ev)
        return sorted(result, key=lambda x: x.get("days_away", 9999))

    def complete_event(self, event_id: str) -> Optional[Dict]:
        return self._set_done("events", event_id)

    def delete_event(self, event_id: str) -> bool:
        return self._delete("events", event_id)

    # ── Notes ───────────────────────────────────────────────────────────

    def add_note(self, content: str, member_id: str = "",
                 tags: Optional[List[str]] = None) -> Dict:
        return self._append("notes", {
            "id": _gen_id(), "content": content,
            "member_id": member_id, "tags": tags or [],
            "created_at": _now(),
        })

    def get_notes(self, member_id: str = "", limit: int = 20) -> List[Dict]:
        items = self._read("notes")["items"]
        if member_id:
            items = [i for i in items if i.get("member_id") == member_id]
        return sorted(items, key=lambda x: x.get("created_at", ""), reverse=True)[:limit]

    def delete_note(self, note_id: str) -> bool:
        return self._delete("notes", note_id)

    # ── Summary ─────────────────────────────────────────────────────────

    def summary(self) -> Dict[str, Any]:
        members = self.get_members()
        events  = self.get_events(upcoming_days=30)
        upcoming_birthdays = [
            m for m in members
            if m.get("birthday_in_days") is not None and m["birthday_in_days"] <= 30
        ]
        return {
            "member_count":        len(members),
            "upcoming_events":     len(events),
            "upcoming_birthdays":  len(upcoming_birthdays),
            "next_event":          events[0]["title"] if events else None,
            "next_event_days":     events[0].get("days_away") if events else None,
        }

    # ── Storage ─────────────────────────────────────────────────────────

    def _path(self, module: str) -> Path:
        return self._base / f"{self._user}_{module}.json"

    def _read(self, module: str) -> Dict:
        try:
            return json.loads(self._path(module).read_text(encoding="utf-8"))
        except Exception:
            return {"items": []}

    def _write(self, module: str, data: Dict) -> None:
        self._path(module).write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _append(self, module: str, item: Dict) -> Dict:
        with self._lock:
            d = self._read(module)
            d["items"].append(item)
            if len(d["items"]) > 500:
                d["items"] = d["items"][-400:]
            self._write(module, d)
        return item

    def _set_done(self, module: str, item_id: str) -> Optional[Dict]:
        with self._lock:
            d = self._read(module)
            for item in d["items"]:
                if item["id"] == item_id:
                    item["done"] = True
                    item["completed_at"] = _now()
                    self._write(module, d)
                    return item
        return None

    def _delete(self, module: str, item_id: str) -> bool:
        with self._lock:
            d = self._read(module)
            before = len(d["items"])
            d["items"] = [i for i in d["items"] if i["id"] != item_id]
            if len(d["items"]) < before:
                self._write(module, d)
                return True
        return False
