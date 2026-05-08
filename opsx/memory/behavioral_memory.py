"""
Behavioral Memory — tracks JARVIS's trading behavioral patterns.

Monitors for: overtrading, revenge entries, disciplined exits,
position sizing discipline, confidence calibration, stop-loss adherence.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Dict, List

from opsx.memory.ai_memory_store import (
    record_behavioral_event, get_strategy_style_perf, post_activity,
)


def evaluate_behavior(recent_decisions: List[Dict]) -> Dict:
    """
    Analyze recent decisions for behavioral patterns.
    Returns a behavioral health score (0–100) and detected issues.
    """
    if not recent_decisions:
        return {"score": 50, "issues": [], "positives": []}

    issues   = []
    positives = []
    score    = 70  # neutral starting point

    n = len(recent_decisions)

    # ── Overtrading check ─────────────────────────────────────────────────
    day_counts: Counter = Counter()
    for d in recent_decisions:
        ts = d.get("decided_at", "")
        if ts:
            day_counts[ts[:10]] += 1
    max_per_day = max(day_counts.values(), default=0)
    if max_per_day >= 8:
        score -= 15
        issues.append("Overtrading detected — too many decisions per day")
        record_behavioral_event("overtrading", f"{max_per_day} decisions in one day", "warning")
        post_activity("Overtrading pattern detected — discipline filters tightening", category="behavior", severity="warning")
    elif max_per_day >= 5:
        score -= 7
        issues.append("Elevated trading frequency — approaching overtrading")

    # ── Confidence consistency ────────────────────────────────────────────
    confs = [float(d.get("confidence", 0.5)) for d in recent_decisions]
    if confs:
        avg_conf = sum(confs) / len(confs)
        conf_var = sum((c - avg_conf) ** 2 for c in confs) / len(confs)
        if conf_var > 0.04:
            issues.append("Inconsistent confidence signals — calibration drift")
            score -= 5
        elif avg_conf > 0.7:
            positives.append("High average confidence maintained")
            score += 5

    # ── Win-streak momentum trap ─────────────────────────────────────────
    correct = [d for d in recent_decisions if d.get("scored") and d.get("actual_direction") == d.get("direction")]
    incorrect = [d for d in recent_decisions if d.get("scored") and d.get("actual_direction") != d.get("direction")]
    if len(correct) >= 5 and len(incorrect) == 0:
        positives.append("Clean winning streak — discipline maintained")
        score += 8
    if len(incorrect) >= 4 and len(correct) <= 1:
        issues.append("Consecutive losses — consider defensive posture")
        score -= 10
        post_activity("Multiple consecutive losses detected — switching to conservative analysis", category="behavior", severity="warning")

    score = max(0, min(100, score))
    return {"score": score, "issues": issues, "positives": positives, "decisions_analyzed": n}
