import yfinance as yf
import pandas as pd


class GlobalDataEngine:

    def market_snapshot(self,symbols):

        data = {}

        for s in symbols:

            try:

                ticker = yf.Ticker(s)
                hist = ticker.history(period="5d")

                data[s] = {
                    "price": float(hist["Close"].iloc[-1]),
                    "change_5d": float(hist["Close"].pct_change().iloc[-1])
                }

            except:
                data[s] = {"error":"data unavailable"}

        return data


    def macro_watch(self):

        symbols = [
            "CL=F",
            "GC=F",
            "^GSPC",
            "^VIX",
            "DX-Y.NYB"
        ]

        return self.market_snapshot(symbols)
