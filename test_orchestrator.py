from core.agent_orchestrator_pro import AgentOrchestratorPro

orch = AgentOrchestratorPro()

print("\n=== LOADING ENGINES ===\n")

for agent in orch.engine_map.keys():
    engine = orch._load_engine(agent)
    if engine:
        print(f"[OK] {agent} -> {engine.__class__.__name__}")
    else:
        print(f"[FAIL] {agent}")

print("\n=== BOOT EVENTS ===\n")
for e in orch.boot_events:
    print(e)
