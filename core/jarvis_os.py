from __future__ import annotations

from typing import Dict

from core.product_brain import ProductBrain


class JarvisOS:
    def __init__(self) -> None:
        self.boot_errors = []
        self.brain = None

        try:
            self.brain = ProductBrain()
        except Exception as e:
            self.boot_errors.append(f"ProductBrain: {e}")
            self.brain = None
            print(f"[WARNING] JarvisOS brain init failed: {e}")

    def health(self) -> dict:
        return {
            "boot_errors": self.boot_errors,
            "brain": self.brain.health() if self.brain else {
                "available": False,
                "error": "brain not available",
            },
        }

    def chat(self, message: str) -> Dict:
        if not self.brain:
            return {
                "type": "general",
                "summary": "JARVIS is online, but the brain is not available.",
                "details": {},
                "action": "Check server health.",
                "confidence": 0.1,
                "source": "fallback",
            }
        return self.brain.respond(message)

    def trader(self, symbol_or_prompt: str) -> Dict:
        if not self.brain:
            return {
                "symbol": str(symbol_or_prompt).upper(),
                "setup_score": None,
                "traffic_light": "red",
                "technicals": {"price": None},
                "trade_plan": {
                    "action": "NO TRADE",
                    "entry_zone": [],
                    "stop_loss": "-",
                    "target_1": "-",
                    "target_2": "-",
                    "risk_reward_estimate": "-",
                },
                "narrative": ["Brain unavailable."],
                "summary": "Brain unavailable.",
                "source": "fallback",
            }
        return self.brain.trader(symbol_or_prompt)
