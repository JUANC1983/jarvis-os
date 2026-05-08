"""
JARVIS Capital Risk Temperature Engine.

Computes current market risk temperature and recommends risk mode
based on real-time market conditions. Adapts AI trading personality
automatically when conditions change.

Temperature levels:
  LOW      (0–25)   — calm markets, normal conditions
  BALANCED (25–50)  — moderate volatility, some caution warranted
  HIGH     (50–75)  — elevated volatility, defensive posture recommended
  EXTREME  (75–100) — crisis conditions, capital preservation priority
"""
from __future__ import annotations

import logging
from typing import Dict, Optional

log = logging.getLogger("jarvis.risk_temperature")

TEMPERATURE_LEVELS = [
    (0,  "LOW",      "#4ade80"),
    (25, "BALANCED", "#facc15"),
    (50, "HIGH",     "#f97316"),
    (75, "EXTREME",  "#f87171"),
]

MODE_TEMPERATURE_CAPS = {
    "conservative":  50,   # never exceeds BALANCED in conservative mode
    "balanced":      75,   # allows HIGH but not EXTREME auto-entry
    "aggressive":    90,   # allows HIGH/EXTREME with reduced sizing
    "experimental":  100,  # full range, paper only
}


def compute_temperature(
    vix: Optional[float] = None,
    market_regime: Optional[str] = None,
    macro_context: Optional[str] = None,
) -> Dict:
    """
    Compute current risk temperature from available market data.

    Returns dict with:
      temperature (0–100 float)
      level_name  (LOW / BALANCED / HIGH / EXTREME)
      color       (hex color)
      factors     (list of contributing factors)
      recommendation (mode recommendation)
    """
    temp   = 30.0  # default: slightly cautious
    factors = []

    # ── VIX contribution ──────────────────────────────────────────────────
    if vix is not None:
        if vix < 15:
            vix_contrib = 10
            factors.append(f"VIX {vix:.1f} — low fear")
        elif vix < 20:
            vix_contrib = 25
            factors.append(f"VIX {vix:.1f} — normal")
        elif vix < 25:
            vix_contrib = 40
            factors.append(f"VIX {vix:.1f} — elevated")
        elif vix < 30:
            vix_contrib = 60
            factors.append(f"VIX {vix:.1f} — high volatility")
        elif vix < 40:
            vix_contrib = 80
            factors.append(f"VIX {vix:.1f} — severe volatility")
        else:
            vix_contrib = 95
            factors.append(f"VIX {vix:.1f} — extreme fear")
        temp = vix_contrib  # VIX is the primary driver

    # ── Market regime adjustments ─────────────────────────────────────────
    if market_regime:
        regime = market_regime.lower()
        if "bull" in regime or "risk_on" in regime:
            temp = max(10, temp - 10)
            factors.append("Bull/risk-on regime — reducing temperature")
        elif "bear" in regime or "risk_off" in regime:
            temp = min(90, temp + 15)
            factors.append("Bear/risk-off regime — raising temperature")
        elif "sideways" in regime or "chop" in regime:
            temp = min(80, temp + 5)
            factors.append("Choppy/sideways regime — slight caution")
        elif "crisis" in regime:
            temp = min(100, temp + 25)
            factors.append("Crisis regime — extreme caution")

    # ── Macro context adjustments ─────────────────────────────────────────
    if macro_context:
        ctx = macro_context.lower()
        if any(w in ctx for w in ["fed", "fomc", "rate decision"]):
            temp = min(100, temp + 10)
            factors.append("Fed event imminent — adding caution buffer")
        if any(w in ctx for w in ["cpi", "inflation"]):
            temp = min(100, temp + 8)
            factors.append("CPI/inflation data — volatility risk")
        if any(w in ctx for w in ["recession", "crisis", "crash"]):
            temp = min(100, temp + 20)
            factors.append("Recession/crisis signals — defensive mode")

    # ── Normalize ─────────────────────────────────────────────────────────
    temp = round(max(0, min(100, temp)), 1)

    # ── Determine level ───────────────────────────────────────────────────
    level_name = "LOW"
    color = "#4ade80"
    for threshold, name, col in reversed(TEMPERATURE_LEVELS):
        if temp >= threshold:
            level_name = name
            color = col
            break

    # ── Mode recommendation ───────────────────────────────────────────────
    if temp >= 75:
        recommended_mode = "conservative"
        mode_reason = "Extreme conditions — capital preservation priority"
    elif temp >= 50:
        recommended_mode = "balanced"
        mode_reason = "High volatility — balanced risk stance recommended"
    elif temp >= 25:
        recommended_mode = "balanced"
        mode_reason = "Normal conditions — balanced approach appropriate"
    else:
        recommended_mode = "balanced"
        mode_reason = "Low volatility — standard balanced mode"

    return {
        "temperature":        temp,
        "level_name":         level_name,
        "color":              color,
        "factors":            factors,
        "recommended_mode":   recommended_mode,
        "mode_reason":        mode_reason,
        "temperature_levels": [
            {"name": n, "threshold": t, "color": c}
            for t, n, c in TEMPERATURE_LEVELS
        ],
    }


def should_auto_adjust(
    current_mode: str,
    temperature: Dict,
    readiness: float,
) -> Optional[str]:
    """
    Determine if the risk mode should be auto-adjusted.
    Only activates when temperature significantly exceeds mode's safe range.
    Returns new mode or None if no change needed.
    """
    if readiness < 30:
        return None  # Not enough readiness to auto-adapt

    temp = float(temperature.get("temperature", 30))
    cap  = MODE_TEMPERATURE_CAPS.get(current_mode, 75)

    if temp > cap:
        # Force downgrade toward safety
        if current_mode == "aggressive":
            return "balanced"
        if current_mode == "balanced" and temp >= 75:
            return "conservative"
    return None
