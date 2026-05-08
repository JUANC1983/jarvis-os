"""
JARVIS Trust Score Engine — Phase 8.

Calculates a 0-100 system trust score based on the weighted health
of all monitored services plus data freshness penalties.

Operator confidence labels:
  90-100  Institutional Mode
  75-89   Operational
  60-74   Degraded Operations
  40-59   Fallback Mode Active
  0-39    Critical Failure
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Dict, Tuple

# ── Weights (must sum to 1.0) ─────────────────────────────────────────────────

_WEIGHTS: Dict[str, float] = {
    "ibkr_gateway":      0.14,
    "market_data":       0.12,
    "autonomous_trader": 0.09,
    "paper_trader":      0.04,
    "signal_engine":     0.07,
    "portfolio_engine":  0.08,
    "risk_engine":       0.05,
    "strategy_engine":   0.04,
    "openai_api":        0.12,
    "claude_api":        0.08,
    "memory_system":     0.05,
    "calendar":          0.03,
    "outlook_email":     0.03,
    "news_ingestion":    0.03,
    "webhook_listener":  0.02,
    "scheduler_jobs":    0.05,
    "notification_svc":  0.02,
    "voice_subsystem":   0.00,   # client-side — doesn't affect score
}

# ── State → numeric score ─────────────────────────────────────────────────────

_STATE_SCORE: Dict[str, float] = {
    "healthy":  1.00,
    "starting": 0.80,
    "fallback": 0.65,
    "degraded": 0.45,
    "unknown":  0.35,
    "offline":  0.00,
}

# ── Confidence labels ─────────────────────────────────────────────────────────

def _label(score: int) -> str:
    if score >= 90:
        return "Institutional Mode"
    if score >= 75:
        return "Operational"
    if score >= 60:
        return "Degraded Operations"
    if score >= 40:
        return "Fallback Mode Active"
    return "Critical Failure"


def _label_color(score: int) -> str:
    if score >= 90:
        return "#4ade80"
    if score >= 75:
        return "#44f0ff"
    if score >= 60:
        return "#facc15"
    if score >= 40:
        return "#f97316"
    return "#f87171"


# ── Engine ────────────────────────────────────────────────────────────────────

class TrustScoreEngine:

    def compute(self, health_snapshot: Dict[str, Dict]) -> Dict[str, Any]:
        """
        Given the full health snapshot dict (from HealthMonitor.get_all()),
        return the trust score record.
        """
        services = health_snapshot

        weighted_sum = 0.0
        total_weight = 0.0
        breakdown: Dict[str, Any] = {}
        critical_failures = []
        active_fallbacks  = []
        degraded_services = []

        for sid, weight in _WEIGHTS.items():
            if weight == 0:
                continue
            sh = services.get(sid, {})
            state   = sh.get("state", "unknown")
            s_score = _STATE_SCORE.get(state, 0.35)

            # Extra penalty if fallback is active
            if sh.get("fallback_active") and state not in ("offline", "unknown"):
                s_score = min(s_score, 0.60)

            weighted_sum  += weight * s_score
            total_weight  += weight
            breakdown[sid] = {
                "state":   state,
                "weight":  weight,
                "score":   round(s_score, 2),
                "contrib": round(weight * s_score * 100, 1),
            }

            if state == "offline":
                critical_failures.append(sh.get("display_name", sid))
            elif sh.get("fallback_active"):
                active_fallbacks.append(sh.get("display_name", sid))
            elif state == "degraded":
                degraded_services.append(sh.get("display_name", sid))

        raw_score = (weighted_sum / total_weight) if total_weight > 0 else 0.0
        score = max(0, min(100, int(round(raw_score * 100))))

        # Hard-cap: if IBKR + market_data both offline in a live-trading context
        ibkr_offline = services.get("ibkr_gateway", {}).get("state") == "offline"
        market_offline = services.get("market_data", {}).get("state") == "offline"
        if ibkr_offline and market_offline:
            score = min(score, 45)

        return {
            "score":             score,
            "label":             _label(score),
            "color":             _label_color(score),
            "critical_failures": critical_failures,
            "active_fallbacks":  active_fallbacks,
            "degraded_services": degraded_services,
            "breakdown":         breakdown,
            "healthy_count":     sum(1 for s in services.values() if s.get("state") == "healthy"),
            "total_services":    len(services),
            "computed_at":       datetime.now(timezone.utc).isoformat(),
        }


# ── Singleton ─────────────────────────────────────────────────────────────────

trust_score = TrustScoreEngine()
