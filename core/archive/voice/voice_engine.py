import os
from elevenlabs.client import ElevenLabs
from elevenlabs import play
from dotenv import load_dotenv

load_dotenv()

class ElevenVoiceEngine:

    def __init__(self):

        self.api_key=os.getenv("ELEVENLABS_API_KEY")

        self.client=ElevenLabs(api_key=self.api_key)

        self.voice="Rachel"


    def speak(self,text):

        audio=self.client.generate(

            text=text,
            voice=self.voice,
            model="eleven_multilingual_v2"

        )

        play(audio)

        return{
        "status":"spoken",
        "text":text
        }
