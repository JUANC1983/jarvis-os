"""
JARVIS Safe Patch Engine — Phase 5.

Before ANY future modification:
  1. Dependency impact analysis — which features depend on the files being changed
  2. Regression prediction — what could break
  3. Protected feature check — if protected, require explicit override token
  4. API contract check — will any endpoint schema change
  5. Frontend hydration check — will any UI function be affected

Usage:
    engine = PatchEngine()
    report = engine.analyze(["main.py", "opsx/connectors/ibkr_bridge_client.py"])
    if report["protected_features_affected"]:
        # Require explicit acknowledgment
        engine.require_override("IBKR_LIVE_BRIDGE", override_key="PATCH_OVERRIDE_2026-05-07")
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

log = logging.getLogger("jarvis.patch_engine")

_REGISTRY_PATH = Path("reports/stability/feature_lock_registry.json")

# ── File → Feature dependency map ────────────────────────────────────────────
# Maps file path fragments to the feature IDs they affect.
# If you modify a file in the key, the features in the value are at risk.
_FILE_TO_FEATURES: Dict[str, List[str]] = {
    "opsx/connectors/ibkr_bridge_client.py": ["IBKR_LIVE_BRIDGE", "PORTFOLIO_COCKPIT", "MARKETS_DASHBOARD", "SNAPSHOT_ENGINE"],
    "opsx/connectors/ibkr_readonly.py":      ["IBKR_LIVE_BRIDGE"],
    "opsx/connectors/ibkr_connector.py":     ["IBKR_LIVE_BRIDGE"],
    "opsx/bridge/watchdog.py":               ["WATCHDOG", "IBKR_LIVE_BRIDGE", "LOAD_CONNECTION_STATUS"],
    "opsx/bridge/production_guard.py":       ["IBKR_LIVE_BRIDGE", "EXECUTION_GUARD"],
    "opsx/bridge/execution_guard.py":        ["EXECUTION_GUARD", "IBKR_LIVE_BRIDGE"],
    "opsx/bridge/secure_bridge.py":          ["IBKR_LIVE_BRIDGE", "EXECUTION_GUARD"],
    "opsx/bridge/account_separation.py":     ["IBKR_LIVE_BRIDGE", "MARKETS_DASHBOARD"],
    "core/paper_trading_engine.py":          ["PAPER_LAB"],
    "core/unified_portfolio_engine.py":      ["PORTFOLIO_COCKPIT", "MARKETS_DASHBOARD"],
    "core/portfolio_intelligence_engine.py": ["MARKETS_DASHBOARD"],
    "main.py":                               [
        "IBKR_LIVE_BRIDGE", "HEALTH_ENDPOINTS", "EXECUTION_GUARD",
        "PAPER_LAB", "PORTFOLIO_COCKPIT", "MARKETS_DASHBOARD",
        "WATCHDOG", "SNAPSHOT_ENGINE",
    ],
    "dashboard/jarvis_futuristic.html":      [
        "NAVIGATION_SYSTEM", "SWITCH_TAB", "HOME_HYDRATION",
        "LOAD_CONNECTION_STATUS", "PORTFOLIO_COCKPIT", "MARKETS_DASHBOARD",
        "GOLF_DASHBOARD", "VOICE_SYSTEM", "AUTOMATIONS",
        "ONBOARDING_WIZARD", "RUNTIME_BOOTLOADER", "OUTLOOK_SYNC", "CALENDAR_SYNC",
        "MEMORY_SYSTEM",
    ],
}

# ── Risk Level per Feature ────────────────────────────────────────────────────
_FEATURE_RISK: Dict[str, str] = {
    "IBKR_LIVE_BRIDGE":     "CRITICAL",
    "EXECUTION_GUARD":      "CRITICAL",
    "RUNTIME_BOOTLOADER":   "CRITICAL",
    "SWITCH_TAB":           "CRITICAL",
    "NAVIGATION_SYSTEM":    "CRITICAL",
    "HEALTH_ENDPOINTS":     "CRITICAL",
    "PAPER_LAB":            "HIGH",
    "PORTFOLIO_COCKPIT":    "HIGH",
    "MARKETS_DASHBOARD":    "HIGH",
    "HOME_HYDRATION":       "HIGH",
    "LOAD_CONNECTION_STATUS": "HIGH",
    "WATCHDOG":             "HIGH",
    "SNAPSHOT_ENGINE":      "HIGH",
    "OUTLOOK_SYNC":         "MEDIUM",
    "CALENDAR_SYNC":        "MEDIUM",
    "MEMORY_SYSTEM":        "MEDIUM",
    "GOLF_DASHBOARD":       "MEDIUM",
    "VOICE_SYSTEM":         "MEDIUM",
    "AUTOMATIONS":          "MEDIUM",
    "ONBOARDING_WIZARD":    "MEDIUM",
}


class PatchReport:
    def __init__(self, files_to_change: List[str]):
        self.files_to_change             = files_to_change
        self.affected_features: List[str] = []
        self.protected_features: List[str] = []
        self.critical_features: List[str]  = []
        self.risk_level                  = "LOW"
        self.requires_override           = False
        self.requires_full_qa            = False
        self.regression_predictions: List[str] = []
        self.api_contracts_at_risk: List[str]   = []
        self.frontend_functions_at_risk: List[str] = []
        self.rollback_recommended        = False

    def to_dict(self) -> Dict:
        return {
            "files_to_change":           self.files_to_change,
            "affected_features":         self.affected_features,
            "protected_features":        self.protected_features,
            "critical_features_affected": self.critical_features,
            "overall_risk":              self.risk_level,
            "requires_override":         self.requires_override,
            "requires_full_qa":          self.requires_full_qa,
            "regression_predictions":    self.regression_predictions,
            "api_contracts_at_risk":     self.api_contracts_at_risk,
            "frontend_functions_at_risk": self.frontend_functions_at_risk,
            "rollback_recommended":      self.rollback_recommended,
        }


class PatchEngine:
    """Pre-patch impact analyzer and protected feature gatekeeper."""

    def __init__(self) -> None:
        self._registry = self._load_registry()

    def _load_registry(self) -> Dict:
        try:
            if _REGISTRY_PATH.exists():
                return json.loads(_REGISTRY_PATH.read_text(encoding="utf-8"))
        except Exception as exc:
            log.warning("Could not load feature registry: %s", exc)
        return {"registry": []}

    def _get_feature(self, feature_id: str) -> Optional[Dict]:
        for f in self._registry.get("registry", []):
            if f["feature_id"] == feature_id:
                return f
        return None

    def analyze(self, files_to_change: List[str]) -> PatchReport:
        """
        Analyze impact of modifying the given files.
        Returns a PatchReport with affected features, risks, and requirements.
        """
        report = PatchReport(files_to_change)
        affected: Set[str] = set()

        for file_path in files_to_change:
            # Normalize path separators
            norm = file_path.replace("\\", "/").lower()
            for pattern, features in _FILE_TO_FEATURES.items():
                if pattern.lower() in norm or norm in pattern.lower():
                    affected.update(features)

        report.affected_features = sorted(affected)

        # Classify by protection status
        for fid in affected:
            feature = self._get_feature(fid)
            if feature and feature.get("protected"):
                report.protected_features.append(fid)
            risk = _FEATURE_RISK.get(fid, "LOW")
            if risk == "CRITICAL":
                report.critical_features.append(fid)

        # Determine overall risk
        if report.critical_features:
            report.risk_level = "CRITICAL"
        elif report.protected_features:
            report.risk_level = "HIGH"
        elif report.affected_features:
            report.risk_level = "MEDIUM"
        else:
            report.risk_level = "LOW"

        # Override and QA requirements
        report.requires_override  = bool(report.protected_features)
        report.requires_full_qa   = bool(report.critical_features)
        report.rollback_recommended = bool(report.critical_features)

        # Regression predictions
        self._predict_regressions(report)

        # API contracts at risk
        self._identify_api_risks(report)

        # Frontend functions at risk
        self._identify_frontend_risks(report, files_to_change)

        return report

    def _predict_regressions(self, report: PatchReport) -> None:
        for fid in report.critical_features:
            if fid == "RUNTIME_BOOTLOADER":
                report.regression_predictions.append(
                    "Modifying boot() may break all tab loading — run full frontend QA"
                )
            if fid == "SWITCH_TAB":
                report.regression_predictions.append(
                    "switchTab() change may break 156+ onclick handlers — audit all nav buttons"
                )
            if fid == "IBKR_LIVE_BRIDGE":
                report.regression_predictions.append(
                    "IBKR connector change — run ibkr_bridge_hardening QA + verify no localhost fallback"
                )
            if fid == "EXECUTION_GUARD":
                report.regression_predictions.append(
                    "Execution guard change — verify all 7 execution methods still raise TradingBlockedError"
                )
        for fid in report.protected_features:
            if fid == "PAPER_LAB":
                report.regression_predictions.append(
                    "Paper Lab change — verify real_trade=False, confirm() still required for reset"
                )
            if fid == "PORTFOLIO_COCKPIT":
                report.regression_predictions.append(
                    "loadCockpit() change — verify no duplicate const declarations introduced"
                )

    def _identify_api_risks(self, report: PatchReport) -> None:
        feature_to_endpoints = {
            "IBKR_LIVE_BRIDGE": ["/api/debug/ibkr", "/api/portfolio/status"],
            "WATCHDOG":         ["/api/bridge/watchdog"],
            "PORTFOLIO_COCKPIT": ["/api/portfolio/cockpit", "/api/portfolio/summary"],
            "HEALTH_ENDPOINTS": ["/api/health", "/api/debug/permissions"],
        }
        for fid in report.affected_features:
            endpoints = feature_to_endpoints.get(fid, [])
            report.api_contracts_at_risk.extend(endpoints)
        report.api_contracts_at_risk = list(set(report.api_contracts_at_risk))

    def _identify_frontend_risks(self, report: PatchReport, files: List[str]) -> None:
        html_touched = any("jarvis_futuristic" in f.lower() for f in files)
        if html_touched:
            report.frontend_functions_at_risk.extend([
                "switchTab()", "loadHome()", "loadConnectionStatus()",
                "loadPortfolioSummary()", "loadCockpit()", "boot()",
            ])

    def require_override(
        self, feature_id: str, override_key: str
    ) -> bool:
        """
        Validate override key for a protected feature.
        Key format: PATCH_OVERRIDE_<DATE>_<FEATURE_ID>
        Returns True if override is valid, raises if not.
        """
        expected = f"PATCH_OVERRIDE_{feature_id}"
        if expected in override_key:
            log.info("Override accepted for %s: %s", feature_id, override_key)
            return True
        raise PermissionError(
            f"Protected feature '{feature_id}' requires override key containing "
            f"'{expected}'. Provide this key to proceed."
        )

    def generate_checklist(self, report: PatchReport) -> List[str]:
        """Generate a step-by-step pre-patch checklist for human review."""
        checklist = [
            f"[ ] Files to change: {', '.join(report.files_to_change)}",
            f"[ ] Risk level: {report.risk_level}",
            f"[ ] Affected features: {', '.join(report.affected_features) or 'none'}",
        ]
        if report.protected_features:
            checklist.append(f"[ ] OVERRIDE REQUIRED for: {', '.join(report.protected_features)}")
        if report.api_contracts_at_risk:
            checklist.append(f"[ ] Verify API contracts: {', '.join(report.api_contracts_at_risk)}")
        if report.frontend_functions_at_risk:
            checklist.append(f"[ ] Run frontend QA for: {', '.join(report.frontend_functions_at_risk)}")
        for pred in report.regression_predictions:
            checklist.append(f"[ ] Regression risk: {pred}")
        if report.rollback_recommended:
            checklist.append("[ ] Create rollback snapshot before proceeding")
        checklist.append("[ ] Run deployment_guard.py after patch")
        return checklist
