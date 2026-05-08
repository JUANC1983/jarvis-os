"""
Strategy Rotation Memory — tracks which trading styles JARVIS currently prefers
and how strategy confidence rotates over time.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from opsx.memory.ai_memory_store import (
    get_strategy_style_perf, update_strategy_style, post_activity,
)

STRATEGY_STYLES = [
    "momentum", "swing", "breakout", "mean_reversion",
    "trend_following", "volatility", "macro_rotation", "defensive",
]


def get_preferred_strategy() -> Optional[str]:
    """Return the strategy style with highest current accuracy (min 5 decisions)."""
    styles = get_strategy_style_perf()
    eligible = [s for s in styles if s.get("decisions", 0) >= 5]
    if not eligible:
        return None
    return max(eligible, key=lambda s: s.get("accuracy_pct", 0)).get("style")


def get_rotation_summary() -> Dict:
    """Full strategy rotation state — what's working, what's not."""
    styles = get_strategy_style_perf()
    ranked = sorted(styles, key=lambda s: s.get("accuracy_pct", 0), reverse=True)
    preferred = ranked[0]["style"] if ranked else None
    avoid     = [s["style"] for s in ranked if s.get("accuracy_pct", 0) < 40 and s.get("decisions", 0) >= 5]
    return {
        "preferred_style": preferred,
        "avoid_styles":    avoid,
        "ranked":          ranked[:5],
        "total_styles":    len(styles),
    }


def record_style_decision(style: str, correct: bool, quality: float) -> None:
    update_strategy_style(style, correct, quality)
    if correct and quality >= 75:
        post_activity(
            f"Strategy '{style}' performing well — confidence reinforced",
            category="strategy", strategy=style, severity="info",
        )
    elif not correct and quality < 40:
        post_activity(
            f"Strategy '{style}' underperforming — filter tightening",
            category="strategy", strategy=style, severity="warning",
        )
