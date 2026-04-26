import whisper

class VoiceRecognitionEngine:

    def __init__(self):

        self.model=whisper.load_model("base")

    def transcribe(self,file_path):

        result=self.model.transcribe(file_path)

        return{
        "text":result["text"]
        }
