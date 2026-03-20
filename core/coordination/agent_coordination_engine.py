class AgentCoordinationEngine:

    def __init__(self):
        self.agents = {}

    def register_agent(self, name, agent):

        self.agents[name] = agent

    def consult_agents(self, query):

        responses = {}

        for name, agent in self.agents.items():

            try:
                if hasattr(agent, "analyze"):
                    responses[name] = agent.analyze(query)

            except Exception as e:
                responses[name] = str(e)

        return responses
