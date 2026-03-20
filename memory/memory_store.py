import json
from datetime import datetime
from pathlib import Path


MEMORY_FILE = Path("memory/jarvis_memory.json")


class MemoryStore:

    def __init__(self):

        if not MEMORY_FILE.exists():
            MEMORY_FILE.parent.mkdir(exist_ok=True)
            MEMORY_FILE.write_text(json.dumps([]))

    def load(self):

        with open(MEMORY_FILE, "r") as f:
            return json.load(f)

    def save(self, memories):

        with open(MEMORY_FILE, "w") as f:
            json.dump(memories, f, indent=2)

    def add_memory(self, memory_type, content, user="default"):

        memories = self.load()

        memory = {
            "type": memory_type,
            "user": user,
            "content": content,
            "timestamp": datetime.utcnow().isoformat()
        }

        memories.append(memory)

        self.save(memories)

        return memory

    def get_memories(self):

        return self.load()