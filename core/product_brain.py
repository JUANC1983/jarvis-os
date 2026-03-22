from __future__ import annotations

from typing import Dict, Any, List

from core.agent_orchestrator_pro import AgentOrchestratorPro


class ProductBrain:

    def __init__(self) -> None:
        self.orchestrator = AgentOrchestratorPro()

    def health(self) -> dict:
        return {
            "available": True,
            "orchestrator_available": True
        }

    # =========================
    # CHAT (INTELIGENTE)
    # =========================
    def chat(self, message: str) -> Dict:
        try:
            result = self.orchestrator.execute(message, domain="general")

            return {
                "type": "chat",
                "summary": result.get("summary"),
                "details": result.get("result"),
                "confidence": 0.9,
                "source": "orchestrator"
            }

        except Exception as e:
            return {
                "type": "error",
                "summary": str(e),
                "confidence": 0.2
            }

    # =========================
    # TRADER (YA FUNCIONA BIEN)
    # =========================
    def trader(self, symbol: str) -> Dict:
        return self.orchestrator.execute_trader(symbol)

    # =========================
    # ?? NUEVO SISTEMA REAL DE RECOMMENDATIONS
    # =========================
    def recommendations(self) -> Dict:

        try:
            result = self.orchestrator.execute(
                "Find the best stock opportunities right now with strong momentum, institutional flow, and asymmetric risk/reward.",
                domain="finance"
            )

            data = result.get("result")

            # Si el engine devuelve lista de oportunidades
            if isinstance(data, list):
                return {"items": data}

            # Si devuelve dict estructurado
            if isinstance(data, dict):

                # Caso: ya viene con items
                if "items" in data:
                    return {"items": data["items"]}

                # Caso: respuesta simple ? convertir
                return {
                    "items": [
                        {
                            "symbol": "AUTO",
                            "price": None,
                            "setup_score": 70,
                            "traffic_light": "green",
                            "summary": str(data)
                        }
                    ]
                }

            return {"items": []}

        except Exception as e:
            return {
                "items": [
                    {
                        "symbol": "ERROR",
                        "summary": str(e),
                        "traffic_light": "red"
                    }
                ]
            }
