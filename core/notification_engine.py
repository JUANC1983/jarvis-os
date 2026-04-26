from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

_PRIORITY_LEVELS = {"low", "medium", "high", "critical"}
_VALID_TYPES     = {"task_reminder", "meeting_alert", "ai_insight", "system_alert", "general"}
_MAX_STORED      = 200   # hard cap; oldest read notifications pruned first
_PRUNE_KEEP      = 150


class NotificationEngine:
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

    # ── pruning ──────────────────────────────────────────────────────

    def _prune_if_needed(self, notifs: List[Dict]) -> List[Dict]:
        if len(notifs) < _MAX_STORED:
            return notifs
        # Read notifications are expendable — prune oldest-read first
        read    = sorted([n for n in notifs if n.get("read")],  key=lambda n: n.get("created_at", ""))
        unread  = sorted([n for n in notifs if not n.get("read")], key=lambda n: n.get("created_at", ""))
        combined = read + unread          # read at front = pruned first
        return combined[len(combined) - _PRUNE_KEEP:]

    # ── deduplication key ────────────────────────────────────────────

    @staticmethod
    def _dedup_key(title: str, notif_type: str, source_id: str) -> str:
        return f"{notif_type}::{title.strip().lower()}::{source_id or ''}"

    # ── CRUD ─────────────────────────────────────────────────────────

    def create(
        self,
        title:     str,
        message:   str = "",
        notif_type: str = "general",
        priority:  str = "medium",
        source_id: str = "",       # e.g. task id, event id
        action_url: str = "",      # optional deep-link (tab#section)
        deduplicate: bool = True,
    ) -> Dict[str, Any]:
        if not title.strip():
            raise ValueError("title required")
        notif_type = notif_type if notif_type in _VALID_TYPES else "general"
        priority   = priority   if priority   in _PRIORITY_LEVELS else "medium"

        notifs = self._read()

        if deduplicate:
            dk = self._dedup_key(title, notif_type, source_id)
            # Only deduplicate against unread notifications
            for n in notifs:
                if n.get("dedup_key") == dk and not n.get("read"):
                    return n   # already queued, skip

        now = datetime.utcnow().isoformat()
        item: Dict[str, Any] = {
            "id":         f"ntf_{uuid4().hex[:10]}",
            "title":      title.strip(),
            "message":    message.strip(),
            "type":       notif_type,
            "priority":   priority,
            "source_id":  source_id,
            "action_url": action_url,
            "dedup_key":  self._dedup_key(title, notif_type, source_id),
            "read":       False,
            "created_at": now,
            "read_at":    None,
        }

        notifs.append(item)
        notifs = self._prune_if_needed(notifs)
        # Sort: newest first for storage
        notifs.sort(key=lambda n: n.get("created_at", ""), reverse=True)
        self._write(notifs)
        return item

    def list_notifications(
        self,
        unread_only: bool = False,
        limit:       int  = 50,
        offset:      int  = 0,
        notif_type:  str  = "",
        priority:    str  = "",
    ) -> Dict[str, Any]:
        notifs = self._read()

        # Priority sort order
        _prio_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        notifs.sort(key=lambda n: (
            n.get("read", False),
            _prio_order.get(n.get("priority", "medium"), 2),
            n.get("created_at", ""),
        ))

        filtered = notifs
        if unread_only:
            filtered = [n for n in filtered if not n.get("read")]
        if notif_type and notif_type in _VALID_TYPES:
            filtered = [n for n in filtered if n.get("type") == notif_type]
        if priority and priority in _PRIORITY_LEVELS:
            filtered = [n for n in filtered if n.get("priority") == priority]

        total  = len(filtered)
        unread = sum(1 for n in notifs if not n.get("read"))
        page   = filtered[offset: offset + limit]

        return {
            "total":  total,
            "unread": unread,
            "offset": offset,
            "limit":  limit,
            "notifications": page,
        }

    def mark_read(self, notif_id: str) -> Dict[str, Any]:
        notifs = self._read()
        for n in notifs:
            if n.get("id") == notif_id:
                n["read"]    = True
                n["read_at"] = datetime.utcnow().isoformat()
                self._write(notifs)
                return n
        raise ValueError(f"notification '{notif_id}' not found")

    def mark_all_read(self) -> int:
        notifs = self._read()
        now = datetime.utcnow().isoformat()
        count = 0
        for n in notifs:
            if not n.get("read"):
                n["read"]    = True
                n["read_at"] = now
                count += 1
        self._write(notifs)
        return count

    def delete(self, notif_id: str) -> bool:
        notifs = self._read()
        before = len(notifs)
        notifs = [n for n in notifs if n.get("id") != notif_id]
        if len(notifs) == before:
            return False
        self._write(notifs)
        return True

    def unread_count(self) -> int:
        return sum(1 for n in self._read() if not n.get("read"))

    # ── convenience creators (called by other engines) ───────────────

    def notify_task_due(self, task_title: str, task_id: str = "", due_date: str = "") -> Dict:
        msg = f"Due: {due_date}" if due_date else "Task is due soon"
        return self.create(
            title=f"Task due: {task_title}",
            message=msg,
            notif_type="task_reminder",
            priority="high",
            source_id=task_id,
            action_url="projects",
        )

    def notify_meeting(self, meeting_title: str, meeting_id: str = "", time_str: str = "") -> Dict:
        msg = f"Starting at {time_str}" if time_str else "Meeting coming up"
        return self.create(
            title=f"Meeting: {meeting_title}",
            message=msg,
            notif_type="meeting_alert",
            priority="high",
            source_id=meeting_id,
            action_url="productivity",
        )

    def notify_ai_insight(self, insight: str, priority: str = "medium") -> Dict:
        return self.create(
            title="AI Insight",
            message=insight[:200],
            notif_type="ai_insight",
            priority=priority,
            action_url="agents",
        )

    def notify_system(self, message: str, priority: str = "low") -> Dict:
        return self.create(
            title="System",
            message=message,
            notif_type="system_alert",
            priority=priority,
        )
