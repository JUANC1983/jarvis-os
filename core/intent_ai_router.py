import os
import json

from dotenv import load_dotenv
load_dotenv()

from openai import OpenAI

from core.models import AgentSelection


class IntentAIRouter:

    def __init__(self):

        api_key = os.getenv("OPENAI_API_KEY")

        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not found")

        self.client = OpenAI(api_key=api_key)

        self.agent_catalog = [
            "chief_of_staff",
            "strategist",
            "risk_analyst",
            "life_strategist",
            "cognitive_bias_detector",
            "decision_simulator",
            "reputation_guardian",
            "intelligence_briefing",
            "trader",
            "strategic_investment",
            "portfolio_manager",
            "tax_strategist_colombia_global",
            "accounting_operations",
            "lawyer",
            "chief_medical_advisor",
            "family_doctor",
            "biometrics_analyzer",
            "fitness_coach",
            "nutritionist",
            "sleep_optimizer",
            "longevity_strategist",
            "supplement_advisor",
            "style_advisor",
            "travel_concierge",
            "golf_caddy_ai",
            "swing_analyzer",
            "research_librarian",
            "image_analyzer",
            "video_analyzer",
            "opportunity_radar",
            "crisis_simulator"
        ]

    def classify_intent(self, message: str) -> AgentSelection:

        prompt = f"""
You are the routing intelligence for JARVIS.

Determine:
- primary_agent
- supporting_agents
- risk_escalated

Agents available:
{self.agent_catalog}

Return JSON ONLY:
{{
 "primary_agent": "...",
 "supporting_agents": [],
 "risk_escalated": false,
 "reasons": []
}}

User message:
{message}
"""

        response = self.client.chat.completions.create(
            model="gpt-4.1-mini",
            temperature=0,
            messages=[
                {"role": "system", "content": "You are an AI routing system for a high-end personal strategic intelligence system."},
                {"role": "user", "content": prompt}
            ]
        )

        content = response.choices[0].message.content

        try:
            data = json.loads(content)
        except Exception:
            data = {
                "primary_agent": "strategist",
                "supporting_agents": [],
                "risk_escalated": False,
                "reasons": ["fallback routing"]
            }

        return AgentSelection(
            primary_agent=data["primary_agent"],
            supporting_agents=data["supporting_agents"],
            risk_escalated=data["risk_escalated"],
            reasons=data["reasons"]
        )
