from datetime import datetime
import json
from pathlib import Path

class DecisionAuditEngine:

    def __init__(self):

        self.path = Path("data/audit")
        self.path.mkdir(parents=True, exist_ok=True)

        self.file = self.path / "decisions.json"

        if not self.file.exists():
            self.file.write_text(json.dumps([]))

    def log_decision(self, decision, reasoning):

        history = json.loads(self.file.read_text())

        entry = {
            "time": datetime.utcnow().isoformat(),
            "decision": decision,
            "reasoning": reasoning
        }

        history.append(entry)

        self.file.write_text(json.dumps(history, indent=2))

    def get_history(self):

        return json.loads(self.file.read_text())
