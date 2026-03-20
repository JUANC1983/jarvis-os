from __future__ import annotations

from typing import Any, Dict, List

import feedparser
import pandas as pd
import yfinance as yf


class GlobalMarketIntelligenceSystem:
    """
    Global market intelligence layer for JARVIS.

    Purpose:
    - monitor cross-asset conditions
    - classify risk / opportunity regimes
    - detect commodity and volatility stress
    - summarize live news headlines
    - generate executive-level strategic guidance
    """

    def __init__(self) -> None:
        self.market_watch = {
            "SPY": "US Equities",
            "QQQ": "US Growth",
            "IWM": "Small Caps",
            "EEM": "Emerging Markets",
            "XLE": "Energy Equities",
            "XLF": "Financials",
            "XLK": "Technology",
            "GLD": "Gold",
            "SLV": "Silver",
            "TLT": "Long Bonds",
            "USO": "Oil ETF",
            "BTC-USD": "Bitcoin",
            "ETH-USD": "Ethereum",
            "^VIX": "Volatility Index",
            "^TNX": "US 10Y Yield",
            "DX-Y.NYB": "US Dollar Index",
            "CL=F": "Crude Oil Futures",
            "GC=F": "Gold Futures",
        }

        self.news_sources = {
            "reuters_world": "http://feeds.reuters.com/Reuters/worldNews",
            "reuters_business": "http://feeds.reuters.com/reuters/businessNews",
        }

    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        try:
            if value is None:
                return default
            return float(value)
        except Exception:
            return default

    def _history(self, symbol: str, period: str = "3mo", interval: str = "1d") -> pd.DataFrame:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=period, interval=interval, auto_adjust=False)
        if hist is None or hist.empty:
            raise ValueError(f"No history available for {symbol}")
        hist = hist.dropna(subset=["Close"]).copy()
        if hist.empty:
            raise ValueError(f"No close history available for {symbol}")
        return hist

    def market_snapshot(self) -> List[Dict[str, Any]]:
        snapshot: List[Dict[str, Any]] = []

        for symbol, label in self.market_watch.items():
            try:
                hist = self._history(symbol, period="1mo", interval="1d")
                close = hist["Close"]

                last_price = self._safe_float(close.iloc[-1])
                prev_price = self._safe_float(close.iloc[-2], last_price) if len(close) > 1 else last_price
                month_start = self._safe_float(close.iloc[0], last_price)

                day_change = ((last_price / prev_price) - 1.0) * 100.0 if prev_price else 0.0
                month_change = ((last_price / month_start) - 1.0) * 100.0 if month_start else 0.0

                snapshot.append(
                    {
                        "symbol": symbol,
                        "label": label,
                        "price": round(last_price, 4),
                        "day_change_pct": round(day_change, 2),
                        "month_change_pct": round(month_change, 2),
                    }
                )
            except Exception as exc:
                snapshot.append(
                    {
                        "symbol": symbol,
                        "label": label,
                        "error": str(exc),
                    }
                )

        return snapshot

    def commodity_regime(self) -> Dict[str, Any]:
        result = {
            "oil_signal": "neutral",
            "gold_signal": "neutral",
            "summary": "Commodity regime not yet classified.",
        }

        try:
            oil = self._history("CL=F", period="3mo")
            gold = self._history("GC=F", period="3mo")

            oil_last = self._safe_float(oil["Close"].iloc[-1])
            oil_ma20 = self._safe_float(oil["Close"].tail(20).mean(), oil_last)

            gold_last = self._safe_float(gold["Close"].iloc[-1])
            gold_ma20 = self._safe_float(gold["Close"].tail(20).mean(), gold_last)

            if oil_last > oil_ma20 * 1.04:
                result["oil_signal"] = "bullish_energy_pressure"
            elif oil_last < oil_ma20 * 0.96:
                result["oil_signal"] = "weakening_energy_pressure"

            if gold_last > gold_ma20 * 1.03:
                result["gold_signal"] = "flight_to_safety_or_inflation_hedge"
            elif gold_last < gold_ma20 * 0.97:
                result["gold_signal"] = "gold_softening"

            result["summary"] = (
                f"Oil signal: {result['oil_signal']}. "
                f"Gold signal: {result['gold_signal']}."
            )
        except Exception as exc:
            result["summary"] = f"Commodity regime unavailable: {exc}"

        return result

    def volatility_and_liquidity_regime(self) -> Dict[str, Any]:
        result = {
            "volatility_regime": "neutral",
            "rates_regime": "neutral",
            "dollar_regime": "neutral",
            "macro_liquidity_state": "neutral",
            "summary": "Volatility and liquidity regime not yet classified.",
        }

        try:
            vix = self._history("^VIX", period="3mo")
            tnx = self._history("^TNX", period="3mo")
            dxy = self._history("DX-Y.NYB", period="3mo")

            vix_last = self._safe_float(vix["Close"].iloc[-1])
            tnx_last = self._safe_float(tnx["Close"].iloc[-1])
            dxy_last = self._safe_float(dxy["Close"].iloc[-1])

            vix_ma20 = self._safe_float(vix["Close"].tail(20).mean(), vix_last)
            tnx_ma20 = self._safe_float(tnx["Close"].tail(20).mean(), tnx_last)
            dxy_ma20 = self._safe_float(dxy["Close"].tail(20).mean(), dxy_last)

            if vix_last > max(22.0, vix_ma20 * 1.12):
                result["volatility_regime"] = "stress"
            elif vix_last < min(16.0, vix_ma20 * 0.95):
                result["volatility_regime"] = "calm"

            if tnx_last > tnx_ma20 * 1.05:
                result["rates_regime"] = "rates_up_pressure"
            elif tnx_last < tnx_ma20 * 0.95:
                result["rates_regime"] = "rates_relief"

            if dxy_last > dxy_ma20 * 1.02:
                result["dollar_regime"] = "dollar_strength"
            elif dxy_last < dxy_ma20 * 0.98:
                result["dollar_regime"] = "dollar_softness"

            if result["volatility_regime"] == "stress" or result["rates_regime"] == "rates_up_pressure":
                result["macro_liquidity_state"] = "tightening_or_stressed"
            elif result["volatility_regime"] == "calm" and result["rates_regime"] == "rates_relief":
                result["macro_liquidity_state"] = "supportive"
            else:
                result["macro_liquidity_state"] = "mixed"

            result["summary"] = (
                f"Vol regime: {result['volatility_regime']}. "
                f"Rates regime: {result['rates_regime']}. "
                f"Dollar regime: {result['dollar_regime']}. "
                f"Liquidity state: {result['macro_liquidity_state']}."
            )
        except Exception as exc:
            result["summary"] = f"Liquidity regime unavailable: {exc}"

        return result

    def sector_rotation(self) -> Dict[str, Any]:
        sectors = ["XLK", "XLE", "XLF", "XLI", "XLV", "XLP"]
        rows: List[Dict[str, Any]] = []

        for symbol in sectors:
            try:
                hist = self._history(symbol, period="3mo")
                close = hist["Close"]
                ret20 = ((self._safe_float(close.iloc[-1]) / self._safe_float(close.iloc[-21])) - 1.0) * 100.0 if len(close) > 21 else 0.0
                rows.append({"symbol": symbol, "ret20_pct": round(ret20, 2)})
            except Exception:
                pass

        leaders = sorted(rows, key=lambda x: x["ret20_pct"], reverse=True)[:3]
        laggards = sorted(rows, key=lambda x: x["ret20_pct"])[:3]

        return {
            "leaders": leaders,
            "laggards": laggards,
            "summary": "Sector rotation classified from last 20 trading sessions.",
        }

    def crypto_risk_view(self) -> Dict[str, Any]:
        symbols = ["BTC-USD", "ETH-USD"]
        payload: List[Dict[str, Any]] = []

        for symbol in symbols:
            try:
                hist = self._history(symbol, period="3mo")
                close = hist["Close"]
                last_price = self._safe_float(close.iloc[-1])
                ma20 = self._safe_float(close.tail(20).mean(), last_price)
                ma50 = self._safe_float(close.tail(50).mean(), last_price)
                trend = "neutral"
                if last_price > ma20 and ma20 > ma50:
                    trend = "bullish"
                elif last_price < ma20 and ma20 < ma50:
                    trend = "bearish"

                payload.append(
                    {
                        "symbol": symbol,
                        "price": round(last_price, 4),
                        "trend": trend,
                    }
                )
            except Exception as exc:
                payload.append({"symbol": symbol, "error": str(exc)})

        return {
            "crypto_view": payload,
            "summary": "Crypto trend classification generated from price structure.",
        }

    def news_brief(self, limit_per_source: int = 5) -> Dict[str, Any]:
        items: List[Dict[str, str]] = []
        seen = set()

        for source, url in self.news_sources.items():
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:limit_per_source]:
                    title = entry.get("title", "").strip()
                    link = entry.get("link", "").strip()

                    if not title:
                        continue

                    key = (title.lower(), link)
                    if key in seen:
                        continue

                    seen.add(key)
                    items.append(
                        {
                            "source": source,
                            "title": title,
                            "link": link,
                        }
                    )
            except Exception:
                continue

        return {
            "items": items,
            "summary": f"Collected {len(items)} live headline items.",
        }

    def risk_matrix(self) -> Dict[str, Any]:
        volatility = self.volatility_and_liquidity_regime()
        commodities = self.commodity_regime()

        risk_flags: List[str] = []
        opportunity_flags: List[str] = []

        if volatility.get("volatility_regime") == "stress":
            risk_flags.append("Volatility stress detected.")

        if volatility.get("rates_regime") == "rates_up_pressure":
            risk_flags.append("Rates pressure may compress multiples and risk appetite.")

        if commodities.get("oil_signal") == "bullish_energy_pressure":
            risk_flags.append("Energy inflation / supply shock risk rising.")
            opportunity_flags.append("Energy-linked assets may outperform.")

        if commodities.get("gold_signal") == "flight_to_safety_or_inflation_hedge":
            opportunity_flags.append("Hard-asset hedge behavior detected in gold.")

        if volatility.get("macro_liquidity_state") == "supportive":
            opportunity_flags.append("Liquidity backdrop may support risk assets.")
        elif volatility.get("macro_liquidity_state") == "tightening_or_stressed":
            risk_flags.append("Macro liquidity backdrop is stressed / tightening.")

        return {
            "risk_flags": risk_flags,
            "opportunity_flags": opportunity_flags,
            "summary": "Risk matrix generated from volatility, rates, dollar, and commodity conditions.",
        }

    def scan(self) -> Dict[str, Any]:
        snapshot = self.market_snapshot()
        commodity = self.commodity_regime()
        volatility = self.volatility_and_liquidity_regime()
        sectors = self.sector_rotation()
        crypto = self.crypto_risk_view()
        news = self.news_brief()
        matrix = self.risk_matrix()

        executive_summary_parts = [
            "Global market intelligence scan complete.",
            commodity.get("summary", ""),
            volatility.get("summary", ""),
            matrix.get("summary", ""),
        ]

        return {
            "executive_summary": " ".join([p for p in executive_summary_parts if p]),
            "market_snapshot": snapshot,
            "commodity_regime": commodity,
            "volatility_and_liquidity_regime": volatility,
            "sector_rotation": sectors,
            "crypto_risk_view": crypto,
            "news_brief": news,
            "risk_matrix": matrix,
        }
