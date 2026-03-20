import os
from typing import Any, Dict

from openai import OpenAI


class StrategicReasoningEngine:
    """
    Motor de análisis profundo para cuando sí se necesite.
    No reemplaza conversación humana; la complementa.
    """

    def __init__(self) -> None:
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def analyze(self, topic: str) -> Dict[str, Any]:
        clean_topic = (topic or "").strip()
        if not clean_topic:
            return {"error": "topic is required"}

        prompt = f"""
You are a world-class strategic intelligence analyst.

Analyze the topic deeply and return a structured JSON object with:
- situation
- key_forces
- scenarios
- risks
- opportunities
- recommended_actions

Topic:
{clean_topic}
"""

        response = self.client.chat.completions.create(
            model="gpt-4o",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "Return only valid JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=1200,
        )

        return {"analysis": response.choices[0].message.content}