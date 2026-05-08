"""
Market Regime Memory — persists regime detection history and provides
regime-aware context for AI decisions.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from opsx.memory.ai_memory_store import (
    record_regime, get_regime_history, post_activity,
)

REGIME_DESCRIPTIONS = {
    "bull":           {"label": "Bullish", "color": "#4ade80",  "icon": "📈"},
    "bear":           {"label": "Defensive", "color": "#f87171", "icon": "📉"},
    "high_vol":       {"label": "High Volatility", "color": "#f97316", "icon": "⚡"},
    "panic":          {"label": "Risk-Off / Panic", "color": "#ef4444", "icon": "🔴"},
    "sideways":       {"label": "Sideways / Neutral", "color": "#facc15", "icon": "📊"},
    "momentum":       {"label": "Momentum Expansion", "color": "#22d3ee", "icon": "🚀"},
    "low_liquidity":  {"label": "Low Liquidity", "color": "#94a3b8",   "icon": "🌊"},
    "risk_off":       {"label": "Risk-Off", "color": "#f87171",        "icon": "🛡️"},
}

_prev_regime: Optional[str] = None


def record_and_broadcast(regime: str, vix: Optional[float] = None,
                         spy_ret_5d: float = 0, spy_ret_20d: float = 0) -> None:
    global _prev_regime
    record_regime(regime, vix=vix, spy_ret_5d=spy_ret_5d, spy_ret_20d=spy_ret_20d)
    info = REGIME_DESCRIPTIONS.get(regime, {"label": regime, "icon": "📊"})
    if _prev_regime and _prev_regime != regime:
        post_activity(
            f"Market regime shift: {REGIME_DESCRIPTIONS.get(_prev_regime,{}).get('label',_prev_regime)} → {info['label']}. Adjusting strategy filters.",
            category="regime", severity="warning",
        )
    _prev_regime = regime


def get_current_regime_info() -> Dict:
    history = get_regime_history(limit=1)
    if not history:
        return {"regime": "unknown", "label": "Unknown", "color": "#94a3b8", "icon": "❓"}
    latest = history[0]
    regime = latest.get("regime", "sideways")
    info   = REGIME_DESCRIPTIONS.get(regime, {"label": regime, "color": "#94a3b8", "icon": "📊"})
    return {
        "regime":      regime,
        "label":       info["label"],
        "color":       info["color"],
        "icon":        info["icon"],
        "vix":         latest.get("vix"),
        "recorded_at": latest.get("recorded_at"),
    }
