from fastapi import APIRouter

from core.real_agent_council import RealAgentCouncil
from core.live_news_engine import LiveNewsEngine
from core.geopolitical_intelligence_engine import GeopoliticalIntelligenceEngine
from core.agent_learning_engine import AgentLearningEngine
from interfaces.whatsapp_real_interface import WhatsAppRealInterface
from interfaces.voice_natural_interface import VoiceNaturalInterface
from interfaces.premium_media_engine import PremiumMediaEngine
from core.email_intelligence_engine import EmailIntelligenceEngine
from core.calendar_intelligence_engine import CalendarIntelligenceEngine

router = APIRouter(prefix="/premium", tags=["premium"])

council = RealAgentCouncil()
news_engine = LiveNewsEngine()
geo_engine = GeopoliticalIntelligenceEngine()
learning_engine = AgentLearningEngine()
whatsapp = WhatsAppRealInterface()
voice = VoiceNaturalInterface()
media = PremiumMediaEngine()
email_engine = EmailIntelligenceEngine()
calendar_engine = CalendarIntelligenceEngine()


@router.post("/council")
def premium_council(payload: dict):
    topic = payload.get("topic", "")
    domain = payload.get("domain", "general")
    owner_name = payload.get("owner_name", "Juan Camilo Montenegro")
    return council.deliberate(topic=topic, domain=domain, owner_name=owner_name)


@router.get("/news")
def premium_news():
    return {"items": news_engine.fetch()}


@router.post("/geopolitical")
def premium_geopolitical(payload: dict):
    topic = payload.get("topic", "")
    context = payload.get("context", "")
    return geo_engine.analyze(topic=topic, context=context)


@router.post("/learning/feedback")
def premium_learning_feedback(payload: dict):
    return learning_engine.store_feedback(
        decision=payload.get("decision", ""),
        outcome=payload.get("outcome", ""),
        score=float(payload.get("score", 0)),
        notes=payload.get("notes", ""),
    )


@router.get("/learning/summary")
def premium_learning_summary():
    return learning_engine.summary()


@router.post("/whatsapp/send")
def premium_whatsapp_send(payload: dict):
    return whatsapp.build_outbound(
        phone=payload.get("phone", ""),
        text=payload.get("text", ""),
    )


@router.post("/voice/synthesize")
def premium_voice_synthesize(payload: dict):
    return voice.synthesize(
        text=payload.get("text", ""),
        provider=payload.get("provider", "elevenlabs"),
        style=payload.get("style", "natural executive"),
    )


@router.post("/voice/transcribe")
def premium_voice_transcribe(payload: dict):
    return voice.transcribe(audio_path=payload.get("audio_path", ""))


@router.post("/media/analyze")
def premium_media_analyze(payload: dict):
    return media.analyze(
        file_path=payload.get("file_path", ""),
        task=payload.get("task", "analyze"),
    )


@router.post("/email/draft")
def premium_email_draft(payload: dict):
    return email_engine.draft_reply(
        sender=payload.get("sender", ""),
        subject=payload.get("subject", ""),
        body=payload.get("body", ""),
        tone=payload.get("tone", "executive"),
    )


@router.post("/calendar/plan")
def premium_calendar_plan(payload: dict):
    return calendar_engine.plan(
        objective=payload.get("objective", ""),
        duration_minutes=int(payload.get("duration_minutes", 60)),
        participants=payload.get("participants", []),
    )
