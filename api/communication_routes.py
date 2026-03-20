from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, Form, HTTPException
from fastapi.responses import FileResponse, Response

from core.cognitive_self_improvement_engine import CognitiveSelfImprovementEngine
from core.decision.strategic_council_engine import StrategicCouncilEngine
from core.global_market_intelligence_system import GlobalMarketIntelligenceSystem
from core.voice_runtime_engine import VoiceRuntimeEngine
from core.twilio_whatsapp_engine import TwilioWhatsAppEngine

router = APIRouter(prefix="/comm", tags=["communications"])

learning_engine = CognitiveSelfImprovementEngine()
council_engine = StrategicCouncilEngine()
global_intel_engine = GlobalMarketIntelligenceSystem()
voice_engine = VoiceRuntimeEngine()
twilio_engine = TwilioWhatsAppEngine()


def _compose_jarvis_reply(message: str) -> str:
    council = council_engine.deliberate(topic=message, context="whatsapp inbound")
    risk = global_intel_engine.risk_matrix()

    recommendation = council.get("executive", {}).get("executive_recommendation", "")
    next_steps = council.get("executive", {}).get("next_steps", [])[:3]
    risk_flags = risk.get("risk_flags", [])[:2]
    opportunity_flags = risk.get("opportunity_flags", [])[:2]

    lines = [
        "JARVIS",
        recommendation or "No executive recommendation available.",
    ]

    if next_steps:
        lines.append("Siguientes pasos:")
        for step in next_steps:
            lines.append(f"- {step}")

    if risk_flags:
        lines.append("Riesgos:")
        for item in risk_flags:
            lines.append(f"- {item}")

    if opportunity_flags:
        lines.append("Oportunidades:")
        for item in opportunity_flags:
            lines.append(f"- {item}")

    return "\n".join(lines)


@router.post("/learning/log-decision")
def log_decision(payload: dict):
    return learning_engine.log_case(
        category=payload.get("category", "general"),
        prompt=payload.get("prompt", ""),
        recommendation=payload.get("recommendation", ""),
        outcome=payload.get("outcome", ""),
        score=float(payload.get("score", 0.0)),
        notes=payload.get("notes", ""),
        metadata=payload.get("metadata", {}),
    )


@router.get("/learning/review")
def learning_review():
    return learning_engine.review()


@router.post("/voice/synthesize")
def synthesize_voice(payload: dict):
    text = payload.get("text", "")
    filename = payload.get("filename", "jarvis_reply.mp3")

    if not text:
        raise HTTPException(status_code=400, detail="text is required")

    return voice_engine.synthesize(text=text, filename=filename)


@router.get("/audio/{filename}")
def get_audio(filename: str):
    path = Path("generated_audio") / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="audio file not found")
    return FileResponse(path, media_type="audio/mpeg", filename=filename)


@router.post("/whatsapp/send")
def whatsapp_send(payload: dict):
    to_number = payload.get("to", "")
    body = payload.get("body", "")

    if not to_number or not body:
        raise HTTPException(status_code=400, detail="to and body are required")

    return twilio_engine.send_text(to_number=to_number, body=body)


@router.post("/whatsapp/send-voice")
def whatsapp_send_voice(payload: dict):
    to_number = payload.get("to", "")
    text = payload.get("text", "")
    filename = payload.get("filename", "jarvis_whatsapp_reply.mp3")

    if not to_number or not text:
        raise HTTPException(status_code=400, detail="to and text are required")

    synth = voice_engine.synthesize_for_whatsapp(text=text, filename=filename)
    if synth.get("status") != "ok":
        return synth

    public_base = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
    if not public_base:
        return {
            "status": "error",
            "message": "Missing PUBLIC_BASE_URL in .env. Needed to expose generated audio file publicly.",
            "audio": synth,
        }

    media_url = f"{public_base}/comm/audio/{synth['filename']}"
    return twilio_engine.send_media(
        to_number=to_number,
        body="JARVIS voice reply",
        media_url=media_url,
    )


@router.post("/whatsapp/inbound")
async def whatsapp_inbound(
    Body: str = Form(default=""),
    From: str = Form(default=""),
    To: str = Form(default=""),
    MessageSid: str = Form(default=""),
    ProfileName: str = Form(default=""),
    NumMedia: str = Form(default="0"),
):
    inbound = {
        "Body": Body,
        "From": From,
        "To": To,
        "MessageSid": MessageSid,
        "ProfileName": ProfileName,
        "NumMedia": NumMedia,
    }

    payload = twilio_engine.inbound_payload(inbound)
    jarvis_reply = _compose_jarvis_reply(payload["body"])

    learning_engine.log_case(
        category="whatsapp_inbound",
        prompt=payload["body"],
        recommendation=jarvis_reply,
        outcome="reply_generated",
        score=0.0,
        notes="Automatic WhatsApp response generated.",
        metadata=payload,
    )

    xml = twilio_engine.twiml_reply(jarvis_reply)
    return Response(content=xml, media_type="application/xml")


@router.post("/whatsapp/inbound-voice")
async def whatsapp_inbound_voice(
    Body: str = Form(default=""),
    From: str = Form(default=""),
    To: str = Form(default=""),
    MessageSid: str = Form(default=""),
    ProfileName: str = Form(default=""),
):
    payload = {
        "Body": Body,
        "From": From,
        "To": To,
        "MessageSid": MessageSid,
        "ProfileName": ProfileName,
    }

    jarvis_reply = _compose_jarvis_reply(payload["Body"] or "voice note received without transcription")
    synth = voice_engine.synthesize_for_whatsapp(jarvis_reply, "jarvis_whatsapp_auto.mp3")

    if synth.get("status") != "ok":
        xml = twilio_engine.twiml_reply(jarvis_reply)
        return Response(content=xml, media_type="application/xml")

    public_base = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
    if not public_base:
        xml = twilio_engine.twiml_reply(jarvis_reply)
        return Response(content=xml, media_type="application/xml")

    media_url = f"{public_base}/comm/audio/{synth['filename']}"
    resp = twilio_engine.twiml_reply("JARVIS preparó una respuesta por voz.")
    # TwiML message with media is easier through plain XML replacement if needed later.
    # For now return text and use outbound send-voice endpoint for production flows.
    return Response(content=resp, media_type="application/xml")
