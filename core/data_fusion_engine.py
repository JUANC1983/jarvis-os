import yfinance as yf
import pandas as pd


class DataFusionEngine:
    def market_snapshot(self):
        symbols = [
            "CL=F",
            "GC=F",
            "^GSPC",
            "^VIX",
            "DX-Y.NYB",
        ]

        data = {}

        for s in symbols:
            try:
                ticker = yf.Ticker(s)
                hist = ticker.history(period="5d")
                data[s] = {
                    "price": float(hist["Close"].iloc[-1]),
                    "change": float(hist["Close"].pct_change().iloc[-1]),
                }
            except Exception:
                data[s] = {"error": "data unavailable"}

        return data

    def macro_summary(self):
        data = self.market_snapshot()
        summary = []

        try:
            if data["CL=F"].get("price", 0) > 80:
                summary.append("Oil elevated")
        except Exception:
            pass

        try:
            if data["^VIX"].get("price", 0) > 20:
                summary.append("Volatility elevated")
        except Exception:
            pass

        return {
            "market_data": data,
            "macro_signals": summary,
        }
