import yfinance as yf

class AutoTradingEngine:

    def signal(self,symbol):

        data = yf.Ticker(symbol).history(period="6mo")

        ma50 = data["Close"].rolling(50).mean().iloc[-1]

        ma200 = data["Close"].rolling(200).mean().iloc[-1]

        price = data["Close"].iloc[-1]

        if ma50 > ma200:

            return {
                "symbol":symbol,
                "signal":"bullish",
                "action":"consider long exposure"
            }

        return {
            "symbol":symbol,
            "signal":"neutral",
            "action":"wait"
        }
