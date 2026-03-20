from pymilvus import connections, Collection

connections.connect(
    alias="default",
    host="localhost",
    port="19530"
)

class VectorMemory:

    def __init__(self):
        self.collection = Collection("jarvis_memory")

    def store(self, vector, text):

        data = [
            [vector],
            [text]
        ]

        self.collection.insert(data)

    def search(self, vector):

        results = self.collection.search(
            [vector],
            "embedding",
            param={"metric_type":"L2"},
            limit=5
        )

        return results
