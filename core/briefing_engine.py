from datetime import datetime

from core.identity import JarvisIdentity


class IntelligenceBriefingEngine:
    def __init__(self):
        self.identity = JarvisIdentity()

    def build(self, focus: str = "general", memory_results=None, opportunity_results=None) -> dict:
        owner = self.identity.owner.name
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

        sections = {
            "owner": owner,
            "timestamp": now,
            "focus": focus,
            "macro_watch": [
                "Monitor geopolitical tension and commodity sensitivity.",
                "Watch inflation, rates, and USD pressure for second-order effects.",
            ],
            "risks": [
                "Protect downside before chasing upside.",
                "Validate legal, tax, and concentration risk before execution.",
            ],
            "opportunities": opportunity_results or [
                "No live radar signal attached yet.",
            ],
            "memory_context": memory_results or [],
            "personal_priorities": [
                "Protect high-value decision time.",
                "Balance wealth building with health, family, and reputation.",
            ],
        }

        summary = (
            f"JARVIS Intelligence Briefing for {owner}. "
            f"Focus: {focus}. "
            "Primary emphasis: protect downside, identify asymmetric opportunities, and maintain alignment across wealth, family, health, and strategic priorities."
        )

        return {
            "owner": owner,
            "title": "JARVIS Intelligence Briefing",
            "sections": sections,
            "summary": summary,
        }
