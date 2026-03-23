
def analyze_symbol(self, raw_symbol: str) -> Dict:
    from typing import Dict   
    import yfinance as yf
    import numpy as np
    import time

    symbol = raw_symbol.upper()

    for attempt in range(2):  # 🔁 retry simple
        try:
            ticker = yf.Ticker(symbol)

            df = ticker.history(period="3mo")

            # 🔴 SI FALLA → retry
            if df is None or df.empty:
                time.sleep(1)
                continue

            close = df["Close"]

            if len(close) < 20:
                return self._fallback(symbol)

            price = float(close.iloc[-1])

            ma20 = close.rolling(20).mean().iloc[-1]
            momentum = (close.iloc[-1] / close.iloc[-5]) - 1

            score = 50

            if price > ma20:
                score += 15
            else:
                score -= 10

            if momentum > 0.05:
                score += 20
            elif momentum > 0:
                score += 10
            elif momentum < -0.05:
                score -= 20
            else:
                score -= 10

            volatility = np.std(close[-10:])

            if volatility < 5:
                score += 5
            else:
                score -= 5

            score = max(0, min(100, int(score)))

            if score >= 80:
                light = "green"
                action = "GO"
            elif score >= 60:
                light = "yellow"
                action = "WAIT"
            else:
                light = "red"
                action = "AVOID"

            return {
                "symbol": symbol,
                "price": price,
                "price_now": price,
                "setup_score": score,
                "traffic_light": light,
                "trade_plan": {
                    "action": action
                },
                "summary": f"{symbol} score {score}",
                "source": "opportunity_master_resilient"
            }

        except Exception:
            time.sleep(1)
            continue

    # 🔥 NUNCA rompe el endpoint
    return self._fallback(symbol)

def _fallback(self, symbol: str) -> Dict:
    return {
        "symbol": symbol,
        "price": None,
        "price_now": None,
        "setup_score": 50,
        "traffic_light": "yellow",
        "trade_plan": {
            "action": "WAIT"
        },
        "summary": f"{symbol} sin datos suficientes",
        "source": "fallback_safe"
    }