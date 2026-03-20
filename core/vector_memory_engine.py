from sentence_transformers import SentenceTransformer
import faiss
import numpy as np

class JarvisVectorMemory:

    def __init__(self):

        self.model = SentenceTransformer("all-MiniLM-L6-v2")

        self.index = faiss.IndexFlatL2(384)

        self.memory = []

    def store(self, text):

        vector = self.model.encode([text])[0]

        self.index.add(np.array([vector]).astype("float32"))

        self.memory.append(text)

        return {"stored":text}

    def search(self, query, k=5):

        vector = self.model.encode([query])[0]

        D,I = self.index.search(np.array([vector]).astype("float32"),k)

        results = []

        for idx in I[0]:

            if idx < len(self.memory):

                results.append(self.memory[idx])

        return results
