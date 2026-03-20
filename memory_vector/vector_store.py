import os
import faiss
import json
import numpy as np
from sentence_transformers import SentenceTransformer


class VectorMemoryStore:
    def __init__(self):
        self.model = SentenceTransformer("all-MiniLM-L6-v2")
        self.dimension = 384
        self.index = faiss.IndexFlatL2(self.dimension)
        self.memory = []
        self.memory_file = "memory_vector/vector_memory.json"

        os.makedirs("memory_vector", exist_ok=True)

        if os.path.exists(self.memory_file):
            with open(self.memory_file, "r", encoding="utf-8") as f:
                self.memory = json.load(f)

            if len(self.memory) > 0:
                embeddings = [m["embedding"] for m in self.memory]
                embeddings = np.array(embeddings).astype("float32")
                self.index.add(embeddings)

    def save(self):
        with open(self.memory_file, "w", encoding="utf-8") as f:
            json.dump(self.memory, f, ensure_ascii=False, indent=2)

    def add_memory(self, text, metadata=None):
        embedding = self.model.encode(text)
        embedding = embedding.astype("float32")
        self.index.add(np.array([embedding]))

        entry = {
            "text": text,
            "embedding": embedding.tolist(),
            "metadata": metadata or {}
        }

        self.memory.append(entry)
        self.save()

    def search(self, query, k=5):
        if len(self.memory) == 0:
            return []

        query_vector = self.model.encode(query)
        query_vector = np.array([query_vector]).astype("float32")

        distances, indices = self.index.search(query_vector, min(k, len(self.memory)))

        results = []
        for idx in indices[0]:
            if idx < len(self.memory):
                results.append(self.memory[idx])

        return results
