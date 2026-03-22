import yfinance as yf
import numpy as np


class ProductBrain:

    def health(self):
        return {"status": "ok", "brain": "connected"}

    # =========================
    # CHAT
    # =========================
    def respond(self, message: str) -> dict:
        msg = message.lower()

        # Routing inteligente
        if any(x in msg for x in ["stock", "trade", "market", "ticker"]):
            return self._best_opportunity()

        if any(x in msg for x in ["best", "opportunity", "money"]):
            return self._best_opportunity()

        return self._chat_natural(message)

    def _chat_natural(self, message: str):
        return {
            "type": "chat",
            "reply": f"Entendido. Estoy procesando: '{message}'. Pregunta por acciones, mercados o oportunidades.",
            "summary": "Conversación general",
            "confidence": 0.7
        }

    # =========================
    # BEST OPPORTUNITY
    # =========================
    def _best_opportunity(self):

        symbols = ["NVDA", "MSFT", "AAPL", "AMZN", "META"]
        results = []

        for symbol in symbols:
            try:
                data = yf.Ticker(symbol).history(period="1mo")

                if data.empty:
                    continue

                close = data["Close"]

                trend = close.iloc[-1] > close.mean()
                momentum = (close.iloc[-1] - close.iloc[-5]) / close.iloc[-5]
                pullback = close.iloc[-1] < close.max() * 0.97

                score = 50
                if trend: score += 15
                if momentum > 0: score += 15
                if pullback: score += 10

                results.append({
                    "symbol": symbol,
                    "price": round(float(close.iloc[-1]), 2),
                    "setup_score": int(score),
                    "traffic_light": "green" if score >= 75 else "yellow" if score >= 60 else "red",
                    "summary": f"{symbol} mostrando {'fuerza' if trend else 'debilidad'} con score {score}"
                })

            except:
                continue

        if not results:
            return self._chat_natural("market unavailable")

        best = sorted(results, key=lambda x: x["setup_score"], reverse=True)[0]

        return {
            "type": "trade_idea",
            "summary": f"{best['symbol']} | Score {best['setup_score']}",
            "details": best,
            "action": "BUY" if best["setup_score"] >= 75 else "WAIT",
            "confidence": 0.85
        }

    # =========================
    # TRADER
    # =========================
    def trader(self, symbol: str):

        try:
            data = yf.Ticker(symbol).history(period="1mo")

            if data.empty:
                return {"error": "No data"}

            close = data["Close"]
            price = float(close.iloc[-1])

            trend = close.iloc[-1] > close.mean()
            momentum = (close.iloc[-1] - close.iloc[-5]) / close.iloc[-5]

            score = 50
            if trend: score += 20
            if momentum > 0: score += 15

            return {
                "symbol": symbol.upper(),
                "price_now": round(price, 2),
                "setup_score": score,
                "traffic_light": "green" if score >= 75 else "yellow" if score >= 60 else "red",
                "trade_plan": {
                    "action": "BUY" if score >= 75 else "WAIT",
                    "entry_zone": [round(price * 0.98, 2), round(price * 1.01, 2)],
                    "stop_loss": round(price * 0.95, 2),
                    "target_1": round(price * 1.05, 2),
                    "target_2": round(price * 1.1, 2),
                    "risk_reward_estimate": "2:1"
                },
                "insight_lines": [
                    f"Tendencia {'alcista' if trend else 'débil'}",
                    f"Momentum {'positivo' if momentum > 0 else 'negativo'}"
                ],
                "summary": f"{symbol} análisis completo"
            }

        except Exception as e:
            return {"error": str(e)}

    # =========================
    # RECOMMENDATIONS
    # =========================
    def recommendations(self):

        symbols = ["NVDA", "MSFT", "AAPL", "META"]
        items = []

        for s in symbols:
            r = self.trader(s)
            if "error" not in r:
                items.append({
                    "symbol": s,
                    "setup_score": r["setup_score"],
                    "traffic_light": r["traffic_light"],
                    "friendly_recommendation": r["summary"]
                })

        return {"items": items}