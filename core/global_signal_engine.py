import requests
import yfinance as yf

class GlobalSignalEngine:

    def __init__(self):
        self.watch_assets = [
            "CL=F",
            "GC=F",
            "SI=F",
            "HG=F",
            "BTC-USD",
            "ETH-USD",
            "DX-Y.NYB",
            "^VIX",
            "^TNX",
            "SPY"
        ]

    def market_snapshot(self):

        data = []

        for symbol in self.watch_assets:

            try:

                ticker = yf.Ticker(symbol)
                hist = ticker.history(period="5d")

                if hist.empty:
                    continue

                price = float(hist["Close"].iloc[-1])
                prev = float(hist["Close"].iloc[-2])

                change = ((price - prev) / prev) * 100

                data.append({
                    "symbol": symbol,
                    "price": round(price,2),
                    "change_pct": round(change,2)
                })

            except:
                pass

        return data


    def detect_global_signals(self):

        snapshot = self.market_snapshot()

        signals = []

        for asset in snapshot:

            if asset["symbol"] == "^VIX" and asset["change_pct"] > 10:
                signals.append("Volatility shock detected")

            if asset["symbol"] == "CL=F" and asset["change_pct"] > 5:
                signals.append("Oil supply risk rising")

            if asset["symbol"] == "GC=F" and asset["change_pct"] > 3:
                signals.append("Flight to safety into gold")

            if asset["symbol"] == "^TNX" and asset["change_pct"] > 3:
                signals.append("Rates shock risk")

        return {
            "snapshot": snapshot,
            "signals": signals
        }
