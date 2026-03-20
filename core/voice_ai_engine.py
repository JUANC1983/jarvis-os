import os
from pathlib import Path
from typing import Optional

import requests
import whisper

from core.voice_orchestration_engine import VoiceOrchestrationEngine


class VoiceAIEngine:
    """
    Compatible con api.voice_routes existente.
    - Descarga audio desde Twilio/WhatsApp
    - Transcribe con Whisper local
    - Sintetiza usando el mismo motor de voz unificado
    """

    def __init__(self) -> None:
        model_name = os.getenv("WHISPER_MODEL", "base").strip()
        self.model = whisper.load_model(model_name)
        self.voice = VoiceOrchestrationEngine()
        self.input_dir = Path("data/voice/incoming")
        self.input_dir.mkdir(parents=True, exist_ok=True)

    def download_audio(self, url: str, path: Optional[str] = None) -> str:
        if not url:
            raise ValueError("media url is required")

        if path:
            output_path = Path(path)
        else:
            output_path = self.input_dir / "incoming_audio.ogg"

        output_path.parent.mkdir(parents=True, exist_ok=True)

        response = requests.get(url, timeout=90)
        response.raise_for_status()

        with output_path.open("wb") as f:
            f.write(response.content)

        return str(output_path).replace("\\", "/")

    def transcribe(self, audio_path: str) -> str:
        if not audio_path:
            raise ValueError("audio_path is required")

        result = self.model.transcribe(audio_path)
        text = (result.get("text") or "").strip()
        return text

    def synthesize(self, text: str, output: Optional[str] = None) -> str:
        filename = None
        if output:
            filename = Path(output).name
        return self.voice.speak(text=text, filename=filename)