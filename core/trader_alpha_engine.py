import yfinance as yf
import numpy as np

class TraderAlphaEngine:

    def run(self, symbol: str):

        try:
            ticker = yf.Ticker(symbol)
            data = ticker.history(period="1mo")

            if data.empty:
                return {"error": "no data"}

            close = data["Close"]

            price = float(close.iloc[-1])

            trend = price > close.mean()
            momentum = (price - close.iloc[-5]) / close.iloc[-5]

            score = 50
            if trend: score += 20
            if momentum > 0: score += 20

            action = "BUY" if score >= 80 else "WAIT"

            return {
                "symbol": symbol,
                "price": round(price,2),
                "setup_score": score,
                "traffic_light": "green" if score >= 80 else "yellow",
                "action": action,
                "summary": f"{symbol} score {score} con precio real {round(price,2)}"
            }

        except Exception as e:
            return {"error": str(e)}
