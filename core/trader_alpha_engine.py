from __future__ import annotations

from typing import Any, Dict

import yfinance as yf
import pandas as pd


class TraderAlphaEngine:
    """
    Premium trader engine.
    No guarantees, but built to reduce bad entries and improve structure.
    """

    def _safe_info(self, ticker: yf.Ticker) -> Dict[str, Any]:
        try:
            return ticker.info or {}
        except Exception:
            return {}

    def _history(self, symbol: str, period: str = "1y") -> pd.DataFrame:
        df = yf.Ticker(symbol).history(period=period)
        if df is None or df.empty:
            raise ValueError(f"No price history found for {symbol}")
        return df

    def _technicals(self, df: pd.DataFrame) -> Dict[str, Any]:
        close = df["Close"]
        volume = df["Volume"]

        price = float(close.iloc[-1])
        ma20 = float(close.rolling(20).mean().iloc[-1])
        ma50 = float(close.rolling(50).mean().iloc[-1])
        ma200 = float(close.rolling(200).mean().iloc[-1])

        avg_vol20 = float(volume.rolling(20).mean().iloc[-1])
        today_vol = float(volume.iloc[-1])
        volume_ratio = today_vol / avg_vol20 if avg_vol20 > 0 else 1.0

        ret5 = ((price / float(close.iloc[-6])) - 1) * 100 if len(close) > 6 else 0
        ret20 = ((price / float(close.iloc[-21])) - 1) * 100 if len(close) > 21 else 0
        ret60 = ((price / float(close.iloc[-61])) - 1) * 100 if len(close) > 61 else 0

        high_252 = float(close.tail(252).max())
        low_252 = float(close.tail(252).min())
        range_position = ((price - low_252) / (high_252 - low_252) * 100) if high_252 > low_252 else 50

        return {
            "price": round(price, 2),
            "ma20": round(ma20, 2),
            "ma50": round(ma50, 2),
            "ma200": round(ma200, 2),
            "ret5_pct": round(ret5, 2),
            "ret20_pct": round(ret20, 2),
            "ret60_pct": round(ret60, 2),
            "high_252": round(high_252, 2),
            "low_252": round(low_252, 2),
            "range_position_pct": round(range_position, 2),
            "volume_ratio": round(volume_ratio, 2),
        }

    def _trend(self, m: Dict[str, Any]) -> str:
        if m["price"] > m["ma20"] > m["ma50"] > m["ma200"]:
            return "strong_bullish"
        if m["price"] > m["ma50"] > m["ma200"]:
            return "bullish"
        if m["price"] < m["ma20"] < m["ma50"] < m["ma200"]:
            return "strong_bearish"
        if m["price"] < m["ma50"] < m["ma200"]:
            return "bearish"
        return "mixed"

    def _fomo(self, m: Dict[str, Any]) -> str:
        if m["ret20_pct"] > 18 and m["range_position_pct"] > 85:
            return "high_fomo_risk"
        if m["ret20_pct"] > 10 and m["range_position_pct"] > 70:
            return "medium_fomo_risk"
        return "controlled"

    def _fundamentals(self, info: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "market_cap": info.get("marketCap"),
            "trailing_pe": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "peg_ratio": info.get("pegRatio"),
            "revenue_growth": info.get("revenueGrowth"),
            "earnings_growth": info.get("earningsGrowth"),
            "gross_margins": info.get("grossMargins"),
            "operating_margins": info.get("operatingMargins"),
            "return_on_equity": info.get("returnOnEquity"),
            "debt_to_equity": info.get("debtToEquity"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "beta": info.get("beta"),
        }

    def _fundamental_score(self, f: Dict[str, Any]) -> int:
        score = 50

        if f["revenue_growth"] is not None and f["revenue_growth"] > 0.10:
            score += 10
        if f["earnings_growth"] is not None and f["earnings_growth"] > 0.10:
            score += 10
        if f["gross_margins"] is not None and f["gross_margins"] > 0.40:
            score += 8
        if f["operating_margins"] is not None and f["operating_margins"] > 0.15:
            score += 8
        if f["return_on_equity"] is not None and f["return_on_equity"] > 0.15:
            score += 8
        if f["debt_to_equity"] is not None and f["debt_to_equity"] > 150:
            score -= 15
        if f["trailing_pe"] is not None and f["trailing_pe"] > 50:
            score -= 8

        return max(0, min(100, score))

    def _setup_score(self, trend: str, fomo: str, m: Dict[str, Any], fscore: int) -> int:
        score = 45

        if trend == "strong_bullish":
            score += 22
        elif trend == "bullish":
            score += 15
        elif trend == "mixed":
            score += 4
        elif trend == "bearish":
            score -= 12
        elif trend == "strong_bearish":
            score -= 20

        if m["volume_ratio"] > 1.3:
            score += 10
        if m["ret60_pct"] > 12:
            score += 8
        if fomo == "high_fomo_risk":
            score -= 18
        elif fomo == "medium_fomo_risk":
            score -= 8

        score += int((fscore - 50) * 0.35)

        return max(0, min(100, score))

    def _trade_plan(self, m: Dict[str, Any], trend: str) -> Dict[str, Any]:
        price = m["price"]

        if trend in ["strong_bullish", "bullish"]:
            entry_zone = [round(max(m["ma20"], price * 0.97), 2), round(price, 2)]
            stop = round(m["ma50"] * 0.985, 2)
            t1 = round(price * 1.05, 2)
            t2 = round(price * 1.10, 2)
            action = "buy_on_pullback_or_breakout_confirmation"
            exit_logic = "take_partial_at_target1_move_stop_then_trail"
        elif trend in ["bearish", "strong_bearish"]:
            entry_zone = [round(price * 0.98, 2), round(price, 2)]
            stop = round(m["ma20"] * 1.02, 2)
            t1 = round(price * 0.95, 2)
            t2 = round(price * 0.90, 2)
            action = "avoid_long_or_short_only_if_system_allows"
            exit_logic = "respect_stop_no_hope_trading"
        else:
            entry_zone = [round(m["ma20"] * 0.99, 2), round(m["ma20"] * 1.01, 2)]
            stop = round(m["ma50"] * 0.98, 2)
            t1 = round(price * 1.03, 2)
            t2 = round(price * 1.06, 2)
            action = "wait_or_probe_small_only"
            exit_logic = "only_if_price_confirms_direction"

        rr = round(abs((t1 - price) / (price - stop)), 2) if price != stop else None

        return {
            "action": action,
            "entry_zone": entry_zone,
            "stop_loss": stop,
            "target_1": t1,
            "target_2": t2,
            "exit_logic": exit_logic,
            "risk_reward_estimate": rr,
        }

    def analyze(self, symbol: str) -> Dict[str, Any]:
        ticker = yf.Ticker(symbol)
        info = self._safe_info(ticker)
        df = self._history(symbol)
        technicals = self._technicals(df)
        trend = self._trend(technicals)
        fomo = self._fomo(technicals)
        fundamentals = self._fundamentals(info)
        fscore = self._fundamental_score(fundamentals)
        setup_score = self._setup_score(trend, fomo, technicals, fscore)
        trade_plan = self._trade_plan(technicals, trend)

        narrative = []

        if trend in ["strong_bullish", "bullish"]:
            narrative.append("Trend structure is constructive.")
        if technicals["volume_ratio"] > 1.3:
            narrative.append("Participation volume is supportive.")
        if fomo == "high_fomo_risk":
            narrative.append("Setup is extended. Avoid emotional entry.")
        if fundamentals["revenue_growth"] is not None and fundamentals["revenue_growth"] > 0.10:
            narrative.append("Revenue growth supports the story.")
        if fundamentals["debt_to_equity"] is not None and fundamentals["debt_to_equity"] > 150:
            narrative.append("Leverage risk exists.")
        if setup_score >= 75:
            narrative.append("This is a high-quality setup if timing is respected.")

        return {
            "symbol": symbol,
            "trend": trend,
            "fomo_risk": fomo,
            "fundamental_score": fscore,
            "setup_score": setup_score,
            "technicals": technicals,
            "fundamentals": fundamentals,
            "trade_plan": trade_plan,
            "narrative": narrative,
            "summary": f"{symbol}: trend={trend}, setup_score={setup_score}, fomo_risk={fomo}.",
            "warning": "No system can guarantee zero losses. Premium execution means disciplined entries, stops and sizing.",
        }
