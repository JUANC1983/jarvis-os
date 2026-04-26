from core.voice_engine import ElevenVoiceEngine
from core.voice_recognition_engine import VoiceRecognitionEngine


class VoiceJarvisBridge:

    def __init__(self):

        self.speaker=ElevenVoiceEngine()

        self.listener=VoiceRecognitionEngine()


    def respond(self,text):

        return self.speaker.speak(text)


    def listen(self,file_path):

        return self.listener.transcribe(file_path)
