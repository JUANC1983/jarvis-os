import os
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

import requests


class VoiceOrchestrationEngine:
    """
    Motor unificado de voz para JARVIS.
    - Usa ELEVENLABS_VOICE_ID del .env
    - Guarda archivos en data/voice
    - Permite detener reproducción del lado frontend
    - Mantiene compatibilidad con el resto de la arquitectura
    """

    def __init__(self) -> None:
        self.api_key = os.getenv("ELEVENLABS_API_KEY", "").strip()
        self.voice_id = os.getenv("ELEVENLABS_VOICE_ID", "").strip()
        self.model_id = os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2").strip()
        self.output_dir = Path("data/voice")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def is_configured(self) -> bool:
        return bool(self.api_key and self.voice_id)

    def config_status(self) -> Dict[str, Any]:
        return {
            "configured": self.is_configured(),
            "voice_id": self.voice_id if self.voice_id else None,
            "model_id": self.model_id,
            "output_dir": str(self.output_dir),
        }

    def _build_payload(
        self,
        text: str,
        stability: float = 0.38,
        similarity_boost: float = 0.82,
        style: float = 0.18,
        use_speaker_boost: bool = True,
    ) -> Dict[str, Any]:
        return {
            "text": text,
            "model_id": self.model_id,
            "voice_settings": {
                "stability": stability,
                "similarity_boost": similarity_boost,
                "style": style,
                "use_speaker_boost": use_speaker_boost,
            },
        }

    def speak(
        self,
        text: str,
        filename: Optional[str] = None,
        stability: float = 0.38,
        similarity_boost: float = 0.82,
        style: float = 0.18,
        use_speaker_boost: bool = True,
    ) -> str:
        clean_text = (text or "").strip()
        if not clean_text:
            raise ValueError("text is required")

        if not self.api_key or not self.voice_id:
            raise ValueError("ELEVENLABS_API_KEY or ELEVENLABS_VOICE_ID missing")

        if not filename:
            filename = f"jarvis_{uuid.uuid4().hex}.mp3"

        output_path = self.output_dir / filename

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}"
        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }
        payload = self._build_payload(
            text=clean_text,
            stability=stability,
            similarity_boost=similarity_boost,
            style=style,
            use_speaker_boost=use_speaker_boost,
        )

        response = requests.post(url, json=payload, headers=headers, timeout=90)
        response.raise_for_status()

        with output_path.open("wb") as f:
            f.write(response.content)

        return str(output_path).replace("\\", "/")