from fastapi import APIRouter, Request

from core.voice_ai_engine import VoiceAIEngine
from core.conversation_engine import ConversationEngine

router = APIRouter(prefix="/voice", tags=["voice"])

voice_engine = VoiceAIEngine()
conversation_engine = ConversationEngine()


@router.post("/whatsapp-voice")
async def whatsapp_voice(request: Request):
    form = await request.form()

    media_url = form.get("MediaUrl0")
    phone = form.get("From")

    if not media_url:
        return {"error": "MediaUrl0 is required", "phone": phone}

    audio_file = voice_engine.download_audio(media_url)
    text = voice_engine.transcribe(audio_file)

    reply = conversation_engine.reply(
        message=text,
        domain="general",
    )

    audio_reply = voice_engine.synthesize(reply)

    return {
        "phone": phone,
        "transcribed": text,
        "reply": reply,
        "audio_file": audio_reply,
    }