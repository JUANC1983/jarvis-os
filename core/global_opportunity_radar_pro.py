from __future__ import annotations

from typing import Any, Dict, List, Optional
import math

import pandas as pd
import yfinance as yf

from core.global_signal_engine import GlobalSignalEngine
from core.macro_liquidity_engine import MacroLiquidityEngine
from core.geopolitical_intelligence_engine import GeopoliticalIntelligenceEngine
from core.narrative_detection_engine import NarrativeDetectionEngine
from core.macro_regime_engine import MacroRegimeEngine
from core.global_market_intelligence_system import GlobalMarketIntelligenceSystem


class GlobalOpportunityRadarPro:
    """
    Institutional-grade opportunity radar.

    Goals:
    - detect deep value reversion candidates
    - detect upside acceleration candidates
    - combine price structure + macro context + risk regime
    - output ranked opportunities with executive reasoning
    """

    def __init__(self) -> None:
        self.signal_engine = GlobalSignalEngine()
        self.liquidity_engine = MacroLiquidityEngine()
        self.geo_engine = GeopoliticalIntelligenceEngine()
        self.narrative_engine = NarrativeDetectionEngine()
        self.regime_engine = MacroRegimeEngine()
        self.market_intel_engine = GlobalMarketIntelligenceSystem()

        self.default_watchlist = [
            "SPY", "QQQ", "IWM", "EEM",
            "XLE", "XLF", "XLK", "XLI", "XLV",
            "GLD", "SLV", "TLT", "USO",
            "CL=F", "GC=F", "SI=F", "HG=F",
            "BTC-USD", "ETH-USD",
            "NVDA", "AAPL", "MSFT", "AMZN", "META", "TSLA",
            "JPM", "BAC", "CVX", "XOM", "COP", "OXY",
        ]

    def get_default_watchlist(self) -> List[str]:
        return self.default_watchlist

    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        try:
            if value is None:
                return default
            if isinstance(value, float) and math.isnan(value):
                return default
            return float(value)
        except Exception:
            return default

    def _history(self, symbol: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=period, interval=interval, auto_adjust=False)

        if hist is None or hist.empty:
            raise ValueError(f"No history available for {symbol}")

        hist = hist.copy()
        hist = hist.dropna(subset=["Close"])
        if hist.empty:
            raise ValueError(f"No close data available for {symbol}")

        return hist

    def _metrics(self, hist: pd.DataFrame) -> Dict[str, float]:
        close = hist["Close"].copy()

        price = self._safe_float(close.iloc[-1])
        high_252 = self._safe_float(close.tail(252).max(), price)
        low_252 = self._safe_float(close.tail(252).min(), price)

        ma20 = self._safe_float(close.tail(20).mean(), price)
        ma50 = self._safe_float(close.tail(50).mean(), price)
        ma200 = self._safe_float(close.tail(200).mean(), price)

        ret20 = ((price / self._safe_float(close.iloc[-21], price)) - 1.0) * 100.0 if len(close) > 21 else 0.0
        ret60 = ((price / self._safe_float(close.iloc[-61], price)) - 1.0) * 100.0 if len(close) > 61 else 0.0
        ret120 = ((price / self._safe_float(close.iloc[-121], price)) - 1.0) * 100.0 if len(close) > 121 else 0.0

        drawdown_from_high = ((price / high_252) - 1.0) * 100.0 if high_252 else 0.0
        rebound_from_low = ((price / low_252) - 1.0) * 100.0 if low_252 else 0.0

        dist_ma20 = ((price / ma20) - 1.0) * 100.0 if ma20 else 0.0
        dist_ma50 = ((price / ma50) - 1.0) * 100.0 if ma50 else 0.0
        dist_ma200 = ((price / ma200) - 1.0) * 100.0 if ma200 else 0.0

        daily_returns = close.pct_change().dropna()
        vol20 = self._safe_float(daily_returns.tail(20).std() * 100.0, 0.0)
        vol60 = self._safe_float(daily_returns.tail(60).std() * 100.0, 0.0)

        range_position = 50.0
        if high_252 > low_252:
            range_position = ((price - low_252) / (high_252 - low_252)) * 100.0

        return {
            "price": round(price, 4),
            "high_252": round(high_252, 4),
            "low_252": round(low_252, 4),
            "ma20": round(ma20, 4),
            "ma50": round(ma50, 4),
            "ma200": round(ma200, 4),
            "ret20_pct": round(ret20, 2),
            "ret60_pct": round(ret60, 2),
            "ret120_pct": round(ret120, 2),
            "drawdown_from_high_pct": round(drawdown_from_high, 2),
            "rebound_from_low_pct": round(rebound_from_low, 2),
            "dist_ma20_pct": round(dist_ma20, 2),
            "dist_ma50_pct": round(dist_ma50, 2),
            "dist_ma200_pct": round(dist_ma200, 2),
            "vol20": round(vol20, 4),
            "vol60": round(vol60, 4),
            "range_position_pct": round(range_position, 2),
        }

    def _cheapness_score(self, m: Dict[str, float]) -> int:
        score = 0

        if m["drawdown_from_high_pct"] <= -30:
            score += 30
        elif m["drawdown_from_high_pct"] <= -20:
            score += 22
        elif m["drawdown_from_high_pct"] <= -10:
            score += 12

        if m["dist_ma200_pct"] <= -15:
            score += 20
        elif m["dist_ma200_pct"] <= -8:
            score += 12

        if m["range_position_pct"] <= 25:
            score += 18
        elif m["range_position_pct"] <= 40:
            score += 10

        if m["ret20_pct"] > 2:
            score += 8
        if m["ret60_pct"] > 5:
            score += 8

        if m["vol20"] > 3:
            score += 6

        return max(0, min(100, int(score)))

    def _momentum_score(self, m: Dict[str, float]) -> int:
        score = 0

        if m["ret20_pct"] >= 10:
            score += 25
        elif m["ret20_pct"] >= 5:
            score += 18
        elif m["ret20_pct"] >= 2:
            score += 10

        if m["ret60_pct"] >= 18:
            score += 24
        elif m["ret60_pct"] >= 10:
            score += 16
        elif m["ret60_pct"] >= 5:
            score += 8

        if m["dist_ma50_pct"] > 0:
            score += 12
        if m["dist_ma200_pct"] > 0:
            score += 12
        if m["range_position_pct"] >= 70:
            score += 15
        elif m["range_position_pct"] >= 55:
            score += 8

        return max(0, min(100, int(score)))

    def _risk_score(self, m: Dict[str, float]) -> int:
        score = 25

        if m["vol20"] >= 4:
            score += 24
        elif m["vol20"] >= 2.5:
            score += 14

        if m["ret20_pct"] < -8:
            score += 16
        elif m["ret20_pct"] < -3:
            score += 8

        if m["dist_ma200_pct"] < -18:
            score += 12

        if m["range_position_pct"] < 20:
            score += 8

        return max(0, min(100, int(score)))

    def _macro_overlay(self, topic: str, context: str) -> Dict[str, Any]:
        liquidity = self.liquidity_engine.analyze()
        geo = self.geo_engine.analyze(topic, context)
        narrative = self.narrative_engine.analyze(topic, context)
        regime = self.regime_engine.analyze(topic, context)
        market_risk = self.market_intel_engine.risk_matrix()

        supportive_bias = 0
        restrictive_bias = 0
        tags: List[str] = []

        if liquidity.get("liquidity_state") in {"expansion", "supportive"}:
            supportive_bias += 10
            tags.append("supportive_liquidity")
        elif liquidity.get("liquidity_state") in {"tightening", "tightening_or_stressed"}:
            restrictive_bias += 12
            tags.append("tight_liquidity")

        if geo.get("opportunities"):
            supportive_bias += 8
            tags.append("geo_opportunity")
        if geo.get("risks"):
            restrictive_bias += 10
            tags.append("geo_risk")

        if narrative.get("dominant_narratives"):
            tags.extend(narrative.get("dominant_narratives", [])[:2])

        if market_risk.get("risk_flags"):
            restrictive_bias += min(15, len(market_risk.get("risk_flags", [])) * 5)

        if market_risk.get("opportunity_flags"):
            supportive_bias += min(15, len(market_risk.get("opportunity_flags", [])) * 5)

        return {
            "supportive_bias": supportive_bias,
            "restrictive_bias": restrictive_bias,
            "net_macro_score": supportive_bias - restrictive_bias,
            "tags": tags[:8],
            "liquidity": liquidity,
            "geopolitical": geo,
            "narrative": narrative,
            "regime": regime,
            "risk_matrix": market_risk,
        }

    def _classify(self, cheapness: int, momentum: int, risk: int, macro_net: int) -> str:
        if cheapness >= 65 and momentum >= 40 and macro_net >= -5:
            return "cheap_but_turning"
        if cheapness >= 70 and momentum < 40:
            return "deep_value_watch"
        if momentum >= 75 and risk <= 60 and macro_net >= -10:
            return "upside_acceleration"
        if momentum >= 65 and risk > 60:
            return "high_beta_momentum"
        if cheapness < 35 and momentum < 35:
            return "no_clear_edge"
        return "mixed_opportunity"

    def analyze_symbol(self, symbol: str, topic: str = "", context: str = "") -> Dict[str, Any]:
        hist = self._history(symbol)
        metrics = self._metrics(hist)
        macro = self._macro_overlay(topic, context)

        cheapness = self._cheapness_score(metrics)
        momentum = self._momentum_score(metrics)
        risk = self._risk_score(metrics)
        macro_net = int(macro["net_macro_score"])

        classification = self._classify(cheapness, momentum, risk, macro_net)

        conviction = int(round(
            (cheapness * 0.28) +
            (momentum * 0.32) +
            (max(0, macro_net + 20) * 0.8) -
            (risk * 0.18)
        ))
        conviction = max(0, min(100, conviction))

        recommendation = "watch"
        if conviction >= 75 and risk <= 65:
            recommendation = "high_priority"
        elif conviction >= 60:
            recommendation = "watch_closely"
        elif conviction < 40:
            recommendation = "avoid_for_now"

        return {
            "symbol": symbol,
            "classification": classification,
            "recommendation": recommendation,
            "cheapness_score": cheapness,
            "momentum_score": momentum,
            "risk_score": risk,
            "macro_net_score": macro_net,
            "conviction_score": conviction,
            "metrics": metrics,
            "macro_overlay": {
                "net_macro_score": macro["net_macro_score"],
                "tags": macro["tags"],
            },
            "summary": (
                f"{symbol} classified as {classification}. "
                f"Cheapness={cheapness}, Momentum={momentum}, Risk={risk}, "
                f"Macro={macro_net}, Conviction={conviction}."
            ),
        }

    def scan(self, topic: str = "", context: str = "", symbols: Optional[List[str]] = None) -> Dict[str, Any]:
        symbols = symbols or self.default_watchlist

        results: List[Dict[str, Any]] = []
        errors: List[Dict[str, str]] = []

        for symbol in symbols:
            try:
                results.append(self.analyze_symbol(symbol, topic=topic, context=context))
            except Exception as exc:
                errors.append({"symbol": symbol, "error": str(exc)})

        deep_value = sorted(results, key=lambda x: (x["cheapness_score"], x["conviction_score"]), reverse=True)[:8]
        momentum = sorted(results, key=lambda x: (x["momentum_score"], x["conviction_score"]), reverse=True)[:8]
        top_convictions = sorted(results, key=lambda x: x["conviction_score"], reverse=True)[:10]
        high_priority = [r for r in top_convictions if r["recommendation"] == "high_priority"][:5]

        market_snapshot = self.market_intel_engine.market_snapshot()
        risk_matrix = self.market_intel_engine.risk_matrix()

        return {
            "topic": topic,
            "context": context,
            "symbols_scanned": symbols,
            "results_count": len(results),
            "errors": errors,
            "deep_value_candidates": deep_value,
            "momentum_candidates": momentum,
            "top_convictions": top_convictions,
            "high_priority_setups": high_priority,
            "market_snapshot": market_snapshot,
            "risk_matrix": risk_matrix,
            "executive_summary": (
                "Global Opportunity Radar Pro completed institutional scan. "
                "Use deep_value_candidates for assets that became cheap and may turn. "
                "Use momentum_candidates for assets already under constructive upside pressure. "
                "Use high_priority_setups for the strongest combined cases."
            ),
        }
