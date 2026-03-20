from memory_vector.vector_store import VectorMemoryStore


class VectorMemoryEngine:
    def __init__(self):
        self.store = VectorMemoryStore()

    def remember(self, message: str):
        self.store.add_memory(message)

    def recall(self, query: str, k: int = 5):
        return self.store.search(query, k=k)
