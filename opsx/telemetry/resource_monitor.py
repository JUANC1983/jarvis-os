"""
JARVIS Resource Monitor — Phase 8.

System telemetry: CPU, RAM, disk, API call counters,
request latency histograms, background job counts.

psutil is optional — if not installed, resource fields return None.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

_LATENCY_WINDOW = 500   # keep last N request latencies

# ── API call counter ──────────────────────────────────────────────────────────

class _APICounter:
    def __init__(self) -> None:
        self._lock   = threading.Lock()
        self._counts: Dict[str, int]   = {}
        self._errors: Dict[str, int]   = {}
        self._latencies: deque[float]  = deque(maxlen=_LATENCY_WINDOW)
        self._session_start = time.monotonic()

    def record(self, endpoint: str, latency_ms: float, error: bool = False) -> None:
        with self._lock:
            self._counts[endpoint]  = self._counts.get(endpoint, 0) + 1
            if error:
                self._errors[endpoint] = self._errors.get(endpoint, 0) + 1
            self._latencies.append(latency_ms)

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            lats = list(self._latencies)
            counts = dict(self._counts)
            errors = dict(self._errors)
        total = sum(counts.values())
        err_total = sum(errors.values())
        uptime = time.monotonic() - self._session_start
        avg_lat  = round(sum(lats) / len(lats), 1) if lats else None
        p95_lat  = round(sorted(lats)[int(len(lats) * 0.95)], 1) if len(lats) >= 20 else None
        top_endpoints = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:10]
        return {
            "total_requests":    total,
            "error_count":       err_total,
            "error_rate_pct":    round(err_total / total * 100, 1) if total > 0 else 0,
            "avg_latency_ms":    avg_lat,
            "p95_latency_ms":    p95_lat,
            "requests_per_min":  round(total / (uptime / 60), 1) if uptime > 0 else 0,
            "top_endpoints":     top_endpoints,
            "session_uptime_s":  int(uptime),
        }


# ── Resource Monitor ──────────────────────────────────────────────────────────

class ResourceMonitor:

    def __init__(self) -> None:
        self.api = _APICounter()
        self._started_at = time.monotonic()

    def get_system(self) -> Dict[str, Any]:
        """CPU, RAM, disk — uses psutil if available."""
        result: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        try:
            import psutil
            result["cpu_pct"]        = psutil.cpu_percent(interval=0.1)
            result["cpu_count"]      = psutil.cpu_count()
            mem = psutil.virtual_memory()
            result["ram_used_mb"]    = round(mem.used / 1024 / 1024)
            result["ram_total_mb"]   = round(mem.total / 1024 / 1024)
            result["ram_pct"]        = mem.percent
            disk = psutil.disk_usage("/")
            result["disk_used_gb"]   = round(disk.used / 1024 / 1024 / 1024, 1)
            result["disk_total_gb"]  = round(disk.total / 1024 / 1024 / 1024, 1)
            result["disk_pct"]       = disk.percent
            result["process_threads"] = len(psutil.Process().threads())
        except ImportError:
            result["psutil_unavailable"] = True
            result["cpu_pct"]  = None
            result["ram_pct"]  = None
            result["disk_pct"] = None

        import threading as _t
        result["active_threads"] = _t.active_count()
        result["uptime_secs"]    = int(time.monotonic() - self._started_at)
        return result

    def get_api(self) -> Dict[str, Any]:
        return self.api.snapshot()

    def snapshot(self) -> Dict[str, Any]:
        return {
            "system": self.get_system(),
            "api":    self.get_api(),
        }


# ── Singleton ─────────────────────────────────────────────────────────────────

resource_monitor = ResourceMonitor()
