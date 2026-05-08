"""
AI Evolution Memory — tracks JARVIS's capability growth over time.

Generates narrative summaries of how the AI has evolved, what skills have
improved, and what stage of development it has reached.
"""
from __future__ import annotations

from typing import Dict, List

from opsx.memory.ai_memory_store import (
    get_strategy_style_perf, get_asset_class_perf, get_regime_history,
    get_activity_feed, post_activity,
)


EVOLUTION_STAGES = [
    (0,  "Beginner",      "Learning basic price patterns and signal recognition"),
    (25, "Pattern Learner","Recognizing momentum, mean reversion, and regime shifts"),
    (45, "Intermediate",  "Multi-asset awareness, risk adaptation, strategy rotation"),
    (65, "Advanced",      "Cross-regime intelligence, volatility expertise, macro awareness"),
    (80, "Expert",        "Consistent disciplined execution across environments"),
    (90, "Elite",         "Institutional-grade adaptive behavior, micro-capital eligible"),
]


def get_evolution_stage(readiness_score: float) -> Dict:
    stage_name = "Beginner"
    stage_desc = EVOLUTION_STAGES[0][2]
    for threshold, name, desc in reversed(EVOLUTION_STAGES):
        if readiness_score >= threshold:
            stage_name, stage_desc = name, desc
            break
    next_stage = None
    for threshold, name, desc in EVOLUTION_STAGES:
        if readiness_score < threshold:
            next_stage = {"threshold": threshold, "name": name}
            break
    return {
        "stage_name":  stage_name,
        "stage_desc":  stage_desc,
        "next_stage":  next_stage,
        "all_stages":  [(t, n) for t, n, _ in EVOLUTION_STAGES],
    }


def get_evolution_narrative(readiness: float, accuracy: float, total_decisions: int) -> str:
    stage = get_evolution_stage(readiness)
    name  = stage["stage_name"]
    next_s = stage.get("next_stage")
    next_str = f" {next_s['threshold']}% readiness unlocks {next_s['name']}." if next_s else " Full capability reached."

    if total_decisions < 5:
        return f"JARVIS is in early training ({name}). Insufficient decisions to evaluate patterns.{next_str}"
    if accuracy >= 65 and readiness >= 50:
        return (f"JARVIS has reached {name} stage with {accuracy:.0f}% decision accuracy "
                f"and {readiness:.0f}% readiness.{next_str} Pattern recognition is strengthening.")
    elif accuracy < 50:
        return (f"JARVIS is in early {name} stage. Accuracy at {accuracy:.0f}% — "
                f"learning filters need refinement.{next_str}")
    else:
        return (f"JARVIS is developing as a {name}. {accuracy:.0f}% accuracy, "
                f"{readiness:.0f}% readiness.{next_str}")
