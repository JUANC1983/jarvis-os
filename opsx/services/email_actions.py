"""
Action engine for Outlook emails.

CRITICAL RULE: No email is sent or deleted without an explicit API call.
All AI outputs flow through this module as suggestions awaiting human approval.
"""
from __future__ import annotations

import json
import logging
import threading
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from opsx.connectors.outlook_email import (
    delete_email  as _graph_delete,
    mark_as_read  as _graph_mark_read,
    send_reply    as _graph_send_reply,
)

log = logging.getLogger("jarvis.email_actions")


def _now() -> str:
    return datetime.utcnow().isoformat()


# ── Email store ───────────────────────────────────────────────────────────────

class EmailStore:
    """
    Thread-safe JSON-backed store for processed email records.
    Persists every write. Replace _load / _persist with DB calls to scale.
    """

    VALID_STATUSES = frozenset({
        "pending_approval", "ignored", "sent", "deleted",
        "task_created", "calendar_created",
    })

    def __init__(self, data_dir: str = "data/outlook") -> None:
        self._lock = threading.Lock()
        self._path = Path(data_dir) / "emails.json"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._data: Dict[str, Dict] = self._load()

    def _load(self) -> Dict[str, Dict]:
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _persist(self) -> None:
        self._path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def save(self, record: Dict) -> Dict:
        record_id = record.get("message_id") or _make_id(record)
        with self._lock:
            record["store_id"]   = record_id
            record["created_at"] = _now()
            self._data[record_id] = record
            self._persist()
        log.info("Email stored id=%s subject=%r status=%s",
                 record_id, record.get("subject"), record.get("status"))
        return record

    def update(self, message_id: str, **kwargs: Any) -> Optional[Dict]:
        with self._lock:
            rec = self._data.get(message_id)
            if not rec:
                return None
            rec.update(kwargs)
            rec["updated_at"] = _now()
            self._data[message_id] = rec
            self._persist()
            return rec

    def get(self, message_id: str) -> Optional[Dict]:
        return self._data.get(message_id)

    def list(
        self,
        status: Optional[str] = None,
        limit: int = 50,
        priority: Optional[str] = None,
    ) -> List[Dict]:
        items = list(self._data.values())
        if status:
            items = [e for e in items if e.get("status") == status]
        if priority:
            items = [e for e in items if e.get("priority") == priority]
        items.sort(key=lambda x: x.get("received_at") or x.get("created_at", ""), reverse=True)
        return items[:limit]

    def stats(self) -> Dict[str, Any]:
        statuses = Counter(e.get("status", "unknown") for e in self._data.values())
        priorities = Counter(e.get("priority", "medium") for e in self._data.values())
        return {
            "total":      len(self._data),
            "by_status":  dict(statuses),
            "by_priority": dict(priorities),
            "pending":    statuses.get("pending_approval", 0),
        }

    def pending_count(self) -> int:
        return sum(1 for e in self._data.values() if e.get("status") == "pending_approval")


def _make_id(record: Dict) -> str:
    import hashlib
    seed = (record.get("subject", "") + record.get("sender_email", "") + _now()).encode()
    return "em_" + hashlib.sha256(seed).hexdigest()[:10]


# Singleton
email_store = EmailStore()


# ── Action functions ──────────────────────────────────────────────────────────

async def store_processed_email(record: Dict) -> Dict:
    """
    Persist an AI-processed email record, status=pending_approval.
    This is the entry point from the processing pipeline.
    """
    return email_store.save(record)


async def send_approved_reply(
    message_id: str,
    reply_text: str,
    user_id: str = "owner",
) -> Dict:
    """
    *** CRITICAL — the ONLY path through which replies are sent. ***
    Called only when the user explicitly clicks "Send Approved Reply".
    """
    rec = email_store.get(message_id)
    if not rec:
        return {"success": False, "error": "Email record not found in store"}

    log.info(
        "SEND APPROVED REPLY message_id=%s subject=%r",
        message_id, rec.get("subject"),
    )

    success = await _graph_send_reply(message_id, reply_text, user_id)
    if success:
        email_store.update(
            message_id,
            status="sent",
            sent_reply=reply_text,
            sent_at=_now(),
        )
        await _graph_mark_read(message_id, user_id)
        return {"success": True, "message": "Reply sent"}
    return {"success": False, "error": "Microsoft Graph send failed"}


async def delete_approved_email(
    message_id: str,
    user_id: str = "owner",
) -> Dict:
    """
    *** CRITICAL — the ONLY path through which emails are deleted. ***
    Called only when the user explicitly clicks "Delete Email".
    """
    log.info("DELETE APPROVED message_id=%s", message_id)
    success = await _graph_delete(message_id, user_id)
    if success:
        email_store.update(message_id, status="deleted", deleted_at=_now())
        return {"success": True, "message": "Email deleted"}
    return {"success": False, "error": "Microsoft Graph delete failed"}


async def ignore_email(message_id: str) -> Dict:
    """Mark as ignored — no external action, no email sent, no deletion."""
    email_store.update(message_id, status="ignored", ignored_at=_now())
    log.info("Email ignored: %s", message_id)
    return {"success": True, "message": "Email ignored"}


async def mark_email_read(message_id: str, user_id: str = "owner") -> Dict:
    """Mark as read via Graph and update local store."""
    success = await _graph_mark_read(message_id, user_id)
    if success:
        email_store.update(message_id, is_read=True)
    return {"success": success}


async def update_reply_draft(message_id: str, new_draft: str) -> Dict:
    """User edited the suggested reply before approving — update local copy."""
    rec = email_store.update(message_id, final_reply=new_draft, draft_edited=True)
    return {"success": bool(rec), "message": "Draft updated" if rec else "Email not found"}


async def create_task_from_email(message_id: str) -> Dict:
    """
    Extract task data from a processed email.
    Returns task fields ready to be passed to the JARVIS task engine.
    """
    rec = email_store.get(message_id)
    if not rec:
        return {"success": False, "error": "Email record not found"}

    task = {
        "title":    f"Follow up: {rec.get('subject', 'Email task')}",
        "notes":    f"From: {rec.get('sender_name')} <{rec.get('sender_email')}>\n\n{rec.get('summary', '')}",
        "priority": rec.get("priority", "medium"),
        "source":   "email",
        "source_id": message_id,
    }
    email_store.update(message_id, status="task_created", task_created_at=_now())
    log.info("Task created from email=%s", message_id)
    return {"success": True, "task": task}


async def create_calendar_event_from_email(message_id: str) -> Dict:
    """
    Extract calendar event data from a processed email.
    Returns event fields for the JARVIS calendar engine.
    """
    rec = email_store.get(message_id)
    if not rec:
        return {"success": False, "error": "Email record not found"}

    event = {
        "title":   f"Meeting: {rec.get('subject', 'Email meeting')}",
        "notes":   rec.get("summary", ""),
        "contact": rec.get("sender_email", ""),
        "source":  "email",
    }
    email_store.update(message_id, status="calendar_created", calendar_created_at=_now())
    log.info("Calendar event prepared from email=%s", message_id)
    return {"success": True, "event": event}
