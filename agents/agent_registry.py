class Agent:
    def __init__(self, name, display_name, category, description, capabilities=None):
        self.name = name
        self.display_name = display_name
        self.category = category
        self.description = description
        self.capabilities = capabilities or []

    def respond(self, message: str) -> str:
        return f"{self.display_name} is processing: {message}"

    def metadata(self):
        return {
            "name": self.name,
            "display_name": self.display_name,
            "category": self.category,
            "description": self.description,
            "capabilities": self.capabilities,
        }


class AgentRegistry:
    def __init__(self):
        self.agents = {}

    def register(self, agent: Agent):
        self.agents[agent.name] = agent

    def get(self, name: str):
        return self.agents.get(name)

    def list_agents(self):
        return list(self.agents.keys())

    def list_agent_details(self):
        return [agent.metadata() for agent in self.agents.values()]
