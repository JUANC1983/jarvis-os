from typing import List
import random

class AgentCouncil:

    def __init__(self):

        self.council_agents = [
            "strategist",
            "risk_analyst",
            "trader",
            "tax_strategist_colombia_global",
            "family_office_advisor",
            "life_strategist",
            "chief_medical_advisor",
            "research_librarian",
            "opportunity_radar",
            "macro_regime_analyst"
        ]

    def deliberate(self, topic:str):

        opinions = []

        for agent in self.council_agents:

            opinions.append({
                "agent":agent,
                "opinion":self.generate_opinion(agent,topic)
            })

        consensus = self.generate_consensus(opinions)

        return {
            "topic":topic,
            "agents_consulted":len(self.council_agents),
            "opinions":opinions,
            "consensus":consensus
        }

    def generate_opinion(self,agent,topic):

        return f"{agent} evaluated topic '{topic}' and provided strategic insight."

    def generate_consensus(self,opinions):

        return "Council consensus: combine opportunity awareness with disciplined risk management."
