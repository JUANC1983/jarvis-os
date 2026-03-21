from core.conversation_engine import ConversationEngine

class JarvisOS:

    def __init__(self):
        try:
            self.conversation = ConversationEngine()
        except Exception as e:
            print(f"[WARNING] Conversation engine failed: {e}")
            self.conversation = None

    def chat(self, message: str):
        if not self.conversation:
            return "Jarvis no disponible."

        return self.conversation.chat(message)
