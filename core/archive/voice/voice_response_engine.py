from core.voice_orchestration_engine import VoiceOrchestrationEngine


class VoiceResponseEngine:
    """
    Mantiene compatibilidad con main.py actual:
    voice_response_engine = VoiceResponseEngine()
    voice_response_engine.speak(reply)
    """

    def __init__(self) -> None:
        self.engine = VoiceOrchestrationEngine()

    def speak(self, text: str) -> str:
        return self.engine.speak(text)