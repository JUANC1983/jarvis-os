from typing import Optional

from core.conversation_engine import ConversationEngine


class JarvisOS:
    def __init__(self) -> None:
        self.boot_errors = []
        self.conversation: Optional[ConversationEngine] = None

        try:
            self.conversation = ConversationEngine()
        except Exception as e:
            self.boot_errors.append(f"ConversationEngine: {e}")
            self.conversation = None
            print(f"[WARNING] JarvisOS conversation init failed: {e}")

    def health(self) -> dict:
        return {
            "boot_errors": self.boot_errors,
            "conversation": self.conversation.health() if self.conversation else {
                "available": False,
                "error": "conversation engine not available",
            },
        }

    def process(self, message: str) -> str:
        if not self.conversation:
            return "Jarvis conversation engine is not available."
        return self.conversation.chat(message)

    def chat(self, message: str) -> str:
        return self.process(message)
