from __future__ import annotations

from typing import Dict, Any

import yfinance as yf
import numpy as np


class ProductBrain:

    def __init__(self) -> None:
        self.available = True

    # =========================
    # HEALTH
    # =========================
    def health(self) -> dict:
        return {
            "available": True,
            "boot_errors": [],
            "orchestrator_available": True,
        }

    # =========================
    # CHAT (LIMPIO Y HUMANO)
    # =========================
    def chat(self, message: str) -> dict:
        message_lower = message.lower().strip()

        # SALUDO
        if message_lower in ["hola", "hola jarvis", "hey", "hi"]:
            return {
                "type": "chat",
                "reply": "Hola Juan. ¿Qué necesitas hoy?",
                "summary": "Saludo inicial",
                "details": {},
                "action": "",
                "confidence": 1.0,
                "source": "brain_simple"
            }

        # PEDIR TICKER
        if any(word in message_lower for word in ["accion", "stock", "trade", "ticker"]):
            return {
                "type": "chat",
                "reply": "Dime el símbolo (ej: AAPL, TSLA) y te doy el análisis.",
                "summary": "Solicitud de análisis",
                "details": {},
                "action": "ask_symbol",
                "confidence": 0.9,
                "source": "brain_simple"
            }

        # RECOMENDACIONES
        if "oportunidad" in message_lower or "recomend" in message_lower:
            recs = self.recommendations()
            items = recs.get("items", [])[:3]

            if not items:
                return {
                    "type": "chat",
                    "reply": "Ahora mismo no veo setups claros.",
                    "summary": "Sin oportunidades",
                    "details": {},
                    "action": "",
                    "confidence": 0.7,
                    "source": "brain_simple"
                }

            top = ", ".join([x["symbol"] for x in items])

            return {
                "type": "chat",
                "reply": f"Las mejores oportunidades ahora: {top}",
                "summary": "Top oportunidades",
                "details": items,
                "action": "",
                "confidence": 0.9,
                "source": "brain_simple"
            }

        # FALLBACK
        return {
            "type": "chat",
            "reply": "Dime qué necesitas: trading, tareas o algo específico.",
            "summary": "Fallback",
            "details": {},
            "action": "",
            "confidence": 0.6,
            "source": "brain_simple"
        }

    # =========================
    # TRADER
    # =========================
    def trader(self, symbol: str) -> Dict[str, Any]:
        symbol = symbol.upper()

        try:
            data = yf.Ticker(symbol).history(period="3mo")

            if data.empty:
                raise ValueError("No data")

            close = data["Close"]

            price = float(close.iloc[-1])
            sma20 = close.rolling(20).mean().iloc[-1]
            sma50 = close.rolling(50).mean().iloc[-1]

            momentum_5 = (close.iloc[-1] - close.iloc[-5]) / close.iloc[-5] * 100
            momentum_20 = (close.iloc[-1] - close.iloc[-20]) / close.iloc[-20] * 100

            score = 50

            if price > sma20:
                score += 15
            if sma20 > sma50:
                score += 15
            if momentum_5 > 0:
                score += 10
            if momentum_20 > 0:
                score += 10

            if score >= 85:
                action = "GO"
                light = "green"
            elif score >= 65:
                action = "WAIT"
                light = "yellow"
            else:
                action = "AVOID"
                light = "red"

            return {
                "symbol": symbol,
                "price": round(price, 2),
                "price_now": round(price, 2),
                "setup_score": int(score),
                "traffic_light": light,
                "trade_plan": {
                    "action": action
                },
                "insight_lines": [
                    f"Momentum 5d: {round(momentum_5,2)}%",
                    f"Momentum 20d: {round(momentum_20,2)}%"
                ],
                "summary": f"{symbol} | score {int(score)} | {action}",
                "friendly_recommendation": "Entrar solo si confirma estructura.",
                "source": "product_brain"
            }

        except Exception:
            return {
                "symbol": symbol,
                "price": None,
                "price_now": None,
                "setup_score": 0,
                "traffic_light": "red",
                "trade_plan": {"action": "AVOID"},
                "insight_lines": ["No hay datos suficientes."],
                "summary": f"{symbol} sin datos",
                "friendly_recommendation": "No operar.",
                "source": "product_brain"
            }

    # =========================
    # RECOMENDACIONES
    # =========================
    def recommendations(self) -> Dict[str, Any]:
        symbols = [
            "NVDA", "AMD", "META", "MSFT", "GOOGL",
            "PLTR", "COIN", "ARM", "MRVL",
            "XOM", "CVX", "OXY", "XLE", "USO"
        ]

        results = []

        for s in symbols:
            r = self.trader(s)
            if r["price"] is not None:
                results.append(r)

        results = sorted(results, key=lambda x: x["setup_score"], reverse=True)

        return {"items": results[:8]}

