import os
from openai import OpenAI

class ConversationEngine:

    def __init__(self):
        self.client = None
        self.available = False

        try:
            api_key = os.environ.get("OPENAI_API_KEY")

            if not api_key:
                raise Exception("Missing OPENAI_API_KEY")

            self.client = OpenAI(api_key=api_key)
            self.available = True

        except Exception as e:
            print(f"[WARNING] OpenAI not available: {e}")

    def chat(self, message: str):
        if not self.available:
            return "?? OpenAI no configurado todavía."

        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are Jarvis."},
                {"role": "user", "content": message}
            ]
        )

        return response.choices[0].message.content
