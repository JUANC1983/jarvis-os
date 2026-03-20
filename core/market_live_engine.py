import yfinance as yf


class MarketLiveEngine:

    def snapshot(self):

        symbols = ["^IXIC", "SPY", "QQQ"]

        data = {}

        for s in symbols:

            t = yf.Ticker(s)
            info = t.history(period="1d")

            price = float(info["Close"].iloc[-1])

            data[s] = price

        return data