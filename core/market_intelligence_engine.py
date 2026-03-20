from datetime import datetime
from typing import Any, Dict, List

import yfinance as yf


class MarketIntelligenceEngine:
    """
    Snapshot institucional simple y robusto.
    Enfocado en lo que sí necesitas en el dashboard.
    """

    def __init__(self) -> None:
        self.core_watchlist = {
            "NASDAQ": "^IXIC",
            "SPY": "SPY",
            "QQQ": "QQQ",
            "VIX": "^VIX",
        }

    def snapshot(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat(),
            "items": [],
        }

        for label, ticker in self.core_watchlist.items():
            ticker_obj = yf.Ticker(ticker)
            hist = ticker_obj.history(period="2d", interval="1d")

            if hist.empty or len(hist) < 1:
                continue

            latest_close = float(hist["Close"].iloc[-1])
            previous_close = float(hist["Close"].iloc[-2]) if len(hist) > 1 else latest_close
            change = latest_close - previous_close
            change_pct = (change / previous_close * 100.0) if previous_close else 0.0

            result["items"].append({
                "label": label,
                "ticker": ticker,
                "price": round(latest_close, 2),
                "change": round(change, 2),
                "change_pct": round(change_pct, 2),
            })

        return result

    def analyze_symbol(self, symbol: str) -> Dict[str, Any]:
        clean = (symbol or "").strip().upper()
        if not clean:
            return {"error": "symbol is required"}

        ticker_obj = yf.Ticker(clean)
        hist = ticker_obj.history(period="6mo", interval="1d")

        if hist.empty or len(hist) < 60:
            return {"error": f"insufficient data for {clean}"}

        price = float(hist["Close"].iloc[-1])
        day_high = float(hist["High"].iloc[-1])
        day_low = float(hist["Low"].iloc[-1])

        ma20 = float(hist["Close"].rolling(20).mean().iloc[-1])
        ma50 = float(hist["Close"].rolling(50).mean().iloc[-1])

        trend = "bullish" if price > ma50 else "bearish"
        momentum = "strong" if price > ma20 and ma20 > ma50 else "neutral"

        return {
            "symbol": clean,
            "price": round(price, 2),
            "day_high": round(day_high, 2),
            "day_low": round(day_low, 2),
            "ma20": round(ma20, 2),
            "ma50": round(ma50, 2),
            "trend": trend,
            "momentum": momentum,
            "timestamp": datetime.utcnow().isoformat(),
        }