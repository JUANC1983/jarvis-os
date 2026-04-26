from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

_MAX_HISTORY = 500        # hard cap per user
_PRUNE_KEEP  = 400        # keep this many after pruning
_PRUNE_LOW_IMPORTANCE = 3 # entries <= this score pruned first

_VALID_TYPES = {"interaction", "decision", "event", "insight", "preference"}


def _fingerprint(content: str, entry_type: str) -> str:
    """Stable hash used for deduplication."""
    return hashlib.sha256(f"{entry_type}::{content.strip().lower()}".encode()).hexdigest()[:16]


class MemoryEngine:
    def __init__(self, file_path: str | Path) -> None:
        self.path = Path(file_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write(self._empty(self.path.stem))

    # ── persistence ─────────────────────────────────────────────────

    @staticmethod
    def _empty(user_id: str) -> Dict[str, Any]:
        return {
            "user_id":      user_id,
            "preferences":  {},
            "history":      [],
            "insights":     [],
            "last_updated": datetime.utcnow().isoformat(),
        }

    def _read(self) -> Dict[str, Any]:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return self._empty(self.path.stem)

    def _write(self, data: Dict[str, Any]) -> None:
        data["last_updated"] = datetime.utcnow().isoformat()
        self.path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # ── pruning ──────────────────────────────────────────────────────

    def _prune_if_needed(self, history: List[Dict]) -> List[Dict]:
        """Remove old low-importance entries when over cap."""
        if len(history) < _MAX_HISTORY:
            return history
        # Sort: low importance + oldest first → most expendable
        history.sort(key=lambda e: (e.get("importance", 5), e.get("timestamp", "")))
        return history[len(history) - _PRUNE_KEEP:]

    # ── core: save ───────────────────────────────────────────────────

    def save(
        self,
        content:    str,
        entry_type: str = "interaction",
        importance: int = 5,
        tags:       List[str] | None = None,
        metadata:   Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """
        Save a memory entry. Deduplicates by fingerprint — returns existing
        entry (with updated importance if higher) instead of creating duplicate.
        """
        if not content.strip():
            raise ValueError("content is required")
        entry_type = entry_type if entry_type in _VALID_TYPES else "interaction"
        importance = max(1, min(10, int(importance)))

        fp = _fingerprint(content, entry_type)
        data = self._read()
        history: List[Dict] = data["history"]

        # Dedup check
        for existing in history:
            if existing.get("fingerprint") == fp:
                if importance > existing.get("importance", 5):
                    existing["importance"] = importance
                    existing["last_seen"] = datetime.utcnow().isoformat()
                    self._write(data)
                return existing

        # New entry
        entry: Dict[str, Any] = {
            "id":          f"mem_{uuid4().hex[:10]}",
            "type":        entry_type,
            "content":     content.strip(),
            "importance":  importance,
            "tags":        tags or [],
            "metadata":    metadata or {},
            "fingerprint": fp,
            "timestamp":   datetime.utcnow().isoformat(),
            "last_seen":   datetime.utcnow().isoformat(),
        }

        # Handle preference type — also write to preferences dict
        if entry_type == "preference" and metadata:
            key = metadata.get("key")
            val = metadata.get("value")
            if key:
                data["preferences"][key] = {"value": val, "updated_at": entry["timestamp"]}

        history.append(entry)
        data["history"] = self._prune_if_needed(history)
        self._write(data)
        return entry

    # ── core: context ────────────────────────────────────────────────

    def get_context(self, limit: int = 20, min_importance: int = 4) -> Dict[str, Any]:
        """
        Return context suitable for injection before an AI call.
        Prioritises importance, then recency.
        """
        data = self._read()
        history: List[Dict] = data["history"]

        # Filter by importance threshold
        eligible = [e for e in history if e.get("importance", 5) >= min_importance]

        # Sort: high importance first, then most recent
        eligible.sort(key=lambda e: (-e.get("importance", 5), e.get("timestamp", "")))
        top = eligible[:limit]

        return {
            "user_id":     data.get("user_id"),
            "preferences": data.get("preferences", {}),
            "context":     top,
            "insights":    data.get("insights", [])[-10:],
            "total_memories": len(history),
        }

    # ── core: history ────────────────────────────────────────────────

    def get_history(
        self,
        limit:      int = 50,
        offset:     int = 0,
        entry_type: str = "",
        min_importance: int = 1,
        since:      str = "",
    ) -> Dict[str, Any]:
        """Paginated history with optional filters."""
        data = self._read()
        history: List[Dict] = data["history"]

        # Apply filters
        filtered = history
        if entry_type and entry_type in _VALID_TYPES:
            filtered = [e for e in filtered if e.get("type") == entry_type]
        if min_importance > 1:
            filtered = [e for e in filtered if e.get("importance", 5) >= min_importance]
        if since:
            filtered = [e for e in filtered if e.get("timestamp", "") >= since]

        # Sort most recent first
        filtered.sort(key=lambda e: e.get("timestamp", ""), reverse=True)

        total = len(filtered)
        page  = filtered[offset: offset + limit]

        return {
            "total":   total,
            "offset":  offset,
            "limit":   limit,
            "entries": page,
        }

    # ── insights ────────────────────────────────────────────────────

    def add_insight(self, content: str, importance: int = 7) -> Dict[str, Any]:
        """Insights are separate from history — high-value persistent observations."""
        if not content.strip():
            raise ValueError("content required")
        data = self._read()
        insights: List[Dict] = data.get("insights", [])

        # Dedup
        fp = _fingerprint(content, "insight")
        for ins in insights:
            if ins.get("fingerprint") == fp:
                return ins

        entry = {
            "id":          f"ins_{uuid4().hex[:10]}",
            "content":     content.strip(),
            "importance":  max(1, min(10, int(importance))),
            "fingerprint": fp,
            "timestamp":   datetime.utcnow().isoformat(),
        }
        insights.append(entry)
        # Keep last 100 insights
        data["insights"] = insights[-100:]
        self._write(data)
        return entry

    # ── preferences ─────────────────────────────────────────────────

    def set_preference(self, key: str, value: Any) -> Dict[str, Any]:
        data = self._read()
        data["preferences"][key] = {"value": value, "updated_at": datetime.utcnow().isoformat()}
        self._write(data)
        return data["preferences"][key]

    def get_preferences(self) -> Dict[str, Any]:
        return self._read().get("preferences", {})

    # ── auto-save helpers ────────────────────────────────────────────

    def auto_save_interaction(self, user_input: str, ai_response: str, importance: int = 3) -> None:
        """Lightweight call made by chat handler — stores at low importance by default."""
        summary = f"User: {user_input[:120]} | AI: {ai_response[:120]}"
        self.save(summary, entry_type="interaction", importance=importance,
                  tags=["chat"], metadata={"raw_input": user_input[:300]})

    def auto_save_decision(self, decision: str, context: str = "", importance: int = 7) -> None:
        self.save(decision, entry_type="decision", importance=importance,
                  tags=["decision"], metadata={"context": context})

    def auto_save_event(self, event_title: str, event_id: str = "", importance: int = 5) -> None:
        self.save(f"Calendar event: {event_title}", entry_type="event", importance=importance,
                  tags=["calendar"], metadata={"event_id": event_id})

    # ── stats ────────────────────────────────────────────────────────

    def stats(self) -> Dict[str, Any]:
        data = self._read()
        history = data.get("history", [])
        by_type: Dict[str, int] = {}
        for e in history:
            t = e.get("type", "unknown")
            by_type[t] = by_type.get(t, 0) + 1
        avg_imp = (sum(e.get("importance", 5) for e in history) / len(history)) if history else 0
        return {
            "total":          len(history),
            "by_type":        by_type,
            "avg_importance": round(avg_imp, 2),
            "insights":       len(data.get("insights", [])),
            "preferences":    len(data.get("preferences", {})),
            "last_updated":   data.get("last_updated", ""),
        }
