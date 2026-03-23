from __future__ import annotations

from typing import Dict, List
import time

import numpy as np
import yfinance as yf


class OpportunityMasterEngine:
    def __init__(self) -> None:
        self.symbols = [
            "NVDA", "AMD", "MSFT", "META", "GOOGL", "AMZN", "AAPL", "TSLA", "NFLX",
            "PLTR", "SNOW", "CRM", "ADBE", "ORCL",
            "AVGO", "TSM", "ASML", "MRVL", "AMAT", "KLAC", "LRCX",
            "JPM", "GS", "MS", "BAC", "C", "BLK",
            "XOM", "CVX", "XLE", "OXY", "SLB", "USO",
            "CAT", "DE", "GE", "BA", "HON",
            "LLY", "UNH", "JNJ", "PFE", "MRK",
            "COIN", "ROKU", "SHOP", "SQ", "UBER", "ABNB",
            "SPY", "QQQ", "IWM", "GLD", "SLV", "TLT", "ARM"
        ]

        self.aliases = {
            "TESLA": "TSLA",
            "GOOGLE": "GOOGL",
            "ALPHABET": "GOOGL",
            "FACEBOOK": "META",
            "APPLE": "AAPL",
            "MICROSOFT": "MSFT",
            "NVIDIA": "NVDA",
            "AMAZON": "AMZN",
            "NETFLIX": "NFLX",
            "PALANTIR": "PLTR",
            "COINBASE": "COIN",
            "GOLD": "GLD",
            "ORO": "GLD",
            "SILVER": "SLV",
            "PLATA": "SLV",
            "OIL": "USO",
            "PETROLEO": "USO",
        }

    def resolve_symbol(self, raw_symbol: str) -> str:
        value = str(raw_symbol or "").strip().upper().replace(".", "-")
        return self.aliases.get(value, value)

    def _safe_float(self, value, default: float = 0.0) -> float:
        try:
            if value is None:
                return default
            return float(value)
        except Exception:
            return default

    def _fallback(self, symbol: str) -> Dict:
        return {
            "symbol": symbol,
            "price": None,
            "price_now": None,
            "setup_score": 50,
            "traffic_light": "yellow",
            "trade_plan": {
                "action": "WAIT",
                "entry_zone": [],
                "stop_loss": "-",
                "target_1": "-",
                "target_2": "-",
                "risk_reward_estimate": "-"
            },
            "insight_lines": [f"{symbol} sin datos suficientes por ahora."],
            "summary": f"{symbol} sin datos suficientes",
            "friendly_recommendation": "No hay contexto suficiente para una entrada seria todavía.",
            "source": "fallback_safe"
        }

    def _build_trade_plan(self, price: float, score: int, volatility: float) -> Dict:
        if price <= 0:
            return {
                "action": "WAIT",
                "entry_zone": [],
                "stop_loss": "-",
                "target_1": "-",
                "target_2": "-",
                "risk_reward_estimate": "-"
            }

        band = max(0.015, min(0.08, volatility / max(price, 1.0)))
        stop_pct = max(0.025, min(0.10, band * 1.8))
        target1_pct = max(0.03, min(0.12, stop_pct * 1.2))
        target2_pct = max(0.05, min(0.20, stop_pct * 2.0))

        action = "GO" if score >= 80 else "WAIT" if score >= 60 else "AVOID"

        if action == "GO":
            entry_low = price * (1 - band * 0.5)
            entry_high = price * (1 + band * 0.35)
        elif action == "WAIT":
            entry_low = price * (1 - band)
            entry_high = price * (1 - band * 0.15)
        else:
            entry_low = price * (1 - band * 1.5)
            entry_high = price * (1 - band * 0.75)

        stop_loss = price * (1 - stop_pct)
        target_1 = price * (1 + target1_pct)
        target_2 = price * (1 + target2_pct)

        risk = max(price - stop_loss, 0.01)
        reward = max(target_1 - price, 0.01)
        rr = round(reward / risk, 2)

        return {
            "action": action,
            "entry_zone": [round(entry_low, 2), round(entry_high, 2)],
            "stop_loss": round(stop_loss, 2),
            "target_1": round(target_1, 2),
            "target_2": round(target_2, 2),
            "risk_reward_estimate": rr
        }

    def analyze_symbol(self, raw_symbol: str) -> Dict:
        symbol = self.resolve_symbol(raw_symbol)

        for _ in range(2):
            try:
                ticker = yf.Ticker(symbol)
                df = ticker.history(period="3mo", interval="1d", auto_adjust=False)

                if df is None or df.empty:
                    time.sleep(1)
                    continue

                close = df["Close"].dropna()

                if len(close) < 20:
                    return self._fallback(symbol)

                price = self._safe_float(close.iloc[-1], 0.0)
                ma20 = self._safe_float(close.rolling(20).mean().iloc[-1], price)
                ma50 = self._safe_float(close.rolling(min(50, len(close))).mean().iloc[-1], price)
                momentum_5 = ((price / self._safe_float(close.iloc[-5], price)) - 1.0) if len(close) >= 5 else 0.0
                momentum_20 = ((price / self._safe_float(close.iloc[-20], price)) - 1.0) if len(close) >= 20 else 0.0
                volatility = self._safe_float(np.std(close.tail(min(10, len(close)))), 0.0)

                score = 50

                if price > ma20:
                    score += 12
                else:
                    score -= 10

                if price > ma50:
                    score += 10
                else:
                    score -= 8

                if momentum_20 > 0.10:
                    score += 18
                elif momentum_20 > 0.03:
                    score += 10
                elif momentum_20 < -0.10:
                    score -= 18
                elif momentum_20 < 0:
                    score -= 8

                if momentum_5 > 0.03:
                    score += 8
                elif momentum_5 > 0:
                    score += 4
                elif momentum_5 < -0.03:
                    score -= 8
                elif momentum_5 < 0:
                    score -= 4

                if volatility < 5:
                    score += 4
                elif volatility > 15:
                    score -= 6

                score = max(0, min(100, int(score)))

                if score >= 80:
                    light = "green"
                elif score >= 60:
                    light = "yellow"
                else:
                    light = "red"

                trade_plan = self._build_trade_plan(price, score, volatility)

                if score >= 80:
                    friendly = "Setup fuerte. Solo entrar si confirma y con riesgo controlado."
                elif score >= 60:
                    friendly = "Setup aceptable. Mejor esperar una entrada más limpia."
                else:
                    friendly = "Ahora no es una entrada limpia. Riesgo alto frente al beneficio esperado."

                insight_lines = []
                insight_lines.append("Tendencia de corto plazo favorable." if price > ma20 else "Debilidad de corto plazo.")
                insight_lines.append("Precio sobre media intermedia." if price > ma50 else "Precio por debajo de media intermedia.")
                insight_lines.append(f"Momentum 5d: {momentum_5 * 100:.2f}%")
                insight_lines.append(f"Momentum 20d: {momentum_20 * 100:.2f}%")

                return {
                    "symbol": symbol,
                    "price": round(price, 2),
                    "price_now": round(price, 2),
                    "setup_score": score,
                    "traffic_light": light,
                    "trade_plan": trade_plan,
                    "insight_lines": insight_lines,
                    "summary": f"{symbol} | precio {round(price, 2)} | score {score} | acción {trade_plan['action']}",
                    "friendly_recommendation": friendly,
                    "source": "opportunity_master_engine"
                }

            except Exception:
                time.sleep(1)
                continue

        return self._fallback(symbol)

    def get_top_opportunities(self, limit: int = 8, force_refresh: bool = False) -> List[Dict]:
        results: List[Dict] = []

        for symbol in self.symbols:
            result = self.analyze_symbol(symbol)
            if result.get("price_now") is not None:
                results.append(result)

        results.sort(key=lambda x: x.get("setup_score", 0), reverse=True)

        green = [x for x in results if x.get("traffic_light") == "green"]
        yellow = [x for x in results if x.get("traffic_light") == "yellow"]
        red = [x for x in results if x.get("traffic_light") == "red"]

        ordered = green + yellow + red
        return ordered[:limit]
