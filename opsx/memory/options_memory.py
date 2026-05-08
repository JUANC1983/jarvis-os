"""
Options Memory — tracks options flow signals and unusual activity.

Currently a structured placeholder. Will activate when options flow
data feed (unusual_whales, flowalgo, etc.) is integrated.

Architecture is complete — data ingestion is pending.
"""
from __future__ import annotations

from typing import Dict, List

from opsx.memory.ai_memory_store import post_activity

OPTIONS_UNIVERSE = ["SPY", "QQQ", "TSLA", "NVDA", "AAPL", "AMZN", "META", "MSFT"]

_options_signals: List[Dict] = []


def record_options_signal(
    symbol: str, contract_type: str, strike: float, expiry: str,
    volume: int, open_interest: int, iv: float, unusual: bool,
) -> None:
    """Record an options flow signal."""
    signal = {
        "symbol": symbol, "contract_type": contract_type,
        "strike": strike, "expiry": expiry,
        "volume": volume, "oi": open_interest,
        "iv": iv, "unusual": unusual,
    }
    _options_signals.append(signal)
    if unusual:
        post_activity(
            f"Unusual options activity: {symbol} {contract_type.upper()} ${strike} — {volume:,} contracts",
            category="options", symbol=symbol, severity="info",
        )


def get_flow_summary() -> Dict:
    return {
        "status":           "awaiting_data_feed",
        "universe":         OPTIONS_UNIVERSE,
        "tracked_signals":  len(_options_signals),
        "note":             "Options flow memory active — connect flowalgo or unusual_whales for live signals",
        "recent_signals":   _options_signals[-5:],
    }
