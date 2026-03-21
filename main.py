from dotenv import load_dotenv
def safe_import(module, name):
    try:
        mod = __import__(module, fromlist=[name])
        return getattr(mod, name)
    except Exception as e:
        print(f"[SAFE IMPORT ERROR] {module}.{name}: {e}")
        return None

def safe_instance(cls):
    try:
        return cls() if cls else None
    except Exception as e:
        print(f"[SAFE INIT ERROR] {cls}: {e}")
        return None
load_dotenv()

def safe_import(module, name):
    try:
        mod = __import__(module, fromlist=[name])
        return getattr(mod, name)
    except Exception as e:
        print(f"[IMPORT ERROR] {module}.{name}: {e}")
        return None

import os
from typing import Any, Dict, List

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

# =========================
# CORE IMPORTS
# =========================
from core.owner_digital_twin import OwnerDigitalTwin
from core.audit_engine import AuditEngine
from core.super_memory_system import SuperMemorySystem
from core.personality_engine import PersonalityEngine
from core.knowledge_engine import KnowledgeEngine
from core.reasoning_quality_engine import ReasoningQualityEngine
from core.agent_learning_engine import AgentLearningEngine
from core.presentation_engine import PresentationEngine
from core.family_office_engine import FamilyOfficeEngine
from core.wealth_optimizer import WealthOptimizer
from core.market_monitor import MarketMonitor
from core.data_fusion_engine import DataFusionEngine
from core.geopolitical_intelligence_engine import GeopoliticalIntelligenceEngine
from core.narrative_detection_engine import NarrativeDetectionEngine
from core.macro_regime_engine import MacroRegimeEngine
from core.alert_engine import AlertEngine
from core.daily_ops_engine import DailyOpsEngine
from core.scheduler_engine import JarvisScheduler
from core.real_agent_council import RealAgentCouncil
from core.email_intelligence_engine import EmailIntelligenceEngine
from core.calendar_intelligence_engine import CalendarIntelligenceEngine
from core.conversation_engine import ConversationEngine
from core.voice_response_engine import VoiceResponseEngine
from core.ticker_resolver import TickerResolver
from core.trader_alpha_engine import TraderAlphaEngine

# =========================
# MODELS
# =========================
from core.models import (
    ChatRequest,
    ChatResponse,
    ReportRequest,
    FeedbackRequest,
    PresentationRequest,
    AgentPersonalityRequest,
    AgentKnowledgeRequest,
    OpportunityRadarRequest,
    AlertCreateRequest,
    NarrativeRequest,
    RegimeRequest,
    MemoryStoreRequest,
    MemorySearchRequest,
    WhatsAppMessageRequest,
    VoiceTranscribeRequest,
    VoiceSynthesizeRequest,
    EmailDraftRequest,
    CalendarPlanRequest,
    MediaRequest,
)

# =========================
# INTERFACES
# =========================
try:
    from interfaces.whatsapp_real_interface import WhatsAppRealInterface
except Exception:
    WhatsAppRealInterface = None
try:
    from interfaces.voice_natural_interface import VoiceNaturalInterface
except Exception:
    VoiceNaturalInterface = None
try:
    from interfaces.premium_media_engine import PremiumMediaEngine
except Exception:
    PremiumMediaEngine = None

# =========================
# BASE ROUTERS
# =========================
from api.premium_routes import router as premium_router
from api.command_center_routes import router as command_center_router
from api.opportunity_routes import router as opportunity_router
from api.global_market_routes import router as global_market_router
from api.strategic_council_routes import router as strategic_council_router
from api.communication_routes import router as communication_router
from api.executive_intelligence_routes import router as executive_intelligence_router
from api.global_opportunity_radar_pro_routes import router as global_opportunity_radar_pro_router
from api.strategic_foresight_pro_routes import router as strategic_foresight_pro_router
from api.whatsapp_routes import router as whatsapp_router
from api.voice_routes import router as voice_router
from api.opportunity_hunter_routes import router as opportunity_hunter_router
from api.operator_routes import router as operator_router
from api.apple_watch_routes import router as apple_watch_router
from api.golf_routes import router as golf_router
from api.golf_vision_routes import router as golf_vision_router
from api.autonomous_routes import router as autonomous_router
from api.computer_agent_routes import router as computer_agent_router

# =========================
# OPTIONAL / PREMIUM ROUTERS
# =========================
try:
    from api.silicon_valley_routes import router as silicon_valley_router
