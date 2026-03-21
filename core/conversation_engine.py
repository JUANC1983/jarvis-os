import os
from openai import OpenAI

class ConversationEngine:

    def __init__(self):
        api_key = os.environ.get("OPENAI_API_KEY")

        if not api_key:
            raise Exception("OPENAI_API_KEY not found in environment")

        self.client = OpenAI(api_key=api_key)

    def chat(self, message: str):
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are Jarvis, elite AI assistant."},
                {"role": "user", "content": message}
            ]
        )
        return response.choices[0].message.content
