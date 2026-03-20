from __future__ import annotations

from typing import Dict, Any, List

from core.premium_agent_registry import PremiumAgentRegistry


class AgentOptimizationEngine:
    def __init__(self) -> None:
        self.registry = PremiumAgentRegistry()

    def optimize_for_domain(self, domain: str) -> Dict[str, Any]:
        agents = self.registry.agents_for_domain(domain)

        top = agents[:5]
        return {
            "domain": domain,
            "recommended_agents": top,
            "primary_agent": top[0]["agent"] if top else "executive_council",
            "secondary_agents": [a["agent"] for a in top[1:]],
            "summary": f"Optimized premium agent stack prepared for domain={domain}.",
        }

    def premium_council_layout(self, domain: str) -> Dict[str, Any]:
        optimized = self.optimize_for_domain(domain)
        agents = optimized["recommended_agents"]

        return {
            "domain": domain,
            "chair_agent": optimized["primary_agent"],
            "critical_challenger": "risk_analyst" if any(a["agent"] == "risk_analyst" for a in agents) else None,
            "execution_agent": "trader_alpha" if any(a["agent"] == "trader_alpha" for a in agents) else "daily_ops",
            "support_agents": [a["agent"] for a in agents[1:]],
            "governance_rules": [
                "No recommendation without downside logic.",
                "No opportunity without invalidation.",
                "No execution without position logic.",
                "Final synthesis belongs to executive_council when domain is ambiguous.",
            ],
        }