except Exception:
    silicon_valley_router = None

try:
    from api.health_performance_routes import router as health_performance_router
except Exception:
    health_performance_router = None

try:
    from api.ops_routes import router as ops_router
except Exception:
    ops_router = None

try:
    from api.agent_orchestrator_routes import router as agent_orchestrator_router
except Exception:
    agent_orchestrator_router = None

try:
    from api.computer_control_routes import router as computer_control_router
except Exception:
    computer_control_router = None

try:
    from api.trader_alpha_routes import router as trader_alpha_router
except Exception:
    trader_alpha_router = None

try:
    from api.dashboard_routes import router as dashboard_router
except Exception:
    dashboard_router = None

try:
    from api.agent_optimization_routes import router as agent_optimization_router
except Exception:
    agent_optimization_router = None


# =========================
# ENGINE INSTANCES
# =========================
def safe_instance(cls):
    try:
        return cls()
    except Exception as e:
        print(f"[INIT ERROR] {cls}: {e}")
        return None

identity = safe_instance(OwnerDigitalTwin)
audit = safe_instance(AuditEngine)
memory = safe_instance(SuperMemorySystem)
personality_engine = PersonalityEngine()
knowledge_engine = KnowledgeEngine()
reasoning_quality_engine = ReasoningQualityEngine()
learning_engine = AgentLearningEngine()
presentation_engine = PresentationEngine()
family_office_engine = FamilyOfficeEngine()
wealth_optimizer = WealthOptimizer()
market_monitor = MarketMonitor()
data_fusion_engine = DataFusionEngine()
geo_engine = GeopoliticalIntelligenceEngine()
narrative_engine = NarrativeDetectionEngine()
regime_engine = MacroRegimeEngine()
alert_engine = AlertEngine()
daily_ops_engine = DailyOpsEngine()
scheduler_engine = JarvisScheduler()
council_engine = RealAgentCouncil()
conversation_engine = ConversationEngine()
voice_response_engine = VoiceResponseEngine()
ticker_resolver = TickerResolver()
trader_engine = TraderAlphaEngine()

whatsapp = safe_instance(WhatsAppRealInterface)
voice = safe_instance(VoiceNaturalInterface)
media = safe_instance(PremiumMediaEngine)
email_engine = EmailIntelligenceEngine()
calendar_engine = CalendarIntelligenceEngine()

# =========================
# APP
# =========================
app = FastAPI(
    title="JARVIS",
    description="Personal AI Operating System",
    version="12.2"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# HELPER FUNCTIONS
# =========================
def _safe_owner_name() -> str:
    try:
        summary = identity.owner_summary()
        if isinstance(summary, dict):
            return summary.get("name") or "Juan Camilo"
    except Exception:
        pass
    return "Juan Camilo"


def _safe_owner_summary() -> Dict[str, Any]:
    try:
        summary = identity.owner_summary()
        if isinstance(summary, dict):
            if not summary.get("name"):
                summary["name"] = "Juan Camilo"
            return summary
    except Exception:
        pass
    return {"name": "Juan Camilo"}


# =========================
# ROUTER REGISTRATION
# =========================
app.include_router(premium_router)
app.include_router(command_center_router)
app.include_router(opportunity_router)
app.include_router(global_market_router)
app.include_router(strategic_council_router)
app.include_router(communication_router)
app.include_router(executive_intelligence_router)
app.include_router(global_opportunity_radar_pro_router)
app.include_router(strategic_foresight_pro_router)
app.include_router(whatsapp_router)
app.include_router(voice_router)
app.include_router(opportunity_hunter_router)
app.include_router(operator_router)
app.include_router(apple_watch_router)
app.include_router(golf_router)
app.include_router(golf_vision_router)
app.include_router(autonomous_router)
app.include_router(computer_agent_router)

if silicon_valley_router is not None:
    app.include_router(silicon_valley_router)

if health_performance_router is not None:
    app.include_router(health_performance_router)

if ops_router is not None:
    app.include_router(ops_router)

if agent_orchestrator_router is not None:
    app.include_router(agent_orchestrator_router)

if computer_control_router is not None:
    app.include_router(computer_control_router)

if trader_alpha_router is not None:
    app.include_router(trader_alpha_router)

if dashboard_router is not None:
    app.include_router(dashboard_router)

if agent_optimization_router is not None:
    app.include_router(agent_optimization_router)


# =========================
# LIFECYCLE
# =========================
@app.on_event("startup")
def startup_event():
    try:
        scheduler_engine.start()
    except Exception as exc:
        print(f"Warning: scheduler could not start: {exc}")


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"error": str(exc)})


