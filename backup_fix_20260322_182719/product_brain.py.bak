from __future__ import annotations
from typing import Dict, Any, Optional

try:
    from core.agent_orchestrator_pro import AgentOrchestratorPro
except:
    AgentOrchestratorPro = None


class ProductBrain:

    def __init__(self) -> None:
        self.orchestrator = None

        if AgentOrchestratorPro:
            try:
                self.orchestrator = AgentOrchestratorPro()
            except Exception as e:
                print(f"[ERROR] Orchestrator failed: {e}")

        self.symbol_aliases = {
            "tesla": "TSLA",
            "apple": "AAPL",
            "amazon": "AMZN",
            "google": "GOOGL",
            "microsoft": "MSFT",
            "nvidia": "NVDA",
            "meta": "META"
        }

    # -----------------------------
    # CORE ENTRY
    # -----------------------------
    def respond(self, message: str) -> Dict[str, Any]:
        return self.chat(message)

    # -----------------------------
    # CHAT (UNIFIED INTELLIGENCE)
    # -----------------------------
    def chat(self, message: str) -> Dict[str, Any]:

        if not self.orchestrator:
            return self._fallback("Sistema disponible pero sin inteligencia central.")

        domain = self._detect_domain(message)

        result = self.orchestrator.execute(message, domain)

        return {
            "type": "intelligence",
            "summary": self._natural_response(result),
            "details": result,
            "confidence": 0.95,
            "source": "orchestrator"
        }

    # -----------------------------
    # TRADER (SPECIALIZED FLOW)
    # -----------------------------
    def trader(self, symbol_or_prompt: str) -> Dict[str, Any]:

        if not self.orchestrator:
            return self._fallback("Trader no disponible.")

        symbol = self._resolve_symbol(symbol_or_prompt)

        result = self.orchestrator.execute_trader(symbol)

        return self._normalize_trader(result)

    # -----------------------------
    # RECOMMENDATIONS
    # -----------------------------
    def recommendations(self):

        symbols = ["NVDA","MSFT","META","GOOGL","AMZN","AAPL","TSLA"]

        items = []

        for s in symbols:
            try:
                r = self.trader(s)

                if r.get("setup_score"):
                    items.append({
                        "symbol": r["symbol"],
                        "setup_score": r["setup_score"],
                        "traffic_light": r["traffic_light"],
                        "price_now": r["technicals"]["price"],
                        "friendly_recommendation": r.get("summary",""),
                        "action": r["trade_plan"]["action"]
                    })
            except:
                continue

        items = sorted(items, key=lambda x: x["setup_score"], reverse=True)

        return {"items": items[:5]}

    # -----------------------------
    # DOMAIN DETECTION
    # -----------------------------
    def _detect_domain(self, message: str) -> str:

        msg = message.lower()

        if any(x in msg for x in ["accion","stock","trade","tesla","apple","nvda"]):
            return "finance"

        if any(x in msg for x in ["salud","dolor","medico","fitness"]):
            return "medical"

        if any(x in msg for x in ["legal","contrato","ley"]):
            return "legal"

        return "general"

    # -----------------------------
    # SYMBOL RESOLUTION
    # -----------------------------
    def _resolve_symbol(self, text: str) -> str:

        t = text.lower().strip()

        if t in self.symbol_aliases:
            return self.symbol_aliases[t]

        return text.upper()

    # -----------------------------
    # NATURAL RESPONSE
    # -----------------------------
    def _natural_response(self, result: Dict) -> str:

        if not result:
            return "No tengo suficiente información."

        res = result.get("result")

        if isinstance(res, dict):
            if "summary" in res:
                return res["summary"]

            if "consensus" in res:
                return res["consensus"]

        return result.get("summary", "Procesado.")

    # -----------------------------
    # NORMALIZE TRADER
    # -----------------------------
    def _normalize_trader(self, r: Dict):

        return {
            "symbol": r.get("symbol"),
            "setup_score": r.get("setup_score"),
            "traffic_light": r.get("traffic_light"),
            "technicals": r.get("technicals"),
            "trade_plan": r.get("trade_plan"),
            "narrative": r.get("narrative"),
            "summary": r.get("summary"),
            "source": r.get("source")
        }

    def _fallback(self, msg):
        return {
            "type": "fallback",
            "summary": msg,
            "confidence": 0.3
        }
