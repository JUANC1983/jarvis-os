from __future__ import annotations

from typing import Optional

from core.agent_orchestrator_pro import AgentOrchestratorPro
from core.conversation_engine import ConversationEngine


class JarvisOS:
    def __init__(self) -> None:
        self.boot_errors = []
        self.orchestrator: Optional[AgentOrchestratorPro] = None
        self.conversation: Optional[ConversationEngine] = None

        try:
            self.orchestrator = AgentOrchestratorPro()
        except Exception as e:
            self.boot_errors.append(f"AgentOrchestratorPro: {e}")
            self.orchestrator = None
            print(f"[WARNING] JarvisOS orchestrator init failed: {e}")

        try:
            self.conversation = ConversationEngine()
        except Exception as e:
            self.boot_errors.append(f"ConversationEngine: {e}")
            self.conversation = None
            print(f"[WARNING] JarvisOS conversation init failed: {e}")

    def health(self) -> dict:
        return {
            "boot_errors": self.boot_errors,
            "orchestrator": self.orchestrator.health() if self.orchestrator else {
                "available": False,
                "error": "orchestrator not available",
            },
            "conversation": self.conversation.health() if self.conversation else {
                "available": False,
                "error": "conversation engine not available",
            },
        }

    def _infer_domain(self, message: str) -> str:
        msg = (message or "").lower()

        if any(k in msg for k in ["stock", "trade", "trading", "ticker", "market", "aapl", "nvda", "tesla", "msft", "amazon", "google"]):
            return "finance"

        if any(k in msg for k in ["macro", "war", "iran", "china", "oil", "middle east", "regime"]):
            return "macro"

        if any(k in msg for k in ["legal", "contract", "compliance", "regulation"]):
            return "legal"

        if any(k in msg for k in ["health", "medical", "fitness", "performance"]):
            return "medical"

        return "general"

    def process(self, message: str) -> str:
        domain = self._infer_domain(message)

        if self.orchestrator:
            routed = self.orchestrator.execute(message, domain)
            result = routed.get("result")

            if isinstance(result, str) and result.strip():
                return result

            if isinstance(result, dict):
                for key in ["summary", "message", "response", "thesis"]:
                    value = result.get(key)
                    if isinstance(value, str) and value.strip():
                        return value

        if self.conversation:
            return self.conversation.chat(message)

        return "Jarvis is online, but no active response engine is available."

    def chat(self, message: str) -> str:
        return self.process(message)

    def trader(self, symbol_or_prompt: str) -> dict:
        if self.orchestrator:
            return self.orchestrator.execute_trader(symbol_or_prompt)

        return {
            "symbol": str(symbol_or_prompt).upper(),
            "setup_score": None,
            "traffic_light": "red",
            "technicals": {"price": None},
            "trade_plan": {
                "action": "-",
                "entry_zone": [],
                "stop_loss": "-",
                "target_1": "-",
                "target_2": "-",
                "risk_reward_estimate": "-",
            },
            "narrative": ["Orchestrator unavailable."],
            "summary": "Orchestrator unavailable.",
            "source": "fallback",
        }
