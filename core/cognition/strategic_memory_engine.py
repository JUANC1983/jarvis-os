import json
from datetime import datetime
from pathlib import Path

class StrategicMemoryEngine:

    def __init__(self):

        self.memory_path = Path("data/memory")
        self.memory_path.mkdir(parents=True, exist_ok=True)

        self.memory_file = self.memory_path / "strategic_memory.json"

        if not self.memory_file.exists():
            self.memory_file.write_text(json.dumps([]))

    def record_event(self, category, description, data=None):

        memory = json.loads(self.memory_file.read_text())

        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "category": category,
            "description": description,
            "data": data
        }

        memory.append(entry)

        self.memory_file.write_text(json.dumps(memory, indent=2))

    def search(self, keyword):

        memory = json.loads(self.memory_file.read_text())

        results = []

        for m in memory:
            if keyword.lower() in json.dumps(m).lower():
                results.append(m)

        return results
