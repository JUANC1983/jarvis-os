from __future__ import annotations

from typing import Dict, Any

from core.global_opportunity_radar_pro import GlobalOpportunityRadarPro
from core.strategic_foresight_engine import StrategicForesightEngine
from core.agent_orchestrator_pro import AgentOrchestratorPro


class ExecutiveBriefingEngine:
    def __init__(self) -> None:
        self.radar = GlobalOpportunityRadarPro()
        self.foresight = StrategicForesightEngine()
        self.orchestrator = AgentOrchestratorPro()

    def build(self, topic: str = "global macro", context: str = "") -> Dict[str, Any]:
        radar = self.radar.scan(topic=topic, context=context)
        foresight = self.foresight.simulate(topic=topic, context=context)
        routing = self.orchestrator.route("macro")

        return {
            "topic": topic,
            "executive_summary": [
                radar.get("executive_summary", ""),
                foresight.get("executive_summary", ""),
            ],
            "high_priority_setups": radar.get("high_priority_setups", [])[:5],
            "recommended_posture": foresight.get("recommended_posture", ""),
            "second_order_effects": foresight.get("second_order_effects", [])[:5],
            "premium_agent_stack": routing,
        }
