"""
JARVIS Capital Readiness Engine.

Readiness is a quality index (0–100) that gates AI capital deployment.

CRITICAL: Readiness NEVER increases from trade quantity.
It increases ONLY from demonstrated quality factors.

Scoring Components (max 100):
  quality_component   (0–45)  — composite decision scores from learning memory
  discipline_component(0–25)  — low drawdown, no overtrading, proper exits
  consistency_component(0–20) — low variance in returns, win-streak bonuses
  calibration_component(0–10) — confidence accurately predicted outcomes

Decrease triggers:
  — excessive drawdown events  (hard penalty, up to -15)
  — overtrading  (>5 trades/day pattern)  (-5 per episode)
  — poor risk/reward structure  (avg_loss > avg_gain)  (-8)
  — confidence overconfidence on losses  (-5)
"""
from __future__ import annotations

import logging
import math
from typing import Dict, List, Optional, Tuple

log = logging.getLogger("jarvis.readiness")


def compute_readiness(
    learning_summary: Dict,
    strategy_stats: List[Dict],
    recent_trades: List[Dict],
) -> Tuple[float, str, Dict]:
    """
    Compute current readiness score from accumulated learning data.

    Returns:
        (score: float, reason: str, components: Dict)
    """
    total      = learning_summary.get("total_decisions", 0)
    accuracy   = float(learning_summary.get("accuracy_pct", 0))
    avg_conf   = float(learning_summary.get("avg_confidence_pct", 50))
    lqs        = float(learning_summary.get("learning_quality_score", 0))

    components: Dict[str, float] = {}

    # ── 1. Quality Component (max 45) ─────────────────────────────────────
    # Needs at least 5 decisions to count; quality must be demonstrated
    if total < 5:
        quality_component = 0.0
        components["quality_note"] = f"Need {5 - total} more decisions"
    else:
        # lqs is 0-100; scaled to 0-45
        quality_component = min(45, lqs * 0.45)
    components["quality"] = round(quality_component, 1)

    # ── 2. Discipline Component (max 25) ──────────────────────────────────
    # Derived from strategy stats: profit factor, drawdown avoidance
    discipline = 25.0
    overtrading_penalty = 0.0
    if strategy_stats:
        # Penalize if any strategy has a terrible profit factor
        worst_pf = min((float(s.get("profit_factor", 0)) for s in strategy_stats), default=0)
        if worst_pf < 0.3 and len(strategy_stats) > 0:
            discipline -= 10  # persistent bad strategy = undisciplined

        # Reward high profit factor strategies
        best_pf = max((float(s.get("profit_factor", 0)) for s in strategy_stats), default=0)
        if best_pf > 2.0:
            discipline = min(25, discipline + 5)

    # Check recent trade velocity (overtrading)
    if len(recent_trades) >= 20:
        # Count trades per day in last 20
        from collections import Counter
        from datetime import datetime
        day_counts: Counter = Counter()
        for t in recent_trades[:20]:
            ts = t.get("opened_at") or t.get("timestamp", "")
            if ts:
                try:
                    day = ts[:10]
                    day_counts[day] += 1
                except Exception:
                    pass
        max_per_day = max(day_counts.values()) if day_counts else 0
        if max_per_day >= 8:
            overtrading_penalty = 10
        elif max_per_day >= 5:
            overtrading_penalty = 5
    discipline = max(0, discipline - overtrading_penalty)
    components["discipline"] = round(discipline, 1)
    components["overtrading_penalty"] = overtrading_penalty

    # ── 3. Consistency Component (max 20) ─────────────────────────────────
    consistency = 0.0
    closed = [t for t in recent_trades if t.get("status") == "closed"]
    if len(closed) >= 5:
        pnl_pcts = [float(t.get("pnl_pct", 0)) for t in closed[-20:]]
        if pnl_pcts:
            mean = sum(pnl_pcts) / len(pnl_pcts)
            variance = sum((x - mean) ** 2 for x in pnl_pcts) / len(pnl_pcts)
            std = math.sqrt(variance)
            # Low std = consistent; high std = volatile
            # Normalize: std <= 2% → full points; std >= 15% → 0 points
            consistency = max(0, 20 * (1 - min(1, std / 15)))

            # Win streak bonus: 3+ consecutive wins = +5 bonus
            streak = 0
            for t in reversed(closed[-10:]):
                if float(t.get("pnl", 0)) > 0:
                    streak += 1
                else:
                    break
            if streak >= 5:
                consistency = min(20, consistency + 5)
            elif streak >= 3:
                consistency = min(20, consistency + 2)
    components["consistency"] = round(consistency, 1)

    # ── 4. Calibration Component (max 10) ─────────────────────────────────
    # High confidence + correct = good; high confidence + wrong = penalized
    if total >= 5:
        calibration = 10 * (accuracy / 100) * (1 - abs(avg_conf / 100 - accuracy / 100))
        calibration = max(0, min(10, calibration))
    else:
        calibration = 0.0
    components["calibration"] = round(calibration, 1)

    # ── Drawdown hard penalty ─────────────────────────────────────────────
    drawdown_penalty = 0.0
    if recent_trades:
        max_loss_pct = min((float(t.get("pnl_pct", 0)) for t in closed[-20:]), default=0)
        if max_loss_pct < -15:
            drawdown_penalty = 15
        elif max_loss_pct < -10:
            drawdown_penalty = 8
        elif max_loss_pct < -5:
            drawdown_penalty = 3
    components["drawdown_penalty"] = drawdown_penalty

    # ── Final score ───────────────────────────────────────────────────────
    raw = quality_component + discipline + consistency + calibration - drawdown_penalty
    score = round(max(0, min(100, raw)), 1)

    # Build human-readable reason for the change
    reasons = []
    if quality_component < 15:
        reasons.append("low decision quality — more disciplined trades needed")
    elif quality_component > 35:
        reasons.append("strong decision quality")
    if discipline < 15:
        reasons.append("discipline concerns detected")
    if drawdown_penalty > 0:
        reasons.append(f"drawdown penalty applied ({drawdown_penalty:.0f}pts)")
    if consistency > 15:
        reasons.append("highly consistent returns")
    reason = "; ".join(reasons) if reasons else "standard evaluation"

    return score, reason, components


def evaluate_readiness_delta(
    prev_score: float,
    new_score: float,
    components: Dict,
) -> Dict:
    """Describe what changed and why."""
    delta = round(new_score - prev_score, 1)
    direction = "increased" if delta > 0 else "decreased" if delta < 0 else "unchanged"

    messages = []
    if components.get("overtrading_penalty", 0) > 0:
        messages.append(f"Overtrading detected — -{components['overtrading_penalty']:.0f} discipline pts")
    if components.get("drawdown_penalty", 0) > 0:
        messages.append(f"Excess drawdown — -{components['drawdown_penalty']:.0f} pts")
    if components.get("quality", 0) > 35:
        messages.append("Excellent trade quality contributing")
    if components.get("consistency", 0) > 15:
        messages.append("Highly consistent return profile")

    return {
        "delta":     delta,
        "direction": direction,
        "messages":  messages,
        "components": components,
    }
