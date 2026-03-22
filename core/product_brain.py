import yfinance as yf
import numpy as np

class ProductBrain:

    def chat(self, message: str) -> dict:
        message = message.lower()

        if "best" in message or "mejor" in message:
            return self._best_opportunity()

        return self._chat_fallback()

    def _best_opportunity(self):
        symbols = ["ASML", "NVDA", "AAPL", "MSFT"]

        candidates = []

        for symbol in symbols:
            data = yf.Ticker(symbol).history(period="1mo")

            if data.empty or len(data) < 10:
                continue

            close = data["Close"]

            # --- FACTORES ---
            trend = close.iloc[-1] > close.mean()
            momentum = (close.iloc[-1] - close.iloc[-5]) / close.iloc[-5]
            volatility = np.std(close[-10:])
            pullback = close.iloc[-1] < close.max() * 0.97

            score = 50

            if trend:
                score += 15
            if momentum > 0:
                score += 15
            if pullback:
                score += 10
            if volatility < 5:
                score += 5

            candidates.append({
                "symbol": symbol,
                "price": round(close.iloc[-1], 2),
                "score": score,
                "momentum": round(momentum * 100, 2),
                "trend": trend,
                "pullback": pullback
            })

        candidates = sorted(candidates, key=lambda x: x["score"], reverse=True)

        best = candidates[0]

        # --- DECISIÓN REAL ---
        if best["score"] >= 75:
            action = "GO"
            context = "Setup fuerte con tendencia y momentum."
        elif best["score"] >= 60:
            action = "WAIT"
            context = "Setup aceptable. Esperar confirmación."
        else:
            action = "AVOID"
            context = "No hay ventaja clara."

        return {
            "type": "trade_idea",
            "summary": f"{best['symbol']} | Score {best['score']} | {action}",
            "details": best,
            "action": action,
            "context": context,
            "confidence": 0.85,
            "source": "multi_factor_engine"
        }

    def _chat_fallback(self):
        return {
            "type": "chat",
            "summary": "Pregunta por oportunidades, análisis de acciones o mercado.",
            "details": {},
            "action": "",
            "confidence": 0.5
        }

    def trader(self, symbol: str):
        data = yf.Ticker(symbol).history(period="1mo")

        if data.empty:
            return {"error": "No data"}

        close = data["Close"]

        price = float(close.iloc[-1])
        support = float(close.min())
        resistance = float(close.max())

        return {
            "symbol": symbol,
            "price": round(price, 2),
            "entry_zone": f"{round(price*0.98,2)} - {round(price*1.01,2)}",
            "stop_loss": round(support, 2),
            "target": round(resistance, 2),
            "action": "WAIT"
        }

    def recommendations(self):
        return self._best_opportunity()
