"""
Risk Adaptation Memory — tracks how JARVIS adapts its risk posture.

Records every risk mode change, the trigger, and the outcome, so the AI
can learn when to be defensive vs. opportunistic.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from opsx.capital.capital_store import capital_store


def get_risk_adaptation_summary() -> Dict:
    """Summarize recent risk adaptation decisions."""
    log = capital_store.get_risk_log(limit=20)
    if not log:
        return {"total_changes": 0, "current_mode": "balanced", "log": []}
    mode_counts: Dict[str, int] = {}
    for entry in log:
        m = entry.get("mode", "balanced")
        mode_counts[m] = mode_counts.get(m, 0) + 1
    most_used = max(mode_counts, key=mode_counts.get) if mode_counts else "balanced"
    current   = log[0].get("mode", "balanced") if log else "balanced"
    return {
        "total_changes":  len(log),
        "current_mode":   current,
        "most_used_mode": most_used,
        "mode_frequency": mode_counts,
        "recent":         log[:5],
    }


def auto_adapt(regime: str, vix: Optional[float], readiness: float) -> Optional[str]:
    """
    Suggest a risk mode change based on current conditions.
    Returns new mode name or None if no change needed.
    """
    vault  = capital_store.get_vault()
    current_mode = vault.get("risk_mode", "balanced")

    # Emergency defensive triggers
    if vix and vix >= 35:
        if current_mode not in ("conservative",):
            return "conservative"
    if regime in ("panic", "risk_off"):
        if current_mode not in ("conservative",):
            return "conservative"

    # Moderate defensive
    if vix and vix >= 25:
        if current_mode == "aggressive":
            return "balanced"

    # Opportunistic upgrade (only if readiness justifies it)
    if readiness >= 70 and vix and vix < 15 and regime == "bull":
        if current_mode == "conservative":
            return "balanced"

    return None
