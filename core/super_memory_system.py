import os
import json
from datetime import datetime


class SuperMemorySystem:
    def __init__(self):
        self.path = "data/super_memory.json"
        os.makedirs("data", exist_ok=True)

        if not os.path.exists(self.path):
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump([], f, ensure_ascii=False)

    def store(self, category: str, text: str):
        memories = self.load()

        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "category": category,
            "text": text,
        }

        memories.append(entry)

        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(memories, f, ensure_ascii=False, indent=2)

        return entry

    def load(self):
        with open(self.path, "r", encoding="utf-8") as f:
            return json.load(f)

    def search(self, keyword: str):
        memories = self.load()
        results = [m for m in memories if keyword.lower() in m["text"].lower()]
        return results[:10]

    def categories(self):
        memories = self.load()
        cats = set([m["category"] for m in memories])
        return list(cats)
