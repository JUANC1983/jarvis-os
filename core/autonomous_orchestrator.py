from core.autonomous_decision_engine import AutonomousDecisionEngine
from core.task_executor import TaskExecutor

class AutonomousOrchestrator:

    def __init__(self):

        self.decision_engine = AutonomousDecisionEngine()
        self.executor = TaskExecutor()

    def run(self, task: dict):

        agent = self.decision_engine.decide(task)

        result = self.executor.execute(agent, task)

        return {
            "agent": agent,
            "task": task,
            "result": result
        }
