import yfinance as yf

class ProductBrain:

    def __init__(self):
        pass

    def chat(self, message: str) -> dict:
        message = message.lower()

        if "best" in message or "mejor" in message:
            return self._best_opportunity()

        return self._chat_fallback(message)

    def _best_opportunity(self):
        symbols = ["ASML", "NVDA", "AAPL", "MSFT"]

        results = []

        for symbol in symbols:
            data = yf.Ticker(symbol).history(period="5d")

            if data.empty:
                continue

            price = float(data["Close"].iloc[-1])
            prev = float(data["Close"].iloc[-2])

            change = (price - prev) / prev

            score = 50 + int(change * 500)

            results.append({
                "symbol": symbol,
                "price": round(price, 2),
                "score": score,
                "change": round(change * 100, 2)
            })

        results = sorted(results, key=lambda x: x["score"], reverse=True)

        best = results[0]

        action = "GO" if best["score"] > 70 else "WAIT"

        return {
            "type": "trade_idea",
            "summary": f"Best opportunity: {best['symbol']}",
            "details": best,
            "action": action,
            "confidence": 0.8,
            "source": "market_analysis"
        }

    def _chat_fallback(self, message: str) -> dict:
        return {
            "type": "chat",
            "summary": "Haz una pregunta específica sobre mercado, acciones o inversión.",
            "details": {},
            "action": "",
            "confidence": 0.5,
            "source": "fallback"
        }

    def trader(self, symbol: str):
        data = yf.Ticker(symbol).history(period="1d")

        if data.empty:
            return {"error": "No data"}

        price = float(data["Close"].iloc[-1])

        return {
            "symbol": symbol,
            "price": round(price, 2),
            "action": "WAIT"
        }

    def recommendations(self):
        return self._best_opportunity()
