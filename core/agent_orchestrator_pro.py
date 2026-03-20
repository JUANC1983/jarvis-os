from __future__ import annotations

from typing import Any, Dict, List


class AgentOrchestratorPro:
    def __init__(self) -> None:
        self.agent_registry = {
            "finance": ["market_intelligence", "opportunity_radar", "wealth_optimizer", "risk_analyst", "trader_alpha"],
            "medical": ["medical_supreme", "fitness_performance"],
            "legal": ["legal_compliance"],
            "general": ["executive_council", "daily_ops", "knowledge_engine"],
            "macro": ["market_intelligence", "risk_analyst", "executive_council", "trader_alpha"],
        }

        self.agent_reputation = {
            "market_intelligence": 0.90,
            "opportunity_radar": 0.88,
            "wealth_optimizer": 0.86,
            "risk_analyst": 0.92,
            "trader_alpha": 0.89,
            "medical_supreme": 0.78,
            "fitness_performance": 0.82,
            "legal_compliance": 0.84,
            "executive_council": 0.91,
            "daily_ops": 0.80,
            "knowledge_engine": 0.79,
        }

    def route(self, domain: str) -> Dict[str, Any]:
        selected = self.agent_registry.get(domain, self.agent_registry["general"])
        weighted = [
            {"agent": agent, "reputation": self.agent_reputation.get(agent, 0.75)}
            for agent in selected
        ]
        weighted = sorted(weighted, key=lambda x: x["reputation"], reverse=True)

        return {
            "domain": domain,
            "selected_agents": weighted,
            "primary_agent": weighted[0]["agent"] if weighted else "executive_council",
        }

    def deliberate(self, query: str, domain: str = "general") -> Dict[str, Any]:
        routed = self.route(domain)
        return {
            "query": query,
            "domain": domain,
            "primary_agent": routed["primary_agent"],
            "selected_agents": routed["selected_agents"],
            "summary": f"AgentOrchestratorPro routed this request to {len(routed['selected_agents'])} specialized agents.",
        }
