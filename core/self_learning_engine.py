class SelfLearningEngine:

    def __init__(self):

        self.experiences=[]

    def record(self,event,result):

        self.experiences.append({
            "event":event,
            "result":result
        })

    def learn(self):

        insights=[]

        for e in self.experiences:

            insights.append(
                f"Learned from {e['event']}"
            )

        return insights
