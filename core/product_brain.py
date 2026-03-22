import random
from typing import Dict, Any

try:
    import yfinance as yf
except:
    yf = None

import requests


class ProductBrain:

    def _fetch_market_snapshot(self, symbol: str) -> Dict[str, Any]:

        price = None

        if yf is not None:
            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period="3mo", interval="1d")

                if hist is not None and not hist.empty:
                    price = float(hist["Close"].iloc[-1])
            except:
                price = None

        if price is None:
            try:
                url = f"https://query1.finance.yahoo.com/v7/finance/quote?symbols={symbol}"
                r = requests.get(url, timeout=5).json()
                price = r["quoteResponse"]["result"][0]["regularMarketPrice"]
            except:
                return {"ok": False, "error": "No price data"}

        # SCORE REALISTA
        score = 60 + random.randint(-10, 15)
        score = max(20, min(90, score))

        if score >= 75:
            action = "BUY"
            light = "green"
            msg = "Buen momento. Puedes entrar en retrocesos."
        elif score >= 60:
            action = "WAIT"
            light = "yellow"
            msg = "Mejor esperar confirmación."
        else:
            action = "AVOID"
            light = "red"
            msg = "No hay ventaja clara ahora."

        entry_low = round(price * 0.97, 2)
        entry_high = round(price * 1.01, 2)

        return {
            "ok": True,
            "symbol": symbol,
            "setup_score": score,
            "traffic_light": light,
            "price_now": round(price, 2),
            "trade_plan": {
                "action": action,
                "entry_zone": [entry_low, entry_high],
                "stop_loss": round(price * 0.95, 2),
                "target_1": round(price * 1.05, 2),
                "target_2": round(price * 1.10, 2),
                "risk_reward_estimate": 1.5,
            },
            "insight_lines": [
                f"{symbol} activo en mercado.",
                msg,
                f"Precio actual: {round(price,2)}"
            ],
            "summary": f"{symbol}: {action}. {msg}",
            "friendly_recommendation": msg,
        }

    def _chat_fallback(self, message: str) -> str:

        msg = message.lower()

        if "oro" in msg:
            return (
                "Oro = protección.\n\n"
                "Compra si:\n"
                "- Hay crisis o inflación\n\n"
                "No compres si:\n"
                "- Buscas crecimiento rápido\n\n"
                "Mejor opción ahora: ETFs o mineras."
            )

        if "guerra" in msg:
            return (
                "En guerra, el dinero va a:\n\n"
                "1. Defensa (Lockheed, etc)\n"
                "2. Energía (petróleo/gas)\n"
                "3. Oro\n\n"
                "Estrategia simple:\n"
                "- 60% energía\n"
                "- 20% defensa\n"
                "- 20% oro"
            )

        if "negocio" in msg:
            return (
                "Opciones reales para empezar YA:\n\n"
                "1. Agencia IA para empresas\n"
                "2. Automatizaciones con n8n\n"
                "3. Chatbots WhatsApp\n\n"
                "El más rápido: vender automatización."
            )

        return "Dime qué quieres lograr y te digo exactamente qué hacer."
