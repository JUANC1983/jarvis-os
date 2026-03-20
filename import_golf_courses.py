from core.golf_ai_agent import GolfAIAgent

agent = GolfAIAgent()

print("Importando campos de Colombia...")

result = agent.import_courses_json("data/golf/colombia_courses.json")

print(result)

print("Estado base de datos:")

print(agent.database_stats())
