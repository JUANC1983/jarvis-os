from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

_DEFAULT_SETTINGS: Dict[str, Any] = {
    "language":          "en-US",
    "auto_speak":        False,
    "speed":             1.0,
    "wake_word_enabled": True,
    "wake_word":         "hey jarvis",
    "use_whisper":       False,
    "voice_id":          "",
}

_MAX_HISTORY  = 200
_KEEP_HISTORY = 150


class VoiceEngine:
    """
    Per-user voice settings + command history.
    Whisper transcription is handled in main.py using the shared OpenAI client.
    """

    def __init__(self, file_path: str, user_id: str = "owner") -> None:
        self._path    = Path(file_path)
        self._user_id = user_id
        self._lock    = threading.Lock()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            self._write({"settings": dict(_DEFAULT_SETTINGS), "history": []})

    # ── settings ──────────────────────────────────────────────────────

    def get_settings(self) -> Dict[str, Any]:
        data = self._read()
        s = dict(_DEFAULT_SETTINGS)
        s.update(data.get("settings", {}))
        return s

    def update_settings(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        allowed = set(_DEFAULT_SETTINGS.keys())
        clean   = {k: v for k, v in updates.items() if k in allowed}
        with self._lock:
            data = self._read()
            s    = dict(_DEFAULT_SETTINGS)
            s.update(data.get("settings", {}))
            s.update(clean)
            data["settings"] = s
            self._write(data)
        return s

    # ── command history ───────────────────────────────────────────────

    def log_command(
        self,
        transcript: str,
        response:   str   = "",
        domain:     str   = "general",
        confidence: float = 1.0,
        source:     str   = "mic",   # "mic" | "whisper" | "text"
    ) -> Dict[str, Any]:
        entry = {
            "id":         self._gen_id(transcript),
            "ts":         datetime.utcnow().isoformat(),
            "transcript": transcript[:500],
            "response":   response[:800],
            "domain":     domain,
            "confidence": round(confidence, 2),
            "source":     source,
        }
        with self._lock:
            data = self._read()
            hist = data.get("history", [])
            hist.append(entry)
            if len(hist) > _MAX_HISTORY:
                hist = hist[-_KEEP_HISTORY:]
            data["history"] = hist
            self._write(data)
        return entry

    def get_history(
        self,
        limit:  int = 20,
        offset: int = 0,
        domain: str = "",
        source: str = "",
    ) -> Dict[str, Any]:
        data = self._read()
        hist = list(reversed(data.get("history", [])))
        if domain:
            hist = [h for h in hist if h.get("domain") == domain]
        if source:
            hist = [h for h in hist if h.get("source") == source]
        total = len(hist)
        paged = hist[offset: offset + limit]
        return {"total": total, "items": paged, "offset": offset, "limit": limit}

    def stats(self) -> Dict[str, Any]:
        data    = self._read()
        hist    = data.get("history", [])
        domains: Dict[str, int] = {}
        sources: Dict[str, int] = {}
        for h in hist:
            d = h.get("domain", "?")
            s = h.get("source", "?")
            domains[d] = domains.get(d, 0) + 1
            sources[s] = sources.get(s, 0) + 1
        return {
            "total_commands":  len(hist),
            "by_domain":       domains,
            "by_source":       sources,
            "last_command_at": hist[-1]["ts"] if hist else None,
            "settings":        self.get_settings(),
        }

    # ── internals ─────────────────────────────────────────────────────

    def _read(self) -> Dict:
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:
            return {"settings": dict(_DEFAULT_SETTINGS), "history": []}

    def _write(self, data: Dict) -> None:
        self._path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def _gen_id(text: str) -> str:
        ts = datetime.utcnow().isoformat()
        return hashlib.sha256(f"{ts}::{text}".encode()).hexdigest()[:12]
