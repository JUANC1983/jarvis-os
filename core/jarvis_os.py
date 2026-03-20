from core.conversation_engine import ConversationEngine
from core.voice_response_engine import VoiceResponseEngine


class JarvisOS:

    def __init__(self):

        self.conversation = ConversationEngine()
        self.voice = VoiceResponseEngine()

    def chat(self, message, domain="general"):

        reply = self.conversation.reply(message, domain)

        return {
            "reply": reply
        }

    def chat_voice(self, message):

        reply = self.conversation.reply(message)

        audio = self.voice.speak(reply)

        return {
            "reply": reply,
            "audio": audio
        }