import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional

FILE = "meetings.json"


class MeetingsEngine:
    def __init__(self, file_path: str = FILE):
        self.file_path = file_path

    def _load(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self.file_path):
            return []
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except Exception:
            return []

    def _save(self, data: List[Dict[str, Any]]) -> None:
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _parse_datetime(self, value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None

        text = str(value).strip()

        formats = [
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%d %H:%M",
            "%H:%M",
        ]

        for fmt in formats:
            try:
                parsed = datetime.strptime(text, fmt)
                if fmt == "%H:%M":
                    now = datetime.now()
                    parsed = parsed.replace(year=now.year, month=now.month, day=now.day)
                return parsed
            except Exception:
                continue

        return None

    def _normalize_meeting(self, meeting: Dict[str, Any]) -> Dict[str, Any]:
        item = dict(meeting)

        item.setdefault("id", f"m_{int(datetime.utcnow().timestamp())}")
        item.setdefault("title", "")
        item.setdefault("notes", "")
        item.setdefault("created_at", datetime.utcnow().isoformat())

        if "datetime" not in item and "time" in item:
            item["datetime"] = item["time"]

        if "time" not in item and "datetime" in item:
            dt_raw = str(item["datetime"]).strip()
            parsed = self._parse_datetime(dt_raw)
            item["time"] = parsed.strftime("%H:%M") if parsed else dt_raw

        parsed = self._parse_datetime(item.get("datetime"))
        item["_sort_key"] = parsed.isoformat() if parsed else f"9999-{item.get('time', '99:99')}"

        return item

    def _sorted(self, meetings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        normalized = [self._normalize_meeting(m) for m in meetings]
        normalized.sort(key=lambda x: x.get("_sort_key", "9999"))
        for item in normalized:
            item.pop("_sort_key", None)
        return normalized

    # Compatibilidad total con lo que ya tienes
    def add_meeting(self, title: str, time_value: str, notes: str = "") -> Dict[str, Any]:
        meetings = self._load()

        item = {
            "id": f"m_{int(datetime.utcnow().timestamp())}",
            "title": title,
            "time": time_value,
            "datetime": time_value,
            "notes": notes,
            "created_at": datetime.utcnow().isoformat()
        }

        meetings.append(item)
        meetings = self._sorted(meetings)
        self._save(meetings)

        normalized = self._normalize_meeting(item)
        normalized.pop("_sort_key", None)
        return normalized

    # Nuevo método pro
    def add_meeting_datetime(self, title: str, datetime_value: str, notes: str = "") -> Dict[str, Any]:
        meetings = self._load()
        parsed = self._parse_datetime(datetime_value)

        item = {
            "id": f"m_{int(datetime.utcnow().timestamp())}",
            "title": title,
            "datetime": datetime_value,
            "time": parsed.strftime("%H:%M") if parsed else datetime_value,
            "notes": notes,
            "created_at": datetime.utcnow().isoformat()
        }

        meetings.append(item)
        meetings = self._sorted(meetings)
        self._save(meetings)

        normalized = self._normalize_meeting(item)
        normalized.pop("_sort_key", None)
        return normalized

    def get_meetings(self) -> List[Dict[str, Any]]:
        meetings = self._sorted(self._load())
        return meetings

    def get_upcoming(self) -> List[Dict[str, Any]]:
        now = datetime.now()
        meetings = self._sorted(self._load())
        upcoming: List[Dict[str, Any]] = []

        for item in meetings:
            parsed = self._parse_datetime(item.get("datetime"))
            if parsed is None:
                upcoming.append(item)
                continue
            if parsed >= now:
                upcoming.append(item)

        return upcoming

    def cleanup_past_meetings(self) -> int:
        now = datetime.now()
        meetings = self._load()
        kept: List[Dict[str, Any]] = []
        removed = 0

        for item in meetings:
            parsed = self._parse_datetime(item.get("datetime"))
            if parsed is None:
                kept.append(item)
                continue
            if parsed >= now:
                kept.append(item)
            else:
                removed += 1

        kept = self._sorted(kept)
        self._save(kept)
        return removed

