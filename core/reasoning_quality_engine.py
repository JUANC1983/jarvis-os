class ReasoningQualityEngine:
    def evaluate(self, prompt: str, response: str):
        return {
            "clarity_score": 0.82,
            "strategic_depth_score": 0.85,
            "actionability_score": 0.83,
            "notes": [
                "Increase factual grounding when external data is available.",
                "Preserve concise executive summary plus deeper strategic layer.",
            ],
        }
