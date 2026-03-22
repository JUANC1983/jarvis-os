import yfinance as yf
import numpy as np

class ProductBrain:

    def chat(self, message: str) -> dict:
        try:
            if "best" in message.lower():
                return self._best_opportunity()
        except:
            pass

        return self._chat_fallback()

    def _best_opportunity(self):
        symbols = ["ASML", "NVDA", "AAPL", "MSFT"]
        candidates = []

        for symbol in symbols:
            try:
                data = yf.Ticker(symbol).history(period="1mo")

                if data.empty:
                    continue

                close = data["Close"]

                trend = close.iloc[-1] > close.mean()
                momentum = (close.iloc[-1] - close.iloc[-5]) / close.iloc[-5]
                volatility = np.std(close[-10:])
                pullback = close.iloc[-1] < close.max() * 0.97

                score = 50
                if trend: score += 15
                if momentum > 0: score += 15
                if pullback: score += 10
                if volatility < 5: score += 5

                candidates.append({
                    "symbol": symbol,
                    "price": round(float(close.iloc[-1]), 2),
                    "score": int(score)
                })

            except:
                continue

        if not candidates:
            return self._chat_fallback()

        best = sorted(candidates, key=lambda x: x["score"], reverse=True)[0]

        action = "GO" if best["score"] >= 75 else "WAIT"

        return {
            "type": "trade_idea",
            "summary": f"{best['symbol']} | Score {best['score']}",
            "details": best,
            "action": action,
            "confidence": 0.8
        }

    def _chat_fallback(self):
        return {
            "type": "chat",
            "summary": "Sistema estable. Pregunta por oportunidades específicas.",
            "confidence": 0.5
        }

    def trader(self, symbol: str):
        try:
            data = yf.Ticker(symbol).history(period="1d")
            price = float(data["Close"].iloc[-1])

            return {
                "symbol": symbol,
                "price": round(price, 2),
                "action": "WAIT"
            }
        except:
            return {"error": "market unavailable"}

    def recommendations(self):
        return self._best_opportunity()