# =========================
# SYSTEM ENDPOINTS
# =========================
@app.get("/")
def root():
    return {
        "system": "JARVIS",
        "status": "online",
        "version": "12.2",
        "owner": _safe_owner_summary(),
        "modules": {
            "strategic_council": True,
            "global_market_intelligence": True,
            "executive_intelligence": True,
            "opportunity_radar_pro": True,
            "strategic_foresight_pro": True,
            "communication": True,
            "voice": True,
            "whatsapp": True,
            "health_performance": health_performance_router is not None,
            "silicon_valley": silicon_valley_router is not None,
            "ops_dashboard": ops_router is not None,
            "agent_orchestrator": agent_orchestrator_router is not None,
            "computer_control": computer_control_router is not None,
            "trader_alpha": trader_alpha_router is not None,
            "dashboard": dashboard_router is not None,
            "human_conversation": True,
        },
    }


@app.get("/health")
def health():
    return {
        "status": "running",
        "system": "JARVIS",
        "version": "12.2",
        "owner": _safe_owner_name(),
    }


@app.get("/owner")
def owner():
    try:
        profile = identity.profile()
        if isinstance(profile, dict) and not profile.get("name"):
            profile["name"] = "Juan Camilo"
        return profile
    except Exception:
        return _safe_owner_summary()


@app.get("/automation/status")
def automation_status():
    try:
        return scheduler_engine.status()
    except Exception as exc:
        return {"status": "unavailable", "error": str(exc)}


@app.get("/audit/events")
def audit_events():
    return {"events": audit.read_events(50)}


# =========================
# AGENT / KNOWLEDGE / MEMORY
# =========================
@app.post("/agent/personality")
def agent_personality(request: AgentPersonalityRequest):
    return personality_engine.get_agent_personality(request.agent_name)


@app.post("/agent/knowledge")
def agent_knowledge(request: AgentKnowledgeRequest):
    return {
        "domain": request.domain,
        "knowledge": knowledge_engine.get_knowledge(request.domain),
    }


@app.post("/memory/store")
def memory_store(request: MemoryStoreRequest):
    return memory.store(request.category, request.text)


@app.post("/memory/search")
def memory_search(request: MemorySearchRequest):
    return memory.search(request.keyword)


@app.get("/memory/categories")
def memory_categories():
    return {"categories": memory.categories()}


# =========================
# LEARNING
# =========================
@app.post("/learning/feedback")
def learning_feedback(request: FeedbackRequest):
    return learning_engine.store_feedback(
        request.decision,
        request.outcome,
        request.score,
        request.notes,
    )


@app.get("/learning/summary")
def learning_summary():
    return learning_engine.summary()


# =========================
# PRESENTATION / REPORTING
# =========================
@app.post("/presentation/outline")
def presentation_outline(request: PresentationRequest):
    return presentation_engine.create_outline(
        request.title,
        request.objective,
        request.audience,
        request.key_points,
    )


@app.post("/presentation/pptx")
def presentation_pptx(request: PresentationRequest):
    return presentation_engine.create_pptx(
        request.title,
        request.objective,
        request.audience,
        request.key_points,
        request.filename,
    )


@app.post("/report/pdf")
def generate_pdf_report(request: ReportRequest):
    output_dir = "generated_reports"
    os.makedirs(output_dir, exist_ok=True)

    filename = request.filename if request.filename.endswith(".pdf") else f"{request.filename}.pdf"
    filepath = os.path.join(output_dir, filename)

    c = canvas.Canvas(filepath, pagesize=letter)
    height = letter[1]

    y = height - 50
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y, request.title)

    y -= 30
    c.setFont("Helvetica", 10)

    lines = request.content.split("\n")
    for line in lines:
        if y < 50:
            c.showPage()
            y = height - 50
            c.setFont("Helvetica", 10)
        c.drawString(50, y, line[:110])
        y -= 15

    c.save()

    return FileResponse(
        filepath,
        media_type="application/pdf",
        filename=filename,
    )


# =========================
# WEALTH / MARKETS / INTEL
# =========================
@app.post("/wealth/family-office")
def family_office(payload: dict):
    return family_office_engine.analyze_wealth(payload)


