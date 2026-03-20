from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Any, Dict

import requests


class VoiceRuntimeEngine:
    """
    ElevenLabs TTS integration.
    Saves generated audio to generated_audio/.
    """

    def __init__(self) -> None:
        self.api_key = os.getenv("ELEVENLABS_API_KEY", "")
        self.voice_id = os.getenv("ELEVENLABS_VOICE_ID", "")
        self.base_url = "https://api.elevenlabs.io/v1"
        self.output_dir = Path("generated_audio")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def configured(self) -> bool:
        return bool(self.api_key and self.voice_id)

    def synthesize(self, text: str, filename: str = "jarvis_reply.mp3") -> Dict[str, Any]:
        if not self.configured():
            return {
                "status": "error",
                "message": "Missing ELEVENLABS_API_KEY or ELEVENLABS_VOICE_ID in .env",
            }

        url = f"{self.base_url}/text-to-speech/{self.voice_id}"
        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }
        payload = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
        }

        response = requests.post(url, headers=headers, json=payload, timeout=120)
        response.raise_for_status()

        file_path = self.output_dir / filename
        file_path.write_bytes(response.content)

        return {
            "status": "ok",
            "file_path": str(file_path).replace("\\", "/"),
            "filename": filename,
            "bytes": len(response.content),
        }

    def synthesize_for_whatsapp(self, text: str, filename: str = "jarvis_whatsapp_reply.mp3") -> Dict[str, Any]:
        return self.synthesize(text=text, filename=filename)
