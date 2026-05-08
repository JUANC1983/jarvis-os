"""
JARVIS System Health Monitor — Phase 8.

Continuous health checks for all platform services.
Background thread polls every POLL_INTERVAL seconds.
State transitions are emitted to SystemEventStream.

Service states:
  healthy  🟢  — operating normally
  degraded 🟡  — available but impaired
  fallback 🟠  — operating on fallback path
  offline  🔴  — service unreachable / down
  starting 🔵  — coming up
  unknown  ⚫  — not yet checked / not configured

Probe registration:
  main.py registers in-process probes via:
    system_health.register_probe("service_id", callable)
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

log = logging.getLogger("jarvis.health_monitor")

_POLL_INTERVAL = 30   # seconds

# ── State ─────────────────────────────────────────────────────────────────────

STATE_HEALTHY  = "healthy"
STATE_DEGRADED = "degraded"
STATE_FALLBACK = "fallback"
STATE_OFFLINE  = "offline"
STATE_STARTING = "starting"
STATE_UNKNOWN  = "unknown"

STATE_EMOJI = {
    STATE_HEALTHY:  "🟢",
    STATE_DEGRADED: "🟡",
    STATE_FALLBACK: "🟠",
    STATE_OFFLINE:  "🔴",
    STATE_STARTING: "🔵",
    STATE_UNKNOWN:  "⚫",
}

# ── ServiceHealth record ──────────────────────────────────────────────────────

@dataclass
class ServiceHealth:
    service_id:         str
    display_name:       str
    category:           str       # broker / market / ai / data / infra / trading
    state:              str       = STATE_UNKNOWN
    latency_ms:         Optional[float] = None
    last_heartbeat:     Optional[str]   = None    # ISO UTC
    last_error:         Optional[str]   = None
    uptime_seconds:     int             = 0
    reconnect_attempts: int             = 0
    fallback_active:    bool            = False
    fallback_mode:      Optional[str]   = None
    source:             Optional[str]   = None
    dependencies:       List[str]       = field(default_factory=list)
    metadata:           Dict[str, Any]  = field(default_factory=dict)
    checked_at:         str             = field(default_factory=lambda: _utcnow())

    def to_dict(self) -> Dict:
        d = asdict(self)
        d["emoji"] = STATE_EMOJI.get(self.state, "⚫")
        return d


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _elapsed_s(iso_ts: Optional[str]) -> Optional[float]:
    """Seconds since an ISO UTC timestamp."""
    if not iso_ts:
        return None
    try:
        t = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - t).total_seconds()
    except Exception:
        return None


# ── Health Monitor ────────────────────────────────────────────────────────────

class HealthMonitor:

    def __init__(self) -> None:
        self._lock    = threading.Lock()
        self._states: Dict[str, ServiceHealth] = {}
        self._probes: Dict[str, Callable[[], Dict[str, Any]]] = {}
        self._started_at  = time.monotonic()
        self._poll_thread: Optional[threading.Thread] = None
        self._running = False
        self._event_cb: Optional[Callable[..., Any]] = None   # injected by main
        self._init_services()

    # ── Service catalogue ─────────────────────────────────────────────────────

    def _init_services(self) -> None:
        catalogue: List[Tuple[str, str, str, List[str]]] = [
            # (service_id, display_name, category, dependencies)
            ("ibkr_gateway",       "IBKR Gateway",          "broker",   []),
            ("market_data",        "Market Data Feed",       "market",   ["ibkr_gateway"]),
            ("autonomous_trader",  "Autonomous Trader",      "trading",  ["market_data"]),
            ("paper_trader",       "Paper Trader",           "trading",  []),
            ("signal_engine",      "Signal Engine",          "trading",  ["market_data"]),
            ("portfolio_engine",   "Portfolio Engine",       "trading",  ["ibkr_gateway"]),
            ("risk_engine",        "Risk Engine",            "trading",  ["portfolio_engine"]),
            ("strategy_engine",    "Strategy Engine",        "trading",  ["signal_engine"]),
            ("openai_api",         "OpenAI API",             "ai",       []),
            ("claude_api",         "Claude / Anthropic API", "ai",       []),
            ("memory_system",      "Vector Memory",          "ai",       []),
            ("calendar",           "Calendar Integration",   "data",     []),
            ("outlook_email",      "Outlook / Email",        "data",     []),
            ("news_ingestion",     "News Ingestion",         "data",     []),
            ("webhook_listener",   "Webhook Listener",       "infra",    []),
            ("scheduler_jobs",     "Scheduler / Jobs",       "infra",    []),
            ("notification_svc",   "Notification Service",   "infra",    []),
            ("voice_subsystem",    "Voice Subsystem",        "infra",    []),
        ]
        for sid, name, cat, deps in catalogue:
            self._states[sid] = ServiceHealth(
                service_id=sid, display_name=name,
                category=cat, dependencies=deps,
            )

    # ── Probe registration ────────────────────────────────────────────────────

    def register_probe(self, service_id: str, probe: Callable[[], Dict[str, Any]]) -> None:
        """Register an in-process probe function for a service.

        The probe must return a dict with at minimum:
          {"state": "healthy"|"degraded"|"offline"|..., "source": str}
        Optional keys: latency_ms, last_heartbeat, fallback_active,
                       fallback_mode, last_error, reconnect_attempts, metadata
        """
        with self._lock:
            self._probes[service_id] = probe

    def set_event_emitter(self, cb: Callable[..., Any]) -> None:
        """Inject the event stream emitter (avoids circular import)."""
        self._event_cb = cb

    # ── Public API ────────────────────────────────────────────────────────────

    def get_all(self) -> Dict[str, Dict]:
        with self._lock:
            return {sid: sh.to_dict() for sid, sh in self._states.items()}

    def get_service(self, service_id: str) -> Optional[Dict]:
        with self._lock:
            sh = self._states.get(service_id)
            return sh.to_dict() if sh else None

    def snapshot(self) -> Dict[str, Any]:
        all_states = self.get_all()
        counts: Dict[str, int] = {}
        for sh in all_states.values():
            counts[sh["state"]] = counts.get(sh["state"], 0) + 1
        uptime_s = int(time.monotonic() - self._started_at)
        return {
            "services":    all_states,
            "counts":      counts,
            "total":       len(all_states),
            "uptime_secs": uptime_s,
            "checked_at":  _utcnow(),
        }

    # ── Background polling ────────────────────────────────────────────────────

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._poll_thread = threading.Thread(
            target=self._poll_loop,
            name="jarvis-health-monitor",
            daemon=True,
        )
        self._poll_thread.start()
        log.info("HealthMonitor started (interval=%ss)", _POLL_INTERVAL)

    def stop(self) -> None:
        self._running = False

    def _poll_loop(self) -> None:
        while self._running:
            try:
                self._run_all_checks()
            except Exception as exc:
                log.error("HealthMonitor poll error: %s", exc)
            time.sleep(_POLL_INTERVAL)

    # ── Check orchestrator ────────────────────────────────────────────────────

    def _run_all_checks(self) -> None:
        checks: Dict[str, Callable[[], ServiceHealth]] = {
            "ibkr_gateway":      self._check_ibkr_gateway,
            "market_data":       self._check_market_data,
            "autonomous_trader": self._check_autonomous_trader,
            "paper_trader":      self._check_paper_trader,
            "signal_engine":     self._check_signal_engine,
            "portfolio_engine":  self._check_portfolio_engine,
            "risk_engine":       self._check_risk_engine,
            "strategy_engine":   self._check_strategy_engine,
            "openai_api":        self._check_openai_api,
            "claude_api":        self._check_claude_api,
            "memory_system":     self._check_memory_system,
            "calendar":          self._check_calendar,
            "outlook_email":     self._check_outlook_email,
            "news_ingestion":    self._check_news_ingestion,
            "webhook_listener":  self._check_webhook_listener,
            "scheduler_jobs":    self._check_scheduler_jobs,
            "notification_svc":  self._check_notification_svc,
            "voice_subsystem":   self._check_voice_subsystem,
        }
        for sid, check_fn in checks.items():
            try:
                # Registered probe overrides built-in check for in-process state
                probe = self._probes.get(sid)
                if probe:
                    result = probe()
                    new_health = self._apply_probe_result(sid, result)
                else:
                    new_health = check_fn()
                self._update_state(sid, new_health)
            except Exception as exc:
                log.debug("Health check failed for %s: %s", sid, exc)
                with self._lock:
                    sh = self._states[sid]
                    sh.state      = STATE_UNKNOWN
                    sh.last_error = str(exc)[:200]
                    sh.checked_at = _utcnow()

    def _apply_probe_result(self, sid: str, result: Dict) -> ServiceHealth:
        with self._lock:
            sh = self._states[sid]
        sh.state              = result.get("state", STATE_UNKNOWN)
        sh.latency_ms         = result.get("latency_ms")
        sh.last_heartbeat     = result.get("last_heartbeat") or _utcnow()
        sh.last_error         = result.get("last_error")
        sh.fallback_active    = result.get("fallback_active", False)
        sh.fallback_mode      = result.get("fallback_mode")
        sh.source             = result.get("source")
        sh.reconnect_attempts = result.get("reconnect_attempts", sh.reconnect_attempts)
        sh.metadata           = result.get("metadata", {})
        sh.checked_at         = _utcnow()
        if sh.state == STATE_HEALTHY:
            sh.last_error = None
        return sh

    def _update_state(self, sid: str, new_health: ServiceHealth) -> None:
        with self._lock:
            old_state = self._states[sid].state
            self._states[sid] = new_health
        if old_state != new_health.state and self._event_cb:
            sev = "WARNING" if new_health.state in (STATE_DEGRADED, STATE_FALLBACK) \
                  else "CRITICAL" if new_health.state == STATE_OFFLINE \
                  else "INFO"
            self._event_cb(
                f"{new_health.display_name} → {new_health.state.upper()}",
                severity=sev, category="system",
                source=sid,
                details={"previous": old_state, "current": new_health.state,
                         "error": new_health.last_error},
            )

    # ── Individual service checks ─────────────────────────────────────────────

    def _check_ibkr_gateway(self) -> ServiceHealth:
        sh = self._clone("ibkr_gateway")
        bridge_url  = os.getenv("IBKR_BRIDGE_URL", "")
        bridge_tok  = os.getenv("IBKR_BRIDGE_TOKEN", "")
        remote_mode = os.getenv("ENABLE_REMOTE_IBKR_BRIDGE", "").lower() == "true"
        railway     = bool(os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RAILWAY_STATIC_URL"))

        if not bridge_url and not railway and not remote_mode:
            sh.state  = STATE_UNKNOWN
            sh.source = "not_configured"
            sh.metadata["note"] = "Local dev mode — IBKR bridge not enabled"
        elif not bridge_url:
            sh.state     = STATE_OFFLINE
            sh.last_error = "IBKR_BRIDGE_URL not set"
            sh.source     = "not_configured"
        elif not bridge_tok:
            sh.state     = STATE_DEGRADED
            sh.last_error = "IBKR_BRIDGE_TOKEN not set"
            sh.source     = "partially_configured"
        else:
            # Try a quick HEAD/GET to bridge health
            t0 = time.monotonic()
            try:
                import httpx
                resp = httpx.get(f"{bridge_url.rstrip('/')}/health",
                                 timeout=4.0,
                                 headers={"X-Bridge-Token": bridge_tok})
                ms = (time.monotonic() - t0) * 1000
                if resp.status_code == 200:
                    sh.state        = STATE_HEALTHY
                    sh.latency_ms   = round(ms, 1)
                    sh.last_heartbeat = _utcnow()
                    sh.source       = "ibkr_remote_bridge"
                else:
                    sh.state      = STATE_DEGRADED
                    sh.last_error = f"Bridge HTTP {resp.status_code}"
                    sh.latency_ms = round(ms, 1)
            except Exception as exc:
                sh.state      = STATE_OFFLINE
                sh.last_error = f"Bridge unreachable: {str(exc)[:100]}"
        sh.checked_at = _utcnow()
        return sh

    def _check_market_data(self) -> ServiceHealth:
        sh = self._clone("market_data")
        snap_path = Path("data/bridge/snapshots/market.json")
        if snap_path.exists():
            try:
                age_s = time.time() - snap_path.stat().st_mtime
                data  = json.loads(snap_path.read_text(encoding="utf-8"))
                source = data.get("source", "unknown")
                if age_s < 120:
                    sh.state = STATE_HEALTHY
                elif age_s < 600:
                    sh.state = STATE_DEGRADED
                    sh.fallback_active = True
                    sh.fallback_mode   = "cached_snapshot"
                else:
                    sh.state = STATE_FALLBACK
                    sh.fallback_active = True
                    sh.fallback_mode   = "stale_snapshot"
                sh.last_heartbeat = _utcnow()
                sh.source         = source
                sh.metadata["snapshot_age_s"] = round(age_s, 0)
            except Exception as exc:
                sh.state      = STATE_DEGRADED
                sh.last_error = str(exc)[:100]
        else:
            # No snapshot yet — try yfinance availability
            try:
                import yfinance as yf
                spy = yf.Ticker("SPY")
                info = spy.fast_info
                price = getattr(info, "last_price", None)
                if price and price > 0:
                    sh.state  = STATE_FALLBACK
                    sh.source = "yfinance"
                    sh.fallback_active = True
                    sh.fallback_mode   = "yfinance_only"
                    sh.last_heartbeat  = _utcnow()
                else:
                    sh.state = STATE_OFFLINE
            except Exception as exc:
                sh.state      = STATE_OFFLINE
                sh.last_error = str(exc)[:100]
        sh.checked_at = _utcnow()
        return sh

    def _check_autonomous_trader(self) -> ServiceHealth:
        sh = self._clone("autonomous_trader")
        try:
            from core.autonomous_paper_trader import autonomous_trader as _atp
            status = _atp.get_status()
            if status.get("running"):
                sh.state  = STATE_HEALTHY
                sh.source = "in_process"
                sh.last_heartbeat = _utcnow()
                sh.metadata = {
                    "regime":       status.get("current_regime"),
                    "scan_count":   status.get("scan_count", 0),
                    "trades":       status.get("trades_this_session", 0),
                    "interval_secs": status.get("scan_interval_secs"),
                }
            else:
                sh.state  = STATE_OFFLINE
                sh.source = "in_process"
                sh.last_error = "Trader not running"
        except Exception as exc:
            sh.state      = STATE_UNKNOWN
            sh.last_error = str(exc)[:100]
        sh.checked_at = _utcnow()
        return sh

    def _check_paper_trader(self) -> ServiceHealth:
        sh = self._clone("paper_trader")
        pp = Path("data/portfolio/paper_positions.json")
        if pp.exists():
            try:
                data = json.loads(pp.read_text(encoding="utf-8"))
                sh.state  = STATE_HEALTHY
                sh.source = "local_file"
                sh.last_heartbeat = _utcnow()
                pos_count = len(data.get("positions", {}).get("open", {}))
                sh.metadata["open_positions"] = pos_count
            except Exception as exc:
                sh.state      = STATE_DEGRADED
                sh.last_error = str(exc)[:100]
        else:
            sh.state  = STATE_HEALTHY
            sh.source = "local_file"
            sh.last_heartbeat = _utcnow()
            sh.metadata["note"] = "No positions file yet (first run)"
        sh.checked_at = _utcnow()
        return sh

    def _check_signal_engine(self) -> ServiceHealth:
        sh = self._clone("signal_engine")
        signal_path = Path("data/learning/signal_outcomes.json")
        try:
            if signal_path.exists():
                data  = json.loads(signal_path.read_text(encoding="utf-8"))
                count = len(data.get("outcomes", []))
                sh.state  = STATE_HEALTHY if count > 0 else STATE_DEGRADED
                sh.source = "local_learning"
                sh.metadata["outcome_count"] = count
                sh.last_heartbeat = _utcnow()
            else:
                sh.state  = STATE_STARTING
                sh.source = "no_data_yet"
        except Exception as exc:
            sh.state      = STATE_DEGRADED
            sh.last_error = str(exc)[:100]
        sh.checked_at = _utcnow()
        return sh

    def _check_portfolio_engine(self) -> ServiceHealth:
        sh = self._clone("portfolio_engine")
        snap = Path("data/bridge/snapshots/market.json")
        try:
            if snap.exists():
                data = json.loads(snap.read_text(encoding="utf-8"))
                positions = data.get("positions") or data.get("portfolio")
                sh.state  = STATE_HEALTHY if positions else STATE_DEGRADED
                sh.source = "bridge_snapshot"
                sh.last_heartbeat = _utcnow()
            else:
                sh.state     = STATE_FALLBACK
                sh.fallback_active = True
                sh.fallback_mode   = "no_live_data"
                sh.source     = "not_configured"
        except Exception as exc:
            sh.state      = STATE_DEGRADED
            sh.last_error = str(exc)[:100]
        sh.checked_at = _utcnow()
        return sh

    def _check_risk_engine(self) -> ServiceHealth:
        sh = self._clone("risk_engine")
        try:
            from opsx.stability.production_rules import PRODUCTION_RULES
            sh.state  = STATE_HEALTHY
            sh.source = "production_rules"
            sh.last_heartbeat = _utcnow()
            sh.metadata["rule_count"] = len(PRODUCTION_RULES) if hasattr(PRODUCTION_RULES, "__len__") else "loaded"
        except Exception as exc:
            sh.state      = STATE_DEGRADED
            sh.last_error = str(exc)[:100]
        sh.checked_at = _utcnow()
        return sh

    def _check_strategy_engine(self) -> ServiceHealth:
        sh = self._clone("strategy_engine")
        strategy_path = Path("data/learning/signal_outcomes.json")
        sh.state  = STATE_HEALTHY if strategy_path.exists() else STATE_STARTING
        sh.source = "learning_engine"
        sh.last_heartbeat = _utcnow()
        sh.checked_at = _utcnow()
        return sh

    def _check_openai_api(self) -> ServiceHealth:
        sh = self._clone("openai_api")
        key = os.getenv("OPENAI_API_KEY", "")
        if not key:
            sh.state     = STATE_OFFLINE
            sh.last_error = "OPENAI_API_KEY not set"
        else:
            sh.state  = STATE_HEALTHY
            sh.source = "env_key_present"
            sh.last_heartbeat = _utcnow()
            sh.metadata["key_prefix"] = key[:6] + "..."
        sh.checked_at = _utcnow()
        return sh

    def _check_claude_api(self) -> ServiceHealth:
        sh = self._clone("claude_api")
        key = os.getenv("ANTHROPIC_API_KEY", "")
        if not key:
            sh.state     = STATE_OFFLINE
            sh.last_error = "ANTHROPIC_API_KEY not set"
        else:
            sh.state  = STATE_HEALTHY
            sh.source = "env_key_present"
            sh.last_heartbeat = _utcnow()
            sh.metadata["key_prefix"] = key[:6] + "..."
        sh.checked_at = _utcnow()
        return sh

    def _check_memory_system(self) -> ServiceHealth:
        sh = self._clone("memory_system")
        mem_dir  = Path("data/memory")
        json_mem = Path("data/jarvis_memory.json")
        try:
            if mem_dir.exists():
                files = list(mem_dir.glob("*.json"))
                sh.state  = STATE_HEALTHY
                sh.source = "local_vector_json"
                sh.metadata["file_count"] = len(files)
                sh.last_heartbeat = _utcnow()
            elif json_mem.exists():
                data = json.loads(json_mem.read_text(encoding="utf-8"))
                count = len(data) if isinstance(data, list) else len(data.get("entries", []))
                sh.state  = STATE_HEALTHY
                sh.source = "local_json"
                sh.metadata["entry_count"] = count
                sh.last_heartbeat = _utcnow()
            else:
                sh.state  = STATE_STARTING
                sh.source = "no_data_yet"
        except Exception as exc:
            sh.state      = STATE_DEGRADED
            sh.last_error = str(exc)[:100]
        sh.checked_at = _utcnow()
        return sh

    def _check_calendar(self) -> ServiceHealth:
        sh = self._clone("calendar")
        cal_files = list(Path("data").glob("calendar_*.json"))
        google_key = os.getenv("GOOGLE_CLIENT_ID", "")
        if cal_files:
            sh.state  = STATE_HEALTHY
            sh.source = "local_storage"
            sh.fallback_active = not bool(google_key)
            sh.fallback_mode   = "local_only" if not google_key else None
            sh.last_heartbeat  = _utcnow()
            sh.metadata["calendar_files"] = len(cal_files)
        else:
            sh.state  = STATE_STARTING
            sh.source = "no_events_yet"
            sh.fallback_active = True
            sh.fallback_mode   = "local_only"
            sh.last_heartbeat  = _utcnow()
        sh.checked_at = _utcnow()
        return sh

    def _check_outlook_email(self) -> ServiceHealth:
        sh = self._clone("outlook_email")
        client_id  = os.getenv("MICROSOFT_CLIENT_ID", "")
        client_sec = os.getenv("MICROSOFT_CLIENT_SECRET", "")
        if not client_id or not client_sec:
            sh.state     = STATE_OFFLINE
            sh.last_error = "MICROSOFT_CLIENT_ID/SECRET not configured"
            sh.source     = "not_configured"
        else:
            token_path = Path("data/ms_token.json")
            if token_path.exists():
                try:
                    tok = json.loads(token_path.read_text(encoding="utf-8"))
                    sh.state  = STATE_HEALTHY if tok.get("access_token") else STATE_DEGRADED
                    sh.source = "ms_oauth"
                    sh.last_heartbeat = _utcnow()
                except Exception:
                    sh.state = STATE_DEGRADED
            else:
                sh.state  = STATE_DEGRADED
                sh.last_error = "No OAuth token yet — run auth flow"
                sh.source = "pending_auth"
        sh.checked_at = _utcnow()
        return sh

    def _check_news_ingestion(self) -> ServiceHealth:
        sh = self._clone("news_ingestion")
        news_cache = Path("data/news_cache.json")
        try:
            if news_cache.exists():
                age_s = time.time() - news_cache.stat().st_mtime
                sh.state  = STATE_HEALTHY if age_s < 1800 else STATE_DEGRADED
                sh.source = "rss_feeds"
                sh.last_heartbeat = _utcnow()
                sh.metadata["cache_age_s"] = round(age_s)
                if age_s >= 1800:
                    sh.fallback_active = True
                    sh.fallback_mode   = "stale_cache"
            else:
                sh.state  = STATE_STARTING
                sh.source = "no_cache_yet"
        except Exception as exc:
            sh.state      = STATE_DEGRADED
            sh.last_error = str(exc)[:100]
        sh.checked_at = _utcnow()
        return sh

    def _check_webhook_listener(self) -> ServiceHealth:
        sh = self._clone("webhook_listener")
        wh_secret = os.getenv("WEBHOOK_SECRET", "") or os.getenv("MICROSOFT_WEBHOOK_SECRET", "")
        sh.state  = STATE_HEALTHY if wh_secret else STATE_DEGRADED
        sh.source = "fastapi_route"
        sh.last_heartbeat = _utcnow()
        if not wh_secret:
            sh.fallback_active = True
            sh.fallback_mode   = "no_secret_validation"
        sh.checked_at = _utcnow()
        return sh

    def _check_scheduler_jobs(self) -> ServiceHealth:
        sh = self._clone("scheduler_jobs")
        threads = [t for t in threading.enumerate() if not t.daemon or "jarvis" in t.name.lower()]
        atp_alive = any("atp" in t.name.lower() or "autonomous" in t.name.lower()
                         for t in threading.enumerate())
        hm_alive  = any("health" in t.name.lower() for t in threading.enumerate())
        sh.state  = STATE_HEALTHY
        sh.source = "in_process_threads"
        sh.last_heartbeat = _utcnow()
        sh.metadata = {
            "total_threads":      threading.active_count(),
            "autonomous_alive":   atp_alive,
            "health_monitor_alive": hm_alive,
        }
        sh.checked_at = _utcnow()
        return sh

    def _check_notification_svc(self) -> ServiceHealth:
        sh = self._clone("notification_svc")
        try:
            from core.notification_engine import NotificationEngine
            sh.state  = STATE_HEALTHY
            sh.source = "in_process"
            sh.last_heartbeat = _utcnow()
        except Exception as exc:
            sh.state      = STATE_OFFLINE
            sh.last_error = str(exc)[:100]
        sh.checked_at = _utcnow()
        return sh

    def _check_voice_subsystem(self) -> ServiceHealth:
        sh = self._clone("voice_subsystem")
        sh.state  = STATE_UNKNOWN
        sh.source = "browser_api"
        sh.metadata["note"] = "Voice is a browser API (SpeechRecognition) — detected client-side"
        sh.checked_at = _utcnow()
        return sh

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _clone(self, service_id: str) -> ServiceHealth:
        """Return a copy of the current ServiceHealth for in-place update."""
        with self._lock:
            orig = self._states[service_id]
            import copy
            return copy.copy(orig)


# ── Singleton ─────────────────────────────────────────────────────────────────

system_health = HealthMonitor()
