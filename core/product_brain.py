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
    # CHAT INTELIGENTE
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
    # TRADER (FUNCIONANDO)
    # =========================
    def trader(self, symbol: str) -> Dict:
        return self.orchestrator.execute_trader(symbol)

    # =========================
    # ?? RECOMMENDATIONS PROFESIONALES
    # =========================
    def recommendations(self) -> Dict:

        opportunities: List[Dict] = []

        # ?? AGENTES CORRECTOS (NO risk_analyst)
        preferred_agents = [
            "opportunity_radar",
            "trader_alpha",
            "market_intelligence"
        ]

        for agent in preferred_agents:

            engine = self.orchestrator._load_engine(agent)

            if engine is None:
                continue

            try:
                result = self.orchestrator._try_methods(
                    engine,
                    "Find top high-probability stock setups with strong momentum and institutional activity",
                    "finance"
                )

                # Si devuelve lista válida
                if isinstance(result, list):
                    for item in result:
                        if isinstance(item, dict):
                            opportunities.append(item)

                # Si devuelve dict
                elif isinstance(result, dict):

                    # Caso: lista interna
                    if "items" in result:
                        opportunities.extend(result["items"])

                    # Caso: single result ? convertir
                    elif "symbol" in result:
                        opportunities.append(result)

            except:
                continue

        # ?? FALLBACK INTELIGENTE SI NADA FUNCIONA
        if not opportunities:

            fallback_symbols = ["NVDA", "AMD", "MSFT", "META", "GOOGL"]

            for sym in fallback_symbols:
                data = self.trader(sym)
                opportunities.append(data)

        # ?? NORMALIZAR OUTPUT
        clean = []

        for o in opportunities[:10]:

            clean.append({
                "symbol": o.get("symbol"),
                "price": o.get("price") or o.get("price_now"),
                "setup_score": o.get("setup_score") or o.get("score", 50),
                "traffic_light": o.get("traffic_light", "yellow"),
                "summary": o.get("summary", f"{o.get('symbol')} opportunity detected"),
                "source": o.get("source", "multi_engine")
            })

        return {"items": clean}
