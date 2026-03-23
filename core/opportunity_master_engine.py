from typing import Dict, List
import yfinance as yf
import numpy as np

class OpportunityMasterEngine:

    def __init__(self):
        self.symbols = [
            "NVDA","AMD","MSFT","META","GOOGL","AMZN",
            "TSLA","PLTR","COIN","NFLX","AAPL",
            "SMCI","ARM","MRVL","AVGO","TSM",
            "XLE","USO","GLD","SLV"
        ]

    def analyze_symbol(self, symbol: str) -> Dict:
        try:
            symbol = symbol.upper()

            data = yf.Ticker(symbol).history(period="1mo")

            if data.empty:
                return self._fallback(symbol)

            close = data["Close"]

            price = float(close.iloc[-1])
            momentum = (close.iloc[-1] - close.iloc[-5]) / close.iloc[-5]
            trend = close.iloc[-1] > close.mean()

            score = 50
            if trend:
                score += 20
            if momentum > 0:
                score += 20

            traffic = "green" if score >= 80 else "yellow" if score >= 60 else "red"

            return {
                "symbol": symbol,
                "price": round(price,2),
                "price_now": round(price,2),
                "setup_score": score,
                "traffic_light": traffic,
                "trade_plan": {
                    "action": "GO" if score >= 80 else "WAIT"
                },
                "summary": f"{symbol} score {score}",
                "source": "stable_pro"
            }

        except:
            return self._fallback(symbol)

    def get_top_opportunities(self, limit: int = 8) -> List[Dict]:

        results = []

        for s in self.symbols:
            r = self.analyze_symbol(s)
            if r["price"] is not None:
                results.append(r)

        results = sorted(results, key=lambda x: x["setup_score"], reverse=True)

        return results[:limit]

    def _fallback(self, symbol: str) -> Dict:
        return {
            "symbol": symbol,
            "price": None,
            "setup_score": 0,
            "traffic_light": "red",
            "summary": "No data",
            "source": "fallback"
        }
