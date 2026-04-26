from datetime import datetime
from typing import Any, Dict, List

import yfinance as yf

from core.agent_schema import build_response, degraded


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

    def analyze(self, query: str) -> Dict[str, Any]:
        """Universal schema: snapshot indices, derive regime, return decision."""
        try:
            snap = self.snapshot()
            items = snap.get("items", [])
        except Exception as exc:
            return degraded(f"Market data fetch failed: {exc}", confidence=0.2)

        if not items:
            return degraded("No market data returned — check yfinance connectivity", confidence=0.25)

        vix_item = next((x for x in items if x["label"] == "VIX"), None)
        spy_item = next((x for x in items if x["label"] == "SPY"), None)
        qqq_item = next((x for x in items if x["label"] == "QQQ"), None)

        vix      = vix_item["price"]      if vix_item else None
        spy_chg  = spy_item["change_pct"] if spy_item else None
        qqq_chg  = qqq_item["change_pct"] if qqq_item else None

        # Regime detection — same rules as /api/markets/snapshot
        if vix is None:
            return degraded("VIX data unavailable — regime cannot be assessed", confidence=0.3)

        if vix > 35:
            regime, risk_level = "FEAR", "high"
            action = (
                "Reduce equity exposure by 25–40%. Increase cash buffer to 20%. "
                "Add defensive positions: gold (GLD), short-duration treasuries (SHY). "
                "Suspend all new speculative entries."
            )
            confidence = 0.88
        elif vix > 25 and spy_chg is not None and spy_chg < 0:
            regime, risk_level = "RISK_OFF", "high"
            action = (
                "Tighten stop-losses on open equity positions to 5% trailing. "
                "Reduce leverage to below 1×. "
                "Hold cash — do not buy dips until VIX <25 confirmed."
            )
            confidence = 0.82
        elif vix > 20:
            regime, risk_level = "CAUTION", "medium"
            action = (
                "Reduce new position sizes by 30%. Avoid high-beta momentum stocks. "
                "Monitor HY credit spreads — widening precedes equity selloff by 2–3 weeks."
            )
            confidence = 0.75
        else:
            regime, risk_level = "NORMAL", "low"
            action = (
                "Normal risk environment. Execute planned positions with standard sizing (1–2% portfolio risk). "
                f"SPY {'up' if (spy_chg or 0) >= 0 else 'down'} {abs(spy_chg or 0):.2f}% — trend intact."
            )
            confidence = 0.80

        signals = [
            f"VIX: {vix:.1f} → regime={regime}",
            f"SPY: {spy_chg:+.2f}%" if spy_chg is not None else "SPY: N/A",
            f"QQQ: {qqq_chg:+.2f}%" if qqq_chg is not None else "QQQ: N/A",
        ]

        return build_response(
            confidence=confidence,
            insight=(
                f"Market regime: {regime}. VIX={vix:.1f}, "
                f"SPY {spy_chg:+.2f}%" if spy_chg is not None else f"Market regime: {regime}. VIX={vix:.1f}."
            ),
            risk_level=risk_level,
            action=action,
            reason=(
                f"VIX={vix:.1f} drives regime classification. "
                f"SPY daily change={spy_chg:+.2f}%. "
                f"Rules: VIX>35→FEAR, VIX>25+SPY<0→RISK_OFF, VIX>20→CAUTION, else→NORMAL."
            ) if spy_chg is not None else f"VIX={vix:.1f} drives regime.",
            signals_used=signals,
            data_sources=["yfinance_2d_daily", "core_watchlist_indices"],
            reasoning_path=[
                "1. Fetch SPY, QQQ, NASDAQ, VIX from yfinance",
                "2. Compute daily price change vs previous close",
                f"3. VIX={vix:.1f}: classify regime against thresholds (35/25/20)",
                f"4. Regime={regime} → risk_level={risk_level}",
                "5. Map regime to specific portfolio action with position sizing",
            ],
            data_freshness=1.0,
            data_completeness=round(len(items) / 4, 2),
        )

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