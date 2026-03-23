from typing import Dict, List
import yfinance as yf

class OpportunityMasterEngine:

    def resolve_symbol(self, s: str) -> str:
        return str(s).upper().replace(".", "-")

    def analyze_symbol(self, symbol: str) -> Dict:
        try:
            symbol = self.resolve_symbol(symbol)

            data = yf.Ticker(symbol).history(period="1mo")

            if data.empty:
                return self._fallback(symbol)

            price = float(data["Close"].iloc[-1])

            return {
                "symbol": symbol,
                "price": round(price, 2),
                "price_now": round(price, 2),
                "setup_score": 60,
                "traffic_light": "yellow",
                "trade_plan": {
                    "action": "WAIT",
                    "entry_zone": [],
                    "stop_loss": "-",
                    "target_1": "-",
                    "target_2": "-",
                    "risk_reward_estimate": "-"
                },
                "insight_lines": ["Datos básicos cargados correctamente"],
                "summary": f"{symbol} precio {round(price,2)}",
                "friendly_recommendation": "Esperar confirmación",
                "source": "safe_engine"
            }

        except:
            return self._fallback(symbol)

    def get_top_opportunities(self, limit: int = 5) -> List[Dict]:
        symbols = ["NVDA","AMD","MSFT","META","GOOGL"]

        results = []

        for s in symbols:
            results.append(self.analyze_symbol(s))

        return results

    def _fallback(self, symbol: str) -> Dict:
        return {
            "symbol": symbol,
            "price": None,
            "setup_score": 0,
            "traffic_light": "red",
            "summary": "No data",
            "source": "fallback"
        }