@app.post("/wealth/optimize")
def optimize_wealth(payload: dict):
    capital = float(payload.get("capital", 0))
    return wealth_optimizer.optimize(capital)


@app.get("/market/monitor")
def market_monitor_scan():
    return market_monitor.scan()


@app.get("/data/markets")
def data_markets():
    return data_fusion_engine.market_snapshot()


@app.get("/data/macro")
def data_macro():
    return data_fusion_engine.macro_summary()


@app.post("/intelligence/geopolitical")
def intelligence_geopolitical(request: OpportunityRadarRequest):
    payload = geo_engine.analyze(request.topic, request.context)
    audit.log_event("geopolitical_intelligence_request", payload)
    return payload


@app.post("/intelligence/narratives")
def intelligence_narratives(request: NarrativeRequest):
    payload = narrative_engine.analyze(request.topic, request.context)
    audit.log_event("narrative_request", payload)
    return payload


@app.post("/intelligence/regime")
def intelligence_regime(request: RegimeRequest):
    payload = regime_engine.analyze(request.topic, request.context)
    audit.log_event("regime_request", payload)
    return payload


# =========================
# COUNCIL / CHAT
# =========================
@app.post("/council")
def council_route(payload: dict):
    topic = payload.get("topic", "")
    domain = payload.get("domain", "general")
    owner_name = payload.get("owner_name", _safe_owner_name())
    return council_engine.deliberate(topic, domain, owner_name)


@app.post("/chat")
def chat(request: ChatRequest):
    reply = conversation_engine.reply(
        message=request.message,
        domain=request.domain,
    )

    memory.store("chat", request.message)
    audit.log_event("chat_request", {"message": request.message, "domain": request.domain})

    return {
        "reply": reply
    }


@app.post("/chat/voice")
def chat_voice(payload: dict):
    message = (payload.get("message") or "").strip()
    domain = (payload.get("domain") or "general").strip()

    if not message:
        return {"error": "message is required"}

    reply = conversation_engine.reply(message=message, domain=domain)
    memory.store("chat", message)
    audit.log_event("chat_voice_request", {"message": message, "domain": domain})

    try:
        audio_file = voice_response_engine.speak(reply)
    except Exception as exc:
        return {
            "reply": reply,
            "audio_file": None,
            "audio_error": str(exc)
        }

    return {
        "reply": reply,
        "audio_file": audio_file
    }


@app.post("/trader/analyze")
def trader_analyze(payload: dict):
    raw_symbol = (payload.get("symbol") or "").strip()
    if not raw_symbol:
        return {"error": "symbol is required"}

    symbol = ticker_resolver.resolve(raw_symbol)
    return trader_engine.analyze(symbol)


# =========================
# ALERTS / OPS
# =========================
@app.post("/alerts/create")
def create_alert(request: AlertCreateRequest):
    return alert_engine.create(
        request.symbol,
        request.condition,
        request.threshold,
        request.note,
    )


@app.get("/alerts")
def list_alerts():
    return {"alerts": alert_engine.list_alerts()}


@app.post("/alerts/evaluate")
def evaluate_alerts():
    return alert_engine.evaluate()


@app.post("/jobs/run/daily-briefing")
def run_daily_briefing():
    return daily_ops_engine.run_daily_briefing("global macro")


# =========================
# INTERFACES
# =========================
@app.post("/interface/whatsapp/incoming")
def whatsapp_incoming(request: WhatsAppMessageRequest):
    return whatsapp.inbound(request.phone, request.text)


@app.post("/interface/whatsapp/send")
def whatsapp_send(request: WhatsAppMessageRequest):
    return whatsapp.build_outbound(request.phone, request.text)


@app.post("/interface/voice/transcribe")
def voice_transcribe(request: VoiceTranscribeRequest):
    return voice.transcribe(request.audio_path)


@app.post("/interface/voice/synthesize")
def voice_synthesize(request: VoiceSynthesizeRequest):
    return voice.synthesize(request.text, request.provider, request.style)


@app.post("/media/analyze")
def media_analyze(request: MediaRequest):
    return media.analyze(request.file_path, request.task)


@app.post("/email/draft")
def email_draft(request: EmailDraftRequest):
    return email_engine.draft_reply(
        request.sender,
        request.subject,
        request.body,
        request.tone,
    )


@app.post("/calendar/plan")
def calendar_plan(request: CalendarPlanRequest):
    return calendar_engine.plan(
        request.objective,
        request.duration_minutes,
        request.participants,
    )









