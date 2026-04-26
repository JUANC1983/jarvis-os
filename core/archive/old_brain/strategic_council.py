from typing import List

from agents.default_agents import registry
from core.models import AgentExecutionResult


class StrategicCouncil:
    def run(self, primary_agent: str, message: str) -> List[AgentExecutionResult]:
        council_agents = self._select_council(primary_agent, message)
        results: List[AgentExecutionResult] = []

        for agent_name in council_agents:
            agent = registry.get(agent_name)
            if not agent:
                continue

            results.append(
                AgentExecutionResult(
                    agent_name=agent.name,
                    display_name=agent.display_name,
                    category=agent.category,
                    response=agent.respond(message),
                )
            )

        return results

    def _select_council(self, primary_agent: str, message: str) -> List[str]:
        text = message.lower()

        if primary_agent in {
            "strategic_investment",
            "trader",
            "portfolio_manager",
            "tax_strategist_colombia_global",
        }:
            return [
                "strategic_investment",
                "trader",
                "risk_analyst",
                "opportunity_radar",
                "crisis_simulator",
                "portfolio_manager",
                "tax_strategist_colombia_global",
                "cognitive_bias_detector",
            ]

        if primary_agent in {
            "chief_medical_advisor",
            "family_doctor",
            "fitness_coach",
            "nutritionist",
        }:
            return [
                "chief_medical_advisor",
                "family_doctor",
                "fitness_coach",
                "nutritionist",
                "sleep_optimizer",
                "longevity_strategist",
                "supplement_advisor",
                "risk_analyst",
            ]

        if primary_agent in {"golf_caddy_ai", "swing_analyzer"}:
            return [
                "golf_caddy_ai",
                "swing_analyzer",
                "chief_medical_advisor",
                "risk_analyst",
            ]

        if primary_agent in {"life_strategist", "chief_of_staff", "strategist"}:
            return [
                "life_strategist",
                "chief_of_staff",
                "strategist",
                "decision_simulator",
                "cognitive_bias_detector",
                "intelligence_briefing",
                "reputation_guardian",
            ]

        if "family" in text or "wife" in text or "children" in text or "hijos" in text or "esposa" in text:
            return [
                "life_strategist",
                "chief_of_staff",
                "reputation_guardian",
                "decision_simulator",
                "cognitive_bias_detector",
            ]

        return [
            primary_agent,
            "strategist",
            "chief_of_staff",
            "risk_analyst",
        ]
