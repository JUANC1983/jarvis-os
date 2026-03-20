from core.super_memory import SuperMemory


class DecisionEngine:

    def __init__(self):

        self.memory = SuperMemory()

    def evaluate(self,decision):

        score = self.estimate_quality(decision)

        self.memory.remember({
            "decision":decision,
            "score":score
        })

        return {
            "decision":decision,
            "score":score,
            "recommendation":self.generate_recommendation(score)
        }

    def estimate_quality(self,decision):

        length = len(decision)

        if length > 80:
            return 0.8

        return 0.6

    def generate_recommendation(self,score):

        if score > 0.75:

            return "High confidence decision structure."

        return "Decision needs more context and validation."
