import yfinance as yf
import numpy as np

class PremiumTraderEngine:

    def analyze(self, symbol: str):

        try:
            ticker = yf.Ticker(symbol)
            data = ticker.history(period="3mo")

            if data.empty:
                return {"error": "no data"}

            close = data["Close"]

            price = float(close.iloc[-1])

            # ===== SIGNALS =====
            sma20 = close[-20:].mean()
            sma50 = close[-50:].mean()
            momentum = (price - close.iloc[-5]) / close.iloc[-5]
            volatility = np.std(close[-20:])
            drawdown = (price - close.max()) / close.max()

            # ===== SCORING =====
            score = 0

            if price > sma20: score += 15
            if sma20 > sma50: score += 15
            if momentum > 0.03: score += 20
            if volatility < 5: score += 10
            if drawdown > -0.1: score += 10

            # Normalize
            score = min(100, max(0, score))

            # ===== ACTION =====
            if score >= 80:
                action = "STRONG BUY"
                light = "green"
            elif score >= 60:
                action = "BUY"
                light = "blue"
            elif score >= 40:
                action = "WAIT"
                light = "yellow"
            else:
                action = "AVOID"
                light = "red"

            return {
                "symbol": symbol,
                "price": round(price,2),
                "setup_score": score,
                "traffic_light": light,
                "action": action,
                "summary": f"{symbol} score {score} | momentum {round(momentum,3)} | trend {'bullish' if price>sma50 else 'bearish'}"
            }

        except Exception as e:
            return {"error": str(e)}
