from typing import Dict, Any
from core.agent_orchestrator_pro import AgentOrchestratorPro


class ProductBrain:

    def __init__(self):
        self.orchestrator = AgentOrchestratorPro()

    # =========================
    # HEALTH
    # =========================
    def health(self):
        return {
            "status": "ok",
            "orchestrator": self.orchestrator.health()
        }

    # =========================
    # CHAT
    # =========================
    def chat(self, message: str) -> dict:
        try:
            msg = message.lower()

            # =========================
            # MARKET INTENT
            # =========================
            if any(x in msg for x in ["stock", "acción", "apple", "tesla", "nvda", "msft", "trade", "invertir"]):
                return self._handle_market_chat(message)

            # =========================
            # GENERAL INTELLIGENCE
            # =========================
            result = self.orchestrator.execute(message, domain="general")

            return {
                "type": "chat",
                "summary": result.get("summary", "Procesado"),
                "details": result,
                "action": "processed",
                "confidence": 0.9
            }

        except Exception as e:
            return {
                "type": "error",
                "summary": f"Error en chat: {str(e)}",
                "confidence": 0.2
            }

    # =========================
    # MARKET CHAT
    # =========================
    def _handle_market_chat(self, message: str):

        # usa trader directamente
        trader = self.trader(message)

        return {
            "type": "trade_analysis",
            "summary": trader.get("summary", "Análisis generado"),
            "details": trader,
            "action": trader.get("trade_plan", {}).get("action", "WAIT"),
            "confidence": 0.9
        }

    # =========================
    # TRADER (CRÍTICO)
    # =========================
    def trader(self, symbol_or_prompt: str) -> Dict[str, Any]:

        try:
            result = self.orchestrator.execute_trader(symbol_or_prompt)

            # enriquecer salida
            summary = result.get("summary", "")
            action = result.get("trade_plan", {}).get("action", "WAIT")

            return {
                "symbol": result.get("symbol"),
                "setup_score": result.get("setup_score"),
                "traffic_light": result.get("traffic_light"),
                "price_now": result.get("technicals", {}).get("price"),
                "trade_plan": result.get("trade_plan"),
                "narrative": result.get("narrative"),
                "summary": summary if summary else f"{result.get('symbol')} análisis generado",
                "action": action,
                "source": result.get("source", "orchestrator")
            }

        except Exception as e:
            return {
                "error": str(e),
                "source": "trader_fallback"
            }

    # =========================
    # RECOMMENDATIONS
    # =========================
    def recommendations(self):

        symbols = ["NVDA", "MSFT", "AMZN", "META", "AAPL"]

        results = []

        for s in symbols:
            try:
                r = self.trader(s)
                if "error" not in r:
                    results.append(r)
            except:
                pass

        results = sorted(results, key=lambda x: x.get("setup_score") or 0, reverse=True)

        return {
            "top": results[:3],
            "all": results
        }
