"""
JARVIS System Event Stream — Phase 8.

Institutional-grade operational event log.
Ring buffer (1 000 events) + JSON file persistence.
Supports severity filtering, search, deduplication, and
WebSocket broadcast for live tail.
"""
from __future__ import annotations

import json
import logging
import threading
import uuid
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

log = logging.getLogger("jarvis.event_stream")

# ── Constants ─────────────────────────────────────────────────────────────────

_RING_SIZE     = 1_000
_PERSIST_PATH  = Path("data/telemetry/events.json")
_PERSIST_LIMIT = 500   # keep last N in the persisted file
_DEDUP_WINDOW  = 5     # seconds — suppress exact-duplicate messages

# ── Severity levels (ordered) ─────────────────────────────────────────────────

SEVERITY_ORDER = ["INFO", "WARNING", "CRITICAL", "SYSTEM", "SECURITY",
                  "TRADING", "EXECUTION", "AI", "NETWORK"]

_SEVERITY_WEIGHT = {s: i for i, s in enumerate(SEVERITY_ORDER)}

# ── Event dataclass (plain dict — JSON serialisable) ─────────────────────────

def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _make_event(
    severity: str,
    category: str,
    source: str,
    message: str,
    details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "event_id":  str(uuid.uuid4())[:12],
        "timestamp": _utcnow(),
        "severity":  severity.upper(),
        "category":  category,
        "source":    source,
        "message":   message,
        "details":   details or {},
        "count":     1,
    }


# ── Stream ────────────────────────────────────────────────────────────────────

class SystemEventStream:
    """Thread-safe event ring buffer with persistence and WebSocket fanout."""

    def __init__(self) -> None:
        self._ring: deque[Dict[str, Any]] = deque(maxlen=_RING_SIZE)
        self._lock = threading.Lock()
        self._ws_listeners: List[Callable[[Dict], None]] = []
        self._last_by_key: Dict[str, float] = {}   # dedup
        self._load_persisted()

    # ── Public API ────────────────────────────────────────────────────────────

    def emit(
        self,
        message: str,
        severity: str = "INFO",
        category: str = "system",
        source: str   = "jarvis",
        details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Add an event. Deduplicates within _DEDUP_WINDOW seconds."""
        now = datetime.now(timezone.utc).timestamp()
        dedup_key = f"{severity}|{source}|{message}"

        with self._lock:
            last_ts = self._last_by_key.get(dedup_key, 0)
            if now - last_ts < _DEDUP_WINDOW:
                # Increment count on the most recent matching event
                for ev in reversed(self._ring):
                    if (ev["source"] == source and
                            ev["message"] == message and
                            ev["severity"] == severity.upper()):
                        ev["count"] += 1
                        return ev
            self._last_by_key[dedup_key] = now
            event = _make_event(severity, category, source, message, details)
            self._ring.append(event)

        self._persist_async()
        self._fanout(event)
        return event

    def events(
        self,
        limit: int = 100,
        severity: Optional[str] = None,
        category: Optional[str] = None,
        source:   Optional[str] = None,
        search:   Optional[str] = None,
        since:    Optional[str] = None,   # ISO timestamp
    ) -> List[Dict[str, Any]]:
        """Return recent events, newest first, with optional filters."""
        with self._lock:
            items = list(self._ring)

        # Filters
        if severity:
            sev_upper = severity.upper()
            items = [e for e in items if e["severity"] == sev_upper]
        if category:
            items = [e for e in items if e["category"] == category]
        if source:
            src_lower = source.lower()
            items = [e for e in items if src_lower in e["source"].lower()]
        if search:
            kw = search.lower()
            items = [e for e in items
                     if kw in e["message"].lower()
                     or kw in json.dumps(e["details"]).lower()]
        if since:
            items = [e for e in items if e["timestamp"] >= since]

        return list(reversed(items))[:limit]

    def summary(self) -> Dict[str, Any]:
        with self._lock:
            items = list(self._ring)
        total = len(items)
        by_severity: Dict[str, int] = {}
        for ev in items:
            by_severity[ev["severity"]] = by_severity.get(ev["severity"], 0) + 1
        latest = items[-1] if items else None
        return {
            "total":       total,
            "by_severity": by_severity,
            "latest":      latest,
        }

    def export_json(self) -> str:
        """Export all in-ring events as JSON string."""
        with self._lock:
            items = list(self._ring)
        return json.dumps(items, indent=2)

    def register_ws_listener(self, cb: Callable[[Dict], None]) -> None:
        with self._lock:
            self._ws_listeners.append(cb)

    def unregister_ws_listener(self, cb: Callable[[Dict], None]) -> None:
        with self._lock:
            try:
                self._ws_listeners.remove(cb)
            except ValueError:
                pass

    # ── Persistence ───────────────────────────────────────────────────────────

    def _load_persisted(self) -> None:
        try:
            if _PERSIST_PATH.exists():
                data = json.loads(_PERSIST_PATH.read_text(encoding="utf-8"))
                for ev in data[-_RING_SIZE:]:
                    self._ring.append(ev)
                log.debug("EventStream: loaded %d persisted events", len(data))
        except Exception as exc:
            log.warning("EventStream: could not load persisted events: %s", exc)

    def _persist_async(self) -> None:
        t = threading.Thread(target=self._persist, daemon=True)
        t.start()

    def _persist(self) -> None:
        try:
            _PERSIST_PATH.parent.mkdir(parents=True, exist_ok=True)
            with self._lock:
                items = list(self._ring)[-_PERSIST_LIMIT:]
            _PERSIST_PATH.write_text(json.dumps(items, indent=2), encoding="utf-8")
        except Exception as exc:
            log.debug("EventStream: persist failed: %s", exc)

    # ── WebSocket fanout ──────────────────────────────────────────────────────

    def _fanout(self, event: Dict[str, Any]) -> None:
        with self._lock:
            listeners = list(self._ws_listeners)
        for cb in listeners:
            try:
                cb(event)
            except Exception:
                pass


# ── Singleton ─────────────────────────────────────────────────────────────────

system_events = SystemEventStream()
