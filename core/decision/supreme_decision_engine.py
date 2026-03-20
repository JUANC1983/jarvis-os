class SupremeDecisionEngine:

    def __init__(self):

        self.agents = {}

    def register(self, name, agent):

        self.agents[name] = agent

    def deliberate(self, question):

        responses = {}

        for name, agent in self.agents.items():

            try:

                if hasattr(agent, "analyze"):
                    responses[name] = agent.analyze(question)

                elif hasattr(agent, "evaluate"):
                    responses[name] = agent.evaluate(question)

                else:
                    responses[name] = "No compatible method"

            except Exception as e:
                responses[name] = str(e)

        return responses


    def synthesize(self, responses):

        summary = []

        for agent, response in responses.items():

            summary.append(f"{agent}: {str(response)[:200]}")

        return {

            "agent_consultations": responses,

            "summary": summary,

            "decision_framework":

            [
                "1. Identify consensus between agents",
                "2. Identify conflicting recommendations",
                "3. Prioritize capital protection",
                "4. Recommend next action"
            ]
        }
