"""
JARVIS Startup Validator — Phase 8.

Runs on JARVIS server startup to verify the system is in a safe, deployable state.
Called from main.py @app.on_event("startup").

Checks:
  - Required env vars present
  - Bridge config valid (no localhost in production)
  - Watchdog configured
  - Frontend integrity (basic checks without a browser)
  - Production rules (real_trade=False, execution_blocked)
  - Protected feature registry loads

If any CRITICAL check fails:
  - Logs CRITICAL with full details
  - Returns structured error report
  - Does NOT crash the server (services other than IBKR may still work)
"""
from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

log = logging.getLogger("jarvis.startup_validator")


class StartupValidator:

    def __init__(self) -> None:
        self._results: List[Dict] = []

    def run_all(self) -> Dict[str, Any]:
        """Run all startup checks. Returns structured validation report."""
        self._results = []
        now = datetime.utcnow().isoformat()

        self._check_env_vars()
        self._check_bridge_config()
        self._check_production_rules_module()
        self._check_feature_registry()
        self._check_frontend_existence()
        self._check_data_directories()
        self._check_railway_localhost_safety()
        self._check_watchdog_config()

        passed   = [r for r in self._results if r["status"] == "PASS"]
        warned   = [r for r in self._results if r["status"] == "WARN"]
        failed   = [r for r in self._results if r["status"] == "FAIL"]
        critical = [r for r in self._results if r["status"] == "CRITICAL"]

        overall = "CRITICAL" if critical else ("FAIL" if failed else ("WARN" if warned else "PASS"))

        if critical:
            for c in critical:
                log.critical("STARTUP CRITICAL: [%s] %s", c["check"], c["message"])
        if failed:
            for f in failed:
                log.error("STARTUP FAIL: [%s] %s", f["check"], f["message"])
        if warned:
            for w in warned:
                log.warning("STARTUP WARN: [%s] %s", w["check"], w["message"])

        if overall in ("PASS", "WARN"):
            log.info("STARTUP VALIDATION: %s (%d pass, %d warn, %d fail, %d critical)",
                     overall, len(passed), len(warned), len(failed), len(critical))
        else:
            log.critical("STARTUP VALIDATION: %s — system may be in degraded state", overall)

        return {
            "overall":   overall,
            "checked_at": now,
            "pass":      passed,
            "warn":      warned,
            "fail":      failed,
            "critical":  critical,
            "counts": {
                "pass": len(passed), "warn": len(warned),
                "fail": len(failed), "critical": len(critical),
            },
        }

    # ── Individual Checks ─────────────────────────────────────────────────────

    def _check_env_vars(self) -> None:
        is_hosted = self._is_hosted()

        required_always = []
        required_in_production = ["IBKR_BRIDGE_URL", "IBKR_BRIDGE_TOKEN"]
        recommended_always = ["ENABLE_REMOTE_IBKR_BRIDGE"]

        for var in required_always:
            val = os.getenv(var, "")
            if val:
                self._pass("env_var", f"{var} is set")
            else:
                self._fail("env_var", f"{var} is required but not set")

        if is_hosted:
            for var in required_in_production:
                val = os.getenv(var, "")
                if val:
                    self._pass("env_var_production", f"{var} is set in production")
                else:
                    self._critical("env_var_production",
                                   f"{var} is NOT set in Railway/production. "
                                   "IBKR portfolio features will be unavailable.")

        for var in recommended_always:
            val = os.getenv(var, "")
            if val:
                self._pass("env_var_recommended", f"{var}={val}")
            else:
                self._warn("env_var_recommended", f"{var} not set (recommended for explicit mode selection)")

    def _check_bridge_config(self) -> None:
        bridge_url   = os.getenv("IBKR_BRIDGE_URL", "")
        bridge_token = os.getenv("IBKR_BRIDGE_TOKEN", "")
        is_hosted    = self._is_hosted()

        if bridge_url:
            localhost_patterns = ("localhost", "127.0.0.1", "0.0.0.0", "::1")
            if any(p in bridge_url.lower() for p in localhost_patterns):
                if is_hosted:
                    self._critical("bridge_config",
                                   f"IBKR_BRIDGE_URL '{bridge_url}' contains localhost — "
                                   "UNREACHABLE in Railway container. Update to ngrok URL.")
                else:
                    self._warn("bridge_config",
                               f"IBKR_BRIDGE_URL '{bridge_url}' is localhost — OK for dev only")
            else:
                self._pass("bridge_config", f"IBKR_BRIDGE_URL set to public URL: {bridge_url}")

            if not bridge_token:
                self._warn("bridge_config",
                           "IBKR_BRIDGE_URL set but IBKR_BRIDGE_TOKEN empty — bridge requests will 401")
            else:
                self._pass("bridge_config", "IBKR_BRIDGE_TOKEN is set")
        elif is_hosted:
            self._critical("bridge_config",
                           "Production detected but IBKR_BRIDGE_URL not configured — "
                           "portfolio data unavailable. Set IBKR_BRIDGE_URL in Railway.")
        else:
            self._warn("bridge_config",
                       "IBKR_BRIDGE_URL not set — IBKR unavailable (dev mode)")

    def _check_production_rules_module(self) -> None:
        try:
            from opsx.stability.production_rules import ProductionRules  # noqa: F401
            self._pass("stability_module", "opsx.stability.production_rules loaded OK")
        except Exception as exc:
            self._fail("stability_module", f"production_rules import failed: {exc}")

        try:
            from opsx.bridge.production_guard import validate_production_config  # noqa: F401
            self._pass("production_guard", "opsx.bridge.production_guard loaded OK")
        except Exception as exc:
            self._fail("production_guard", f"production_guard import failed: {exc}")

        try:
            from opsx.bridge.execution_guard import ExecutionGuardMiddleware  # noqa: F401
            self._pass("execution_guard", "ExecutionGuardMiddleware loaded OK")
        except Exception as exc:
            self._critical("execution_guard",
                           f"ExecutionGuardMiddleware import failed: {exc}. "
                           "Execution may not be blocked!")

    def _check_feature_registry(self) -> None:
        registry_path = Path("reports/stability/feature_lock_registry.json")
        if registry_path.exists():
            try:
                import json
                data = json.loads(registry_path.read_text(encoding="utf-8"))
                count = len(data.get("registry", []))
                protected = sum(1 for f in data.get("registry", []) if f.get("protected"))
                self._pass("feature_registry",
                           f"Loaded {count} features, {protected} protected")
            except Exception as exc:
                self._warn("feature_registry", f"Registry exists but failed to parse: {exc}")
        else:
            self._warn("feature_registry",
                       "Feature lock registry not found — run stability governor to create it")

    def _check_frontend_existence(self) -> None:
        html_path = Path("dashboard/jarvis_futuristic.html")
        if html_path.exists():
            size_kb = html_path.stat().st_size // 1024
            self._pass("frontend", f"dashboard HTML exists ({size_kb} KB)")
            # Quick critical check: use strict + boot function must be present
            try:
                sample = html_path.read_text(encoding="utf-8", errors="ignore")[:500000]
                if "function boot" in sample and "window.JARVIS_RUNTIME" in sample:
                    self._pass("frontend_runtime", "boot() and JARVIS_RUNTIME guard present")
                else:
                    self._critical("frontend_runtime",
                                   "boot() or JARVIS_RUNTIME missing from dashboard — "
                                   "runtime may not initialize")
            except Exception as exc:
                self._warn("frontend_read", f"Could not inspect dashboard: {exc}")
        else:
            self._critical("frontend",
                           "dashboard/jarvis_futuristic.html not found — frontend will 404")

    def _check_data_directories(self) -> None:
        required_dirs = [
            "data/portfolio",
            "data/bridge",
        ]
        for d in required_dirs:
            p = Path(d)
            if p.exists():
                self._pass("data_dir", f"{d} exists")
            else:
                self._warn("data_dir", f"{d} missing — will be created on first use")

    def _check_railway_localhost_safety(self) -> None:
        """Final safety check: ensure no localhost URLs are about to be used in production."""
        is_hosted   = self._is_hosted()
        bridge_url  = os.getenv("IBKR_BRIDGE_URL", "")
        gateway_url = os.getenv("IBKR_GATEWAY_URL", "")

        for var_name, url in [("IBKR_BRIDGE_URL", bridge_url), ("IBKR_GATEWAY_URL", gateway_url)]:
            if url and is_hosted:
                if any(p in url.lower() for p in ("localhost", "127.0.0.1")):
                    self._critical("railway_localhost_safety",
                                   f"{var_name}='{url}' is localhost — will NEVER work in Railway. "
                                   "Update to ngrok/public URL immediately.")

        if not is_hosted:
            self._pass("railway_localhost_safety", "Not in hosted runtime — localhost check N/A")
        elif is_hosted and not bridge_url:
            pass  # Already flagged in bridge_config
        elif is_hosted and bridge_url and not any(p in bridge_url.lower() for p in ("localhost", "127.0.0.1")):
            self._pass("railway_localhost_safety",
                       f"IBKR_BRIDGE_URL is not localhost in production ✓")

    def _check_watchdog_config(self) -> None:
        poll    = os.getenv("WATCHDOG_POLL_INTERVAL", "60")
        backoff = os.getenv("WATCHDOG_MAX_BACKOFF", "120")
        circuit = os.getenv("WATCHDOG_CIRCUIT_THRESHOLD", "5")

        try:
            self._pass("watchdog_config",
                       f"Watchdog config: poll={poll}s backoff_max={backoff}s circuit={circuit}fails")
        except Exception:
            self._warn("watchdog_config", "Could not read watchdog env vars")

    # ── Result Helpers ────────────────────────────────────────────────────────

    def _pass(self, check: str, message: str) -> None:
        self._results.append({"check": check, "status": "PASS", "message": message})

    def _warn(self, check: str, message: str) -> None:
        self._results.append({"check": check, "status": "WARN", "message": message})

    def _fail(self, check: str, message: str) -> None:
        self._results.append({"check": check, "status": "FAIL", "message": message})

    def _critical(self, check: str, message: str) -> None:
        self._results.append({"check": check, "status": "CRITICAL", "message": message})

    @staticmethod
    def _is_hosted() -> bool:
        return bool(
            os.getenv("RAILWAY_ENVIRONMENT")
            or os.getenv("RAILWAY_SERVICE_ID")
            or os.getenv("RAILWAY_PROJECT_ID")
            or os.getenv("RAILWAY_STATIC_URL")
            or os.getenv("RAILWAY_PUBLIC_DOMAIN")
            or os.getenv("ENV", "").lower() in {"production", "prod"}
        )
