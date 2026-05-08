"""
Crypto Memory — 24/7 cryptocurrency performance tracking.

Crypto markets never close, making them ideal for continuous learning.
Tracks BTC, ETH, SOL, and major altcoins via yfinance -USD pairs.
"""
from __future__ import annotations

from typing import Dict, List

from opsx.memory.ai_memory_store import (
    update_asset_perf, get_asset_class_perf, post_activity,
)

CRYPTO_UNIVERSE = [
    "BTC-USD", "ETH-USD", "SOL-USD",
    "BNB-USD", "XRP-USD", "ADA-USD",
    "AVAX-USD", "DOT-USD", "LINK-USD",
]

CRYPTO_CHARACTERISTICS = {
    "BTC-USD":  {"name": "Bitcoin",    "vol_profile": "high",   "liquidity": "highest"},
    "ETH-USD":  {"name": "Ethereum",   "vol_profile": "high",   "liquidity": "high"},
    "SOL-USD":  {"name": "Solana",     "vol_profile": "v_high", "liquidity": "high"},
    "BNB-USD":  {"name": "BNB",        "vol_profile": "high",   "liquidity": "high"},
}


def record_crypto_decision(symbol: str, correct: bool, quality: float) -> None:
    update_asset_perf("crypto", correct, quality)
    if correct:
        post_activity(
            f"Crypto signal correct: {symbol} — {quality:.0f} quality score",
            category="crypto", symbol=symbol, asset_class="crypto", severity="info",
        )
    elif quality < 30:
        post_activity(
            f"Crypto signal failed: {symbol} — signal filters tightening",
            category="crypto", symbol=symbol, asset_class="crypto", severity="warning",
        )


def get_crypto_summary() -> Dict:
    perf = [p for p in get_asset_class_perf() if p.get("asset_class") == "crypto"]
    f = perf[0] if perf else {}
    return {
        "universe":    CRYPTO_UNIVERSE,
        "decisions":   f.get("decisions", 0),
        "accuracy":    f.get("accuracy_pct", 0),
        "avg_quality": f.get("avg_quality", 0),
        "note":        "Crypto training runs 24/7 — no market hours restriction",
    }
