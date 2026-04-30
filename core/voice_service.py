from __future__ import annotations

import logging
import os
import re
import time
import urllib.request
import urllib.error
import json as _json
from typing import Optional

logger = logging.getLogger(__name__)


class VoiceService:
    """
    ElevenLabs TTS integration.
    All config via env vars: ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID, ELEVENLABS_MODEL_ID.
    Returns raw MP3 bytes or None on failure — never crashes callers.
    """

    _DEFAULT_VOICE = "21m00Tcm4TlvDq8ikWAM"   # ElevenLabs Rachel
    _DEFAULT_MODEL = "eleven_turbo_v2_5"
    _BASE_URL      = "https://api.elevenlabs.io/v1/text-to-speech"
    _MAX_CHARS     = 1500
    _TIMEOUT_S     = 2.5
    _MAX_RETRIES   = 1

    def __init__(self) -> None:
        self.api_key  = os.getenv("ELEVENLABS_API_KEY", "").strip()
        self.voice_id = os.getenv("ELEVENLABS_VOICE_ID", self._DEFAULT_VOICE).strip()
        self.model_id = os.getenv("ELEVENLABS_MODEL_ID", self._DEFAULT_MODEL).strip()

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def status(self) -> dict:
        s = {
            "status":                  "ok" if self.configured else "degraded",
            "elevenlabs_configured":   self.configured,
            "voice_id_configured":     bool(os.getenv("ELEVENLABS_VOICE_ID")),
            "model":                   self.model_id,
            "reason":                  None if self.configured else "ELEVENLABS_API_KEY not set",
        }
        print(f"[VOICE STATUS] configured={s['elevenlabs_configured']} model={s['model']}")
        return s

    def speak(self, text: str) -> Optional[bytes]:
        """Return MP3 bytes for text, or None on any failure."""
        if not self.configured:
            print("[VOICE ERROR] ELEVENLABS_API_KEY not set — TTS skipped")
            logger.debug("VoiceService: ELEVENLABS_API_KEY not set — skipping TTS")
            return None

        clean = self._sanitize(text)
        if not clean:
            return None

        print(f"[VOICE TTS] Sending {len(clean)} chars to ElevenLabs voice={self.voice_id} model={self.model_id}")
        for attempt in range(self._MAX_RETRIES + 1):
            try:
                t0      = time.monotonic()
                data    = self._call_api(clean)
                elapsed = time.monotonic() - t0
                print(f"[VOICE TTS] OK — {len(data)} bytes in {elapsed:.2f}s")
                logger.info("ElevenLabs TTS: %d chars → %d bytes in %.2fs",
                            len(clean), len(data), elapsed)
                return data
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")[:300] if hasattr(exc, "read") else ""
                print(f"[VOICE ERROR] ElevenLabs HTTP {exc.code} attempt={attempt+1}: {body}")
                logger.warning("ElevenLabs HTTP %s on attempt %d: %s", exc.code, attempt + 1, body)
                if exc.code in (401, 403):
                    break   # bad key — no point retrying
            except urllib.error.URLError as exc:
                print(f"[VOICE ERROR] Network error attempt={attempt+1}: {exc}")
                logger.warning("ElevenLabs network error on attempt %d: %s", attempt + 1, exc)
            except Exception as exc:
                print(f"[VOICE ERROR] TTS exception attempt={attempt+1}: {exc}")
                logger.warning("ElevenLabs TTS failed on attempt %d: %s", attempt + 1, exc)
        return None

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _sanitize(self, text: str) -> str:
        t = (text or "").strip()
        t = re.sub(r"```[\s\S]*?```", " ", t)         # remove code blocks
        t = re.sub(r"`[^`]+`", " ", t)                # inline code
        t = re.sub(r"\*\*|\*|__", "", t)              # markdown bold/italic
        t = re.sub(r"\{[^}]{0,200}\}", " ", t)        # small JSON blobs
        t = re.sub(r"https?://\S+", "link", t)        # URLs
        t = re.sub(r"[#>{}\[\]|\\]", " ", t)          # special chars
        t = re.sub(r"\s+", " ", t)
        return t[:self._MAX_CHARS].strip()

    def _call_api(self, text: str) -> bytes:
        url     = f"{self._BASE_URL}/{self.voice_id}"
        payload = _json.dumps({
            "text":       text,
            "model_id":   self.model_id,
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        }).encode("utf-8")

        req = urllib.request.Request(url, data=payload, method="POST")
        req.add_header("xi-api-key",    self.api_key)
        req.add_header("Content-Type",  "application/json")
        req.add_header("Accept",        "audio/mpeg")

        with urllib.request.urlopen(req, timeout=self._TIMEOUT_S) as resp:
            return resp.read()


# Module-level singleton — callers import this directly
_voice_service: Optional[VoiceService] = None


def get_voice_service() -> VoiceService:
    global _voice_service
    if _voice_service is None:
        _voice_service = VoiceService()
    return _voice_service
