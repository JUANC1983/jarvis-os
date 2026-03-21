import os
from typing import Optional

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


class ConversationEngine:
    def __init__(self) -> None:
        self.available = False
        self.client: Optional[object] = None
        self.error: Optional[str] = None
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

        api_key = os.getenv("OPENAI_API_KEY", "").strip()

        if not api_key:
            self.error = "OPENAI_API_KEY not found in environment"
            print(f"[WARNING] ConversationEngine disabled: {self.error}")
            return

        if OpenAI is None:
            self.error = "openai package not installed"
            print(f"[WARNING] ConversationEngine disabled: {self.error}")
            return

        try:
            self.client = OpenAI(api_key=api_key)
            self.available = True
            print("[OK] ConversationEngine initialized")
        except Exception as e:
            self.error = str(e)
            self.available = False
            self.client = None
            print(f"[WARNING] ConversationEngine init failed: {self.error}")

    def health(self) -> dict:
        return {
            "available": self.available,
            "error": self.error,
            "model": self.model,
        }

    def chat(self, message: str) -> str:
        if not self.available or self.client is None:
            return "OpenAI not configured."

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are Jarvis, an elite AI assistant."},
                    {"role": "user", "content": message},
                ],
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            return f"OpenAI request failed: {e}"

    def reply(self, message: str, domain: str = "general") -> str:
        prompt = f"[DOMAIN: {domain}] {message}"
        return self.chat(prompt)
