import os
import json
from typing import List, Dict, Any

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


class RealAgentCouncil:
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY", "")
        self.client = OpenAI(api_key=api_key) if api_key else None

        self.agent_profiles = {
            "strategist": {
                "persona": "Long-term strategic thinker. Focus on leverage points, second-order effects, positioning, and compounding.",
            },
            "risk_analyst": {
                "persona": "Downside protection specialist. Focus on failure modes, hidden risk, correlation, fragility, and tail events.",
            },
            "trader": {
                "persona": "Execution-oriented market operator. Focus on timing, setups, invalidation, discipline, and trade structure.",
            },
            "tax_strategist_colombia_global": {
                "persona": "Tax strategist focused on Colombia and international structuring. Focus on legal optimization, compliance, and documentation.",
            },
            "life_strategist": {
                "persona": "Life architect. Focus on wealth, family, health, energy, legacy, and time allocation.",
            },
            "chief_medical_advisor": {
                "persona": "Elite preventive medical advisor. Focus on prevention, escalation, biomarkers, performance, and longevity.",
            },
            "research_librarian": {
                "persona": "Research synthesizer. Focus on gathering and structuring high-value evidence and frameworks.",
            },
            "opportunity_radar": {
                "persona": "Asymmetric opportunity hunter. Focus on timing, underpriced shifts, catalysts, and windows of advantage.",
            },
            "macro_regime_analyst": {
                "persona": "Macro regime analyst. Focus on rates, inflation, liquidity, energy, and global regime transitions.",
            },
            "family_office_advisor": {
                "persona": "Family office advisor. Focus on multi-asset wealth protection, tax sensitivity, liquidity, and intergenerational strategy.",
            },
        }

    def _select_agents(self, domain: str) -> List[str]:
        domain = (domain or "general").lower()

        if domain in {"finance", "investment", "macro", "wealth"}:
            return [
                "strategist",
                "risk_analyst",
                "trader",
                "opportunity_radar",
                "macro_regime_analyst",
                "tax_strategist_colombia_global",
                "family_office_advisor",
            ]

        if domain in {"health", "medical", "longevity"}:
            return [
                "chief_medical_advisor",
                "risk_analyst",
                "life_strategist",
                "research_librarian",
            ]

        if domain in {"life", "family", "personal"}:
            return [
                "life_strategist",
                "strategist",
                "risk_analyst",
                "family_office_advisor",
            ]

        return [
            "strategist",
            "risk_analyst",
            "research_librarian",
            "life_strategist",
        ]

    def _fallback(self, topic: str, domain: str, agents: List[str]) -> Dict[str, Any]:
        opinions = []
        for agent in agents:
            persona = self.agent_profiles.get(agent, {}).get("persona", "General elite intelligence.")
            opinions.append(
                {
                    "agent": agent,
                    "opinion": f"{agent} reviewed '{topic}' under domain '{domain}'. Lens: {persona}",
                }
            )

        return {
            "topic": topic,
            "domain": domain,
            "agents_consulted": agents,
            "opinions": opinions,
            "consensus": "Council consensus: pursue upside only with strong downside protection, documentation, and strategic alignment.",
            "dissent": [
                "Execution quality matters more than idea quality if timing is poor.",
                "A valid thesis can still be a bad position if sizing, structure, or context are wrong.",
            ],
            "recommended_next_steps": [
                "Clarify objective, horizon, and downside tolerance.",
                "Validate assumptions with real data before acting.",
                "Align the decision with wealth, family, health, and time priorities.",
            ],
        }

    def deliberate(self, topic: str, domain: str = "general", owner_name: str = "Juan Camilo Montenegro") -> Dict[str, Any]:
        agents = self._select_agents(domain)

        if not self.client:
            return self._fallback(topic, domain, agents)

        prompt = f"""
You are the deliberation engine for JARVIS, the personal strategic intelligence system of {owner_name}.

Topic:
{topic}

Domain:
{domain}

Council agents:
{agents}

Agent personas:
{json.dumps(self.agent_profiles, ensure_ascii=False)}

Return valid JSON with this exact structure:
{{
  "topic": "...",
  "domain": "...",
  "agents_consulted": ["..."],
  "opinions": [
    {{"agent": "...", "opinion": "..."}}
  ],
  "consensus": "...",
  "dissent": ["..."],
  "recommended_next_steps": ["..."]
}}

Rules:
- Make the reasoning premium, executive, and practical.
- Reflect disagreement where useful.
- Optimize for wealth, health, family, reputation, and long-term strategic advantage.
- Do not be generic.
"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4.1-mini",
                temperature=0.2,
                messages=[
                    {"role": "system", "content": "You are an elite multi-agent strategic council."},
                    {"role": "user", "content": prompt},
                ],
            )

            content = response.choices[0].message.content
            data = json.loads(content)
            return data

        except Exception:
            return self._fallback(topic, domain, agents)
