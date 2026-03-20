from memory.memory_store import MemoryStore


store = MemoryStore()


def extract_memory(text):

    text_lower = text.lower()

    memories = []

    if "prefer" in text_lower or "i like" in text_lower:

        memories.append(
            store.add_memory("preference", text)
        )

    if "meeting" in text_lower or "reunión" in text_lower:

        memories.append(
            store.add_memory("event", text)
        )

    if "goal" in text_lower or "objetivo" in text_lower:

        memories.append(
            store.add_memory("goal", text)
        )

    return memories