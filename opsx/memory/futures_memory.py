"""
Futures Memory — tracks futures contract performance via ETF proxies.

Futures contracts tracked via liquid ETF proxies (no CME data feed required):
  ES  → SPY    (S&P 500 futures)
  NQ  → QQQ    (Nasdaq futures)
  CL  → USO    (Crude Oil futures)
  GC  → GLD    (Gold futures)
  ZN  → TLT    (Treasury futures)
  RTY → IWM    (Russell 2000 futures)
  VX  → VXX   (VIX futures)
"""
from __future__ import annotations

from typing import Dict, List

from opsx.memory.ai_memory_store import (
    update_asset_perf, get_asset_class_perf, post_activity,
)

FUTURES_PROXY_MAP = {
    "ES":  "SPY",
    "NQ":  "QQQ",
    "CL":  "USO",
    "GC":  "GLD",
    "ZN":  "TLT",
    "RTY": "IWM",
    "VX":  "VXX",
    "YM":  "DIA",
}


def record_futures_decision(contract: str, correct: bool, quality: float) -> None:
    update_asset_perf("futures", correct, quality)
    proxy = FUTURES_PROXY_MAP.get(contract, contract)
    if correct and quality >= 70:
        post_activity(
            f"Futures signal correct: {contract} ({proxy} proxy) — quality {quality:.0f}",
            category="futures", asset_class="futures", severity="info",
        )


def get_futures_summary() -> Dict:
    perf = [p for p in get_asset_class_perf() if p.get("asset_class") == "futures"]
    f = perf[0] if perf else {}
    return {
        "proxy_map":   FUTURES_PROXY_MAP,
        "decisions":   f.get("decisions", 0),
        "accuracy":    f.get("accuracy_pct", 0),
        "avg_quality": f.get("avg_quality", 0),
        "note":        "Futures tracked via ETF proxies — no CME data feed required",
    }
