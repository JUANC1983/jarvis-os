from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

_ALLOWED_UPDATES = {
    "title", "description", "start", "end", "timezone",
    "participants", "linked_project_id", "linked_task_id",
    "reminder_minutes",
}


class CalendarEngine:
    def __init__(self, file_path: str | Path) -> None:
        self.path = Path(file_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write([])

    # ── persistence ─────────────────────────────────────────────────

    def _read(self) -> List[Dict[str, Any]]:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _write(self, data: List[Dict[str, Any]]) -> None:
        self.path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # ── datetime helpers ─────────────────────────────────────────────

    @staticmethod
    def _parse(s: str) -> Optional[datetime]:
        if not s:
            return None
        for fmt in (
            "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M",
            "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M",
            "%Y-%m-%d",
        ):
            try:
                return datetime.strptime(s.strip(), fmt)
            except ValueError:
                pass
        return None

    @staticmethod
    def _today_range() -> tuple[datetime, datetime]:
        now = datetime.now()
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end   = start + timedelta(days=1)
        return start, end

    @staticmethod
    def _week_range() -> tuple[datetime, datetime]:
        now   = datetime.now()
        start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        end   = start + timedelta(days=7)
        return start, end

    @staticmethod
    def _month_range() -> tuple[datetime, datetime]:
        now   = datetime.now()
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if now.month == 12:
            end = start.replace(year=now.year + 1, month=1)
        else:
            end = start.replace(month=now.month + 1)
        return start, end

    # ── CRUD ─────────────────────────────────────────────────────────

    def list_events(
        self,
        range_name: str = "",
        from_date:  str = "",
        to_date:    str = "",
    ) -> List[Dict[str, Any]]:
        events = self._read()

        # Compute filter window
        from_dt: Optional[datetime] = None
        to_dt:   Optional[datetime] = None

        rn = (range_name or "").lower()
        if rn == "day":
            from_dt, to_dt = self._today_range()
        elif rn == "week":
            from_dt, to_dt = self._week_range()
        elif rn == "month":
            from_dt, to_dt = self._month_range()
        else:
            from_dt = self._parse(from_date) if from_date else None
            to_dt   = self._parse(to_date)   if to_date   else None

        filtered = []
        for ev in events:
            ev_start = self._parse(ev.get("start", ""))
            if ev_start is None:
                filtered.append(ev)
                continue
            if from_dt and ev_start < from_dt:
                continue
            if to_dt and ev_start >= to_dt:
                continue
            filtered.append(ev)

        filtered.sort(key=lambda e: e.get("start", ""))
        return filtered

    def create_event(
        self,
        title:            str,
        start:            str,
        end:              str = "",
        description:      str = "",
        timezone_str:     str = "America/Bogota",
        participants:     List[str] | None = None,
        linked_project_id: str | None = None,
        linked_task_id:   str | None = None,
        reminder_minutes: int = 30,
        duration_minutes: int = 60,
    ) -> Dict[str, Any]:
        if not title.strip():
            raise ValueError("title is required")
        start_dt = self._parse(start)
        if start_dt is None:
            raise ValueError("invalid start datetime")

        # Compute end if not given
        if not end:
            end_dt = start_dt + timedelta(minutes=duration_minutes)
            end = end_dt.strftime("%Y-%m-%dT%H:%M")
        else:
            end_dt = self._parse(end)
            if end_dt is None:
                end = (start_dt + timedelta(minutes=duration_minutes)).strftime("%Y-%m-%dT%H:%M")

        now = datetime.utcnow().isoformat()
        item: Dict[str, Any] = {
            "id":               f"ev_{uuid4().hex[:10]}",
            "title":            title.strip(),
            "description":      description.strip(),
            "start":            start,
            "end":              end,
            "timezone":         timezone_str or "America/Bogota",
            "participants":     participants or [],
            "linked_project_id": linked_project_id,
            "linked_task_id":   linked_task_id,
            "reminder_minutes": int(reminder_minutes),
            "source":           "jarvis",
            "created_at":       now,
            "updated_at":       now,
        }
        data = self._read()
        data.append(item)
        data.sort(key=lambda e: e.get("start", ""))
        self._write(data)
        return item

    def update_event(self, event_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        data = self._read()
        for ev in data:
            if ev.get("id") == event_id:
                for k, v in updates.items():
                    if k in _ALLOWED_UPDATES:
                        ev[k] = v
                ev["updated_at"] = datetime.utcnow().isoformat()
                data.sort(key=lambda e: e.get("start", ""))
                self._write(data)
                return ev
        raise ValueError(f"event '{event_id}' not found")

    def delete_event(self, event_id: str) -> bool:
        data = self._read()
        before = len(data)
        data = [e for e in data if e.get("id") != event_id]
        if len(data) == before:
            return False
        self._write(data)
        return True

    def get_today_events(self) -> List[Dict[str, Any]]:
        return self.list_events(range_name="day")

    def get_upcoming(self, limit: int = 5) -> List[Dict[str, Any]]:
        now = datetime.now()
        events = self._read()
        upcoming = [
            e for e in events
            if (self._parse(e.get("start", "")) or datetime.min) >= now
        ]
        upcoming.sort(key=lambda e: e.get("start", ""))
        return upcoming[:limit]
