"""
Bridge Snapshot Cache — TTL-based in-memory + disk fallback.

Two-layer cache:
  Layer 1 — in-memory dict (fast, lost on restart)
  Layer 2 — JSON files in data/bridge/snapshots/ (survives restart)

Staleness logic:
  - Data is "fresh"  if age < FRESH_TTL  (default 30s)
  - Data is "stale"  if age < STALE_MAX  (default 300s) — returned with _stale=True
  - Data is "expired" if age >= STALE_MAX — disk fallback tried, then empty response

All returned dicts include:
  _stale         : bool
  _stale_age_sec : int (seconds since last refresh)
  _cache_source  : "memory" | "disk" | "none"
"""
from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

log = logging.getLogger("jarvis.bridge.cache")

_CACHE_DIR  = Path("data/bridge/snapshots")
_FRESH_TTL  = 30    # seconds — data considered live
_STALE_MAX  = 300   # seconds — data too old to serve even as stale


class CacheEntry:
    __slots__ = ("data", "written_at")

    def __init__(self, data: Dict[str, Any]) -> None:
        self.data       = data
        self.written_at = time.monotonic()

    @property
    def age(self) -> float:
        return time.monotonic() - self.written_at

    def is_fresh(self, ttl: float = _FRESH_TTL) -> bool:
        return self.age < ttl

    def is_usable(self, max_age: float = _STALE_MAX) -> bool:
        return self.age < max_age


class SnapshotCache:
    """Thread-safe dual-layer snapshot cache."""

    def __init__(
        self,
        fresh_ttl: int = _FRESH_TTL,
        stale_max: int = _STALE_MAX,
    ) -> None:
        self._fresh_ttl = fresh_ttl
        self._stale_max = stale_max
        self._memory: Dict[str, CacheEntry] = {}
        self._lock = threading.RLock()
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # ── Write ─────────────────────────────────────────────────────────────────

    def set(self, key: str, data: Dict[str, Any]) -> None:
        """Cache data in memory and persist to disk."""
        clean = {k: v for k, v in data.items() if not k.startswith("_stale")}
        clean["_cached_at"] = datetime.utcnow().isoformat()

        with self._lock:
            self._memory[key] = CacheEntry(clean)

        self._write_disk(key, clean)

    # ── Read ──────────────────────────────────────────────────────────────────

    def get(self, key: str) -> Tuple[Optional[Dict], bool]:
        """
        Returns (data, is_stale).
        data is None only when nothing exists anywhere.
        """
        with self._lock:
            entry = self._memory.get(key)

        if entry:
            if entry.is_fresh(self._fresh_ttl):
                return self._annotate(entry.data, stale=False, age=entry.age, source="memory"), False
            if entry.is_usable(self._stale_max):
                return self._annotate(entry.data, stale=True, age=entry.age, source="memory"), True

        # Memory miss or expired — try disk
        disk_data, disk_age = self._read_disk(key)
        if disk_data is not None:
            if disk_age < self._stale_max:
                # Warm memory cache from disk
                with self._lock:
                    entry = CacheEntry(disk_data)
                    entry.written_at = time.monotonic() - disk_age
                    self._memory[key] = entry
                return self._annotate(disk_data, stale=True, age=disk_age, source="disk"), True

        return None, True  # no data at all

    def get_fresh_or_stale(self, key: str) -> Dict[str, Any]:
        """
        Convenience: always returns a dict (may have _stale=True).
        Returns empty dict with _stale=True if nothing cached.
        """
        data, is_stale = self.get(key)
        if data is None:
            return {
                "_stale":         True,
                "_stale_age_sec": -1,
                "_cache_source":  "none",
                "status":         "no_cache",
            }
        return data

    def is_fresh(self, key: str) -> bool:
        with self._lock:
            entry = self._memory.get(key)
        if entry:
            return entry.is_fresh(self._fresh_ttl)
        _, age = self._read_disk(key)
        return age is not None and age < self._fresh_ttl

    def invalidate(self, key: str) -> None:
        with self._lock:
            self._memory.pop(key, None)
        disk_path = _CACHE_DIR / f"{key}.json"
        if disk_path.exists():
            try:
                disk_path.unlink()
            except Exception:
                pass

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            keys = list(self._memory.keys())
        return {
            "keys_in_memory": len(keys),
            "keys":           keys,
            "fresh_ttl":      self._fresh_ttl,
            "stale_max":      self._stale_max,
        }

    # ── Disk helpers ──────────────────────────────────────────────────────────

    def _write_disk(self, key: str, data: Dict) -> None:
        path = _CACHE_DIR / f"{_safe_key(key)}.json"
        try:
            path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
        except Exception as exc:
            log.warning("Cache disk write failed key=%s: %s", key, exc)

    def _read_disk(self, key: str) -> Tuple[Optional[Dict], float]:
        """Returns (data, age_seconds) or (None, inf)."""
        path = _CACHE_DIR / f"{_safe_key(key)}.json"
        if not path.exists():
            return None, float("inf")
        try:
            stat = path.stat()
            age  = time.time() - stat.st_mtime
            data = json.loads(path.read_text(encoding="utf-8"))
            return data, age
        except Exception as exc:
            log.warning("Cache disk read failed key=%s: %s", key, exc)
            return None, float("inf")

    # ── Annotation helper ─────────────────────────────────────────────────────

    @staticmethod
    def _annotate(
        data: Dict,
        stale: bool,
        age: float,
        source: str,
    ) -> Dict:
        annotated = dict(data)
        annotated["_stale"]         = stale
        annotated["_stale_age_sec"] = round(age)
        annotated["_cache_source"]  = source
        return annotated


def _safe_key(key: str) -> str:
    """Sanitise cache key for use as a filename."""
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in key)


# Singleton
snapshot_cache = SnapshotCache()
