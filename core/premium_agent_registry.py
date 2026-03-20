from __future__ import annotations

from typing import Dict, Any, List


class PremiumAgentRegistry:
    def __init__(self) -> None:
        self.agents = {
            "executive_council": {
                "role": "Final strategic synthesis",
                "domains": ["general", "macro", "business", "decision"],
                "reputation": 0.95,
                "style": "executive_strategic",
            },
            "market_intelligence": {
                "role": "Market and macro structure analysis",
                "domains": ["macro", "finance", "trading", "investing"],
                "reputation": 0.92,
                "style": "institutional_market",
            },
            "opportunity_radar": {
                "role": "Opportunity discovery and asymmetric setups",
                "domains": ["macro", "investing", "trading"],
                "reputation": 0.90,
                "style": "opportunistic_precise",
            },
            "risk_analyst": {
                "role": "Risk, downside and invalidation",
                "domains": ["macro", "finance", "trading", "legal"],
                "reputation": 0.96,
                "style": "conservative_precise",
            },
            "trader_alpha": {
                "role": "Trade execution logic, entries, exits, timing",
                "domains": ["trading", "finance", "macro"],
                "reputation": 0.91,
                "style": "tactical_structured",
            },
            "wealth_optimizer": {
                "role": "Capital allocation and wealth optimization",
                "domains": ["finance", "wealth", "investing"],
                "reputation": 0.88,
                "style": "wealth_architect",
            },
            "legal_compliance": {
                "role": "Legal and compliance logic",
                "domains": ["legal", "tax", "contracts"],
                "reputation": 0.86,
                "style": "precise_legal",
            },
            "medical_supreme": {
                "role": "Medical support, triage, labs",
                "domains": ["medical", "health"],
                "reputation": 0.82,
                "style": "clinical_structured",
            },
            "fitness_performance": {
                "role": "Fitness, recovery and performance",
                "domains": ["fitness", "health", "performance"],
                "reputation": 0.84,
                "style": "performance_coach",
            },
            "daily_ops": {
                "role": "Execution rhythm and operational structure",
                "domains": ["general", "productivity", "operations"],
                "reputation": 0.80,
                "style": "operator",
            },
            "knowledge_engine": {
                "role": "General knowledge support",
                "domains": ["general"],
                "reputation": 0.78,
                "style": "reference",
            },
        }

    def list_agents(self) -> Dict[str, Any]:
        return self.agents

    def agents_for_domain(self, domain: str) -> List[Dict[str, Any]]:
        matches = []
        for name, meta in self.agents.items():
            if domain in meta["domains"] or "general" in meta["domains"]:
                matches.append({"agent": name, **meta})

        matches.sort(key=lambda x: x["reputation"], reverse=True)
        return matches
