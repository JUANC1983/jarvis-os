from __future__ import annotations

from typing import Any, Dict, List
import math

import pandas as pd
import yfinance as yf


class PremiumOpportunityEngine:
    """
    Premium opportunity engine.

    What it tries to detect:
    1. Assets that became cheap and may be mean-reverting.
    2. Assets already under upside pressure / acceleration.
    3. High-volatility assets with asymmetric setups.
    4. Theme-aware interpretation using topic + context.
    """

    def __init__(self) -> None:
        self.default_watchlist = [
            "SPY",
            "QQQ",
            "IWM",
            "EEM",
            "XLE",
            "XLK",
            "XLF",
            "GLD",
            "SLV",
            "TLT",
            "USO",
            "UNG",
            "CL=F",
            "GC=F",
            "SI=F",
            "HG=F",
            "BTC-USD",
            "ETH-USD",
            "NVDA",
            "AAPL",
            "AMZN",
            "META",
            "TSLA",
        ]

    def get_default_watchlist(self) -> List[str]:
        return self.default_watchlist

    def _history(self, symbol: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=period, interval=interval, auto_adjust=False)

        if hist is None or hist.empty:
            raise ValueError(f"No history available for {symbol}")

        hist = hist.copy()
        hist = hist.dropna(subset=["Close"])
        if hist.empty:
            raise ValueError(f"Close history unavailable for {symbol}")

        return hist

    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        try:
            if value is None or (isinstance(value, float) and math.isnan(value)):
                return default
            return float(value)
        except Exception:
            return default

    def _calc_metrics(self, hist: pd.DataFrame) -> Dict[str, float]:
        close = hist["Close"].copy()

        price = self._safe_float(close.iloc[-1])
        high_252 = self._safe_float(close.tail(252).max(), price)
        low_252 = self._safe_float(close.tail(252).min(), price)

        ma20 = self._safe_float(close.tail(20).mean(), price)
        ma50 = self._safe_float(close.tail(50).mean(), price)
        ma200 = self._safe_float(close.tail(200).mean(), price)

        ret20 = self._safe_float((price / self._safe_float(close.iloc[-21], price) - 1.0) * 100.0, 0.0) if len(close) > 21 else 0.0
        ret60 = self._safe_float((price / self._safe_float(close.iloc[-61], price) - 1.0) * 100.0, 0.0) if len(close) > 61 else 0.0
        ret120 = self._safe_float((price / self._safe_float(close.iloc[-121], price) - 1.0) * 100.0, 0.0) if len(close) > 121 else 0.0

        drawdown_from_high = self._safe_float(((price / high_252) - 1.0) * 100.0, 0.0) if high_252 else 0.0
        rebound_from_low = self._safe_float(((price / low_252) - 1.0) * 100.0, 0.0) if low_252 else 0.0

        dist_ma20 = self._safe_float(((price / ma20) - 1.0) * 100.0, 0.0) if ma20 else 0.0
        dist_ma50 = self._safe_float(((price / ma50) - 1.0) * 100.0, 0.0) if ma50 else 0.0
        dist_ma200 = self._safe_float(((price / ma200) - 1.0) * 100.0, 0.0) if ma200 else 0.0

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

        if m["drawdown_from_high_pct"] <= -25:
            score += 28
        elif m["drawdown_from_high_pct"] <= -15:
            score += 18
        elif m["drawdown_from_high_pct"] <= -8:
            score += 10

        if m["dist_ma200_pct"] <= -15:
            score += 22
        elif m["dist_ma200_pct"] <= -8:
            score += 12

        if m["range_position_pct"] <= 30:
            score += 20
        elif m["range_position_pct"] <= 45:
            score += 10

        if m["ret20_pct"] > 3:
            score += 12

        if m["ret60_pct"] > 5:
            score += 8

        if m["vol20"] > 3:
            score += 6

        return max(0, min(100, int(score)))

    def _upside_pressure_score(self, m: Dict[str, float]) -> int:
        score = 0

        if m["ret20_pct"] >= 8:
            score += 24
        elif m["ret20_pct"] >= 4:
            score += 16
        elif m["ret20_pct"] >= 1:
            score += 8

        if m["ret60_pct"] >= 15:
            score += 22
        elif m["ret60_pct"] >= 8:
            score += 14
        elif m["ret60_pct"] >= 3:
            score += 8

        if m["dist_ma50_pct"] > 0:
            score += 14
        if m["dist_ma200_pct"] > 0:
            score += 14

        if m["range_position_pct"] >= 70:
            score += 16
        elif m["range_position_pct"] >= 55:
            score += 8

        if m["dist_ma20_pct"] > 0:
            score += 10

        return max(0, min(100, int(score)))

    def _risk_score(self, m: Dict[str, float]) -> int:
        score = 30

        if m["vol20"] >= 4:
            score += 22
        elif m["vol20"] >= 2.5:
            score += 12

        if m["ret20_pct"] < -8:
            score += 18
        elif m["ret20_pct"] < -3:
            score += 10

        if m["dist_ma200_pct"] < -20:
            score += 14

        if m["range_position_pct"] < 20:
            score += 8

        return max(0, min(100, int(score)))

    def _classification(self, cheapness: int, upside: int, risk: int) -> str:
        if cheapness >= 65 and upside >= 45:
            return "cheap_but_recovering"
        if cheapness >= 70 and upside < 40:
            return "deep_value_watch"
        if upside >= 75 and risk <= 60:
            return "upside_acceleration"
        if upside >= 70 and risk > 60:
            return "high_beta_momentum"
        if cheapness < 40 and upside < 40:
            return "no_edge_detected"
        return "mixed_setup"

    def _theme_overlay(self, topic: str, context: str) -> Dict[str, Any]:
        text = f"{topic} {context}".lower()

        bias = "neutral"
        catalysts: List[str] = []
        risks: List[str] = []

        if any(w in text for w in ["oil", "petroleo", "war", "middle east", "iran", "israel", "energy"]):
            bias = "energy_bullish_if_supply_shock"
            catalysts.extend([
                "Supply disruption",
                "Shipping risk",
                "Energy inflation pass-through",
            ])
            risks.extend([
                "Policy intervention",
                "Fast reversal on de-escalation",
            ])

        if any(w in text for w in ["gold", "oro", "inflation", "usd", "dollar", "rates"]):
            bias = "hard_assets_supportive"
            catalysts.extend([
                "Inflation hedge demand",
                "Rates uncertainty",
                "Dollar weakness scenario",
            ])
            risks.extend([
                "Higher real yields",
                "Narrative reversal",
            ])

        if any(w in text for w in ["ai", "semiconductor", "chips", "nvidia", "compute"]):
            bias = "structural_growth_supportive"
            catalysts.extend([
                "Compute demand",
                "Capital expenditure cycle",
                "Narrative momentum",
            ])
            risks.extend([
                "Crowded positioning",
                "Valuation compression",
            ])

        return {
            "theme_bias": bias,
            "theme_catalysts": catalysts,
            "theme_risks": risks,
        }

    def analyze_symbol(self, symbol: str, topic: str = "", context: str = "") -> Dict[str, Any]:
        hist = self._history(symbol)
        metrics = self._calc_metrics(hist)

        cheapness = self._cheapness_score(metrics)
        upside = self._upside_pressure_score(metrics)
        risk = self._risk_score(metrics)
        classification = self._classification(cheapness, upside, risk)
        overlay = self._theme_overlay(topic, context)

        conviction_score = int(round((cheapness * 0.35) + (upside * 0.45) - (risk * 0.20)))
        conviction_score = max(0, min(100, conviction_score))

        return {
            "symbol": symbol,
            "classification": classification,
            "cheapness_score": cheapness,
            "upside_pressure_score": upside,
            "risk_score": risk,
            "conviction_score": conviction_score,
            "metrics": metrics,
            "theme_overlay": overlay,
            "summary": (
                f"{symbol} classified as {classification}. "
                f"Cheapness={cheapness}, UpsidePressure={upside}, Risk={risk}, Conviction={conviction_score}."
            ),
        }

    def scan_symbols(self, symbols: List[str], topic: str = "", context: str = "") -> Dict[str, Any]:
        results: List[Dict[str, Any]] = []
        errors: List[Dict[str, str]] = []

        for symbol in symbols:
            try:
                results.append(self.analyze_symbol(symbol, topic=topic, context=context))
            except Exception as exc:
                errors.append({"symbol": symbol, "error": str(exc)})

        cheap_candidates = sorted(results, key=lambda x: (x["cheapness_score"], x["conviction_score"]), reverse=True)[:7]
        upside_candidates = sorted(results, key=lambda x: (x["upside_pressure_score"], x["conviction_score"]), reverse=True)[:7]
        top_convictions = sorted(results, key=lambda x: x["conviction_score"], reverse=True)[:7]

        return {
            "topic": topic,
            "context": context,
            "symbols_scanned": symbols,
            "results_count": len(results),
            "errors": errors,
            "deep_value_reversion_candidates": cheap_candidates,
            "upside_acceleration_candidates": upside_candidates,
            "top_convictions": top_convictions,
        }

    def premium_scan(self, topic: str = "", context: str = "", symbols: List[str] | None = None) -> Dict[str, Any]:
        symbols = symbols or self.default_watchlist
        payload = self.scan_symbols(symbols=symbols, topic=topic, context=context)

        return {
            **payload,
            "executive_summary": (
                "Premium opportunity scan complete. "
                "Use deep_value_reversion_candidates to find assets that became cheap and may turn. "
                "Use upside_acceleration_candidates to find assets already under upward pressure. "
                "Use top_convictions for the strongest combined setups."
            ),
        }
