from datetime import datetime
from pathlib import Path
from typing import List, Optional
import json
import os
import shutil
import threading
import time

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from openai import OpenAI as _OpenAI
    _OPENAI_AVAILABLE = True
except ImportError:
    _OPENAI_AVAILABLE = False

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from core.product_brain import ProductBrain
from core.product_brain_pro import ProductBrainPro
from core.dashboard_workspace_engine import DashboardWorkspaceEngine
from core.meetings_engine import MeetingsEngine
from core.agent_orchestrator_pro import AgentOrchestratorPro
from core.news_intelligence_engine import NewsIntelligenceEngine
from core.golf_dashboard_engine import GolfDashboardEngine
from core.voice_service import get_voice_service
from core.live_news_engine import LiveNewsEngine
from core.project_planner_engine import ProjectPlannerEngine
from core.user_engine import UserEngine
from core.auth_engine import AuthEngine
from core.calendar_engine import CalendarEngine
from core.memory_engine import MemoryEngine
from core.notification_engine import NotificationEngine
from core.ai_orchestrator import AIOrchestrator, classify_intent
from core.automation_engine import AutomationEngine
from core.integrations import (
    TokenStore,
    GoogleCalendarIntegration,
    OutlookIntegration,
    GmailIntegration,
    SlackIntegration,
)
from core.integrations.base import ConfigError as _IntegrationConfigError
from core.analytics_engine import AnalyticsEngine as _AnalyticsEngine
from core.voice_engine import VoiceEngine
from core.wow_engine import WowEngine as _WowEngine
from core.golf_vision_engine import GolfVisionEngine

_analytics = _AnalyticsEngine()
_wow       = _WowEngine()

try:
    from core.market_intelligence_engine import MarketIntelligenceEngine as _MarketIntelEngine
    _mkt_engine = _MarketIntelEngine()
    _MKT_AVAILABLE = True
except Exception:
    _mkt_engine = None
    _MKT_AVAILABLE = False

app = FastAPI(title="JARVIS OS")
brain           = ProductBrain()
brain_pro       = ProductBrainPro()
workspace       = DashboardWorkspaceEngine()
meetings_engine = MeetingsEngine()
orchestrator    = AgentOrchestratorPro()
news_engine     = NewsIntelligenceEngine()
golf_engine     = GolfDashboardEngine()
live_news       = LiveNewsEngine()
planner         = ProjectPlannerEngine()
user_engine     = UserEngine()
auth_engine     = AuthEngine(user_engine)
ai_orchestrator = AIOrchestrator()

# ── Auth dependencies ────────────────────────────────────────────────
_bearer = HTTPBearer(auto_error=False)

def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict:
    if not creds:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user = auth_engine.decode_token(creds.credentials)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user

def get_optional_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict:
    """Returns decoded user or falls back to owner for legacy routes."""
    if creds:
        user = auth_engine.decode_token(creds.credentials)
        if user:
            return user
    return {"user_id": "owner", "role": "owner"}

# ── Per-user engine factories (cached) ──────────────────────────────
_ws_cache: dict = {}
_me_cache: dict = {}
_ge_cache: dict = {}

def _ws(user_id: str) -> DashboardWorkspaceEngine:
    if user_id not in _ws_cache:
        if user_id == "owner":
            _ws_cache[user_id] = workspace
        else:
            path = BASE_DIR / "data" / f"workspace_{user_id}.json"
            ws = DashboardWorkspaceEngine(base_path=str(path))
            ws.meetings_engine = _me(user_id)   # inject scoped meetings
            _ws_cache[user_id] = ws
    return _ws_cache[user_id]

def _me(user_id: str) -> MeetingsEngine:
    if user_id not in _me_cache:
        if user_id == "owner":
            _me_cache[user_id] = meetings_engine
        else:
            path = BASE_DIR / "data" / f"meetings_{user_id}.json"
            _me_cache[user_id] = MeetingsEngine(file_path=str(path))
    return _me_cache[user_id]

def _ge(user_id: str) -> GolfDashboardEngine:
    if user_id not in _ge_cache:
        if user_id == "owner":
            _ge_cache[user_id] = golf_engine
        else:
            bag_path = BASE_DIR / "data" / "golf" / f"bag_{user_id}.json"
            _ge_cache[user_id] = GolfDashboardEngine(bag_file=str(bag_path))
    return _ge_cache[user_id]

def _user_name(user_id: str) -> str:
    u = user_engine.get_user(user_id)
    return u["name"] if u else "User"

_cal_cache: dict = {}

def _cal(user_id: str) -> CalendarEngine:
    if user_id not in _cal_cache:
        path = BASE_DIR / "data" / f"calendar_{user_id}.json"
        _cal_cache[user_id] = CalendarEngine(str(path))
    return _cal_cache[user_id]

_mem_cache: dict = {}

def _memory(user_id: str) -> MemoryEngine:
    if user_id not in _mem_cache:
        path = BASE_DIR / "data" / "memory" / f"{user_id}.json"
        _mem_cache[user_id] = MemoryEngine(str(path))
    return _mem_cache[user_id]

_notif_cache: dict = {}

def _notif(user_id: str) -> NotificationEngine:
    if user_id not in _notif_cache:
        path = BASE_DIR / "data" / f"notifications_{user_id}.json"
        _notif_cache[user_id] = NotificationEngine(str(path))
    return _notif_cache[user_id]

_auto_cache: dict = {}

def _auto(user_id: str) -> AutomationEngine:
    if user_id not in _auto_cache:
        path = BASE_DIR / "data" / "automations" / f"{user_id}.json"
        eng  = AutomationEngine(str(path), user_id=user_id)
        eng.inject(
            notify=_notif(user_id),
            memory=_memory(user_id),
            orchestrator=ai_orchestrator,
            workspace=_ws(user_id),
        )
        _auto_cache[user_id] = eng
    return _auto_cache[user_id]

# ── Integrations hub ─────────────────────────────────────────────────

_tok_cache: dict = {}

def _tok(user_id: str) -> TokenStore:
    if user_id not in _tok_cache:
        path = BASE_DIR / "data" / "integrations" / f"{user_id}.json"
        _tok_cache[user_id] = TokenStore(str(path))
    return _tok_cache[user_id]

_PROVIDERS = ("google_calendar", "outlook", "gmail", "slack")

# ── Golf Vision Engine ───────────────────────────────────────────────

_gve_cache: dict = {}

def _gve(user_id: str) -> GolfVisionEngine:
    if user_id not in _gve_cache:
        path = BASE_DIR / "data" / "golf_vision" / f"{user_id}.json"
        _gve_cache[user_id] = GolfVisionEngine(str(path), user_id)
    return _gve_cache[user_id]

# ── Voice Engine ──────────────────────────────────────────────────────

_ve_cache: dict = {}

def _voice_engine(user_id: str) -> VoiceEngine:
    if user_id not in _ve_cache:
        path = BASE_DIR / "data" / "voice" / f"{user_id}.json"
        _ve_cache[user_id] = VoiceEngine(str(path), user_id)
    return _ve_cache[user_id]

def _integration(user_id: str, provider: str):
    """Return the correct integration instance for a given provider."""
    ts = _tok(user_id)
    if provider == "google_calendar": return GoogleCalendarIntegration(ts)
    if provider == "outlook":         return OutlookIntegration(ts)
    if provider == "gmail":           return GmailIntegration(ts)
    if provider == "slack":           return SlackIntegration(ts)
    raise ValueError(f"Unknown provider: {provider}")

BASE_DIR       = Path(__file__).resolve().parent
DASHBOARD_HTML = BASE_DIR / "dashboard" / "jarvis_futuristic.html"
UPLOADS_DIR    = BASE_DIR / "dashboard" / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


# ================================================================
# LLM — OpenAI wrapper
# json_mode=True  → response_format json_object, low temp, 200 tok
# json_mode=False → natural prose, normal temp, 600 tok
# ================================================================
_llm_client = None


def _get_llm():
    global _llm_client
    if not _OPENAI_AVAILABLE:
        return None
    if _llm_client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            _llm_client = _OpenAI(api_key=api_key)
    return _llm_client


def generate_response(messages: list, json_mode: bool = False) -> str | None:
    client = _get_llm()
    if not client:
        return None
    try:
        kwargs: dict = {
            "model":       os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            "messages":    messages,
            "max_tokens":  200 if json_mode else 600,
            "temperature": 0.1 if json_mode else 0.72,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        resp = client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content.strip()
    except Exception:
        return None


# ================================================================
# CHAT MEMORY — last 5 exchanges (10 messages)
# ================================================================
_HISTORY_LIMIT = 5
_chat_history: list[dict] = []


def _push_history(role: str, content: str) -> None:
    _chat_history.append({"role": role, "content": content[:800]})
    while len(_chat_history) > _HISTORY_LIMIT * 2:
        _chat_history.pop(0)


# ================================================================
# JARVIS MEMORY — persistent semantic memory, non-blocking
# ================================================================
_RECALL_TRIGGERS: frozenset[str] = frozenset({
    # English
    "what did i tell you", "remember when", "last time", "previously",
    "what did we discuss", "you said", "you told me", "recall",
    "what do you know about me", "my history",
    # Spanish
    "qué te dije", "recuerdas cuando", "la última vez", "anteriormente",
    "de qué hablamos", "me dijiste", "dijiste que", "recuerda",
    "qué sabes de mí", "mi historial",
})


def _mem():
    from core.jarvis_memory import get_jarvis_memory
    return get_jarvis_memory()


def _push_memory(user_msg: str, reply: str, agent: str = "", domain: str = "") -> None:
    threading.Thread(
        target=lambda: _mem().store(user_msg, reply, agent=agent, domain=domain),
        daemon=True,
    ).start()


def _handle_recall_query(message: str) -> dict:
    memories = _mem().last_n(8)
    if not memories:
        no_mem = "No tengo interacciones previas guardadas todavía."
        _push_history("user", message)
        _push_history("assistant", no_mem)
        return {
            "type": "memory_recall", "reply": no_mem, "summary": no_mem,
            "details": {}, "action": "recall", "confidence": 0.95,
            "source": "jarvis_memory",
        }
    lines = []
    for m in reversed(memories[-5:]):
        ts = m["ts"][:10]
        u  = m["user"][:80]
        o  = m["output"][:120]
        lines.append(f"[{ts}] Tú: {u}\nJARVIS: {o}")
    reply = "Esto es lo que recuerdo de nuestras últimas conversaciones:\n\n" + "\n\n".join(lines)
    _push_history("user", message)
    _push_history("assistant", reply)
    return {
        "type": "memory_recall", "reply": reply,
        "summary": f"Memory recall: {len(memories)} interactions found.",
        "details": {"memories": memories}, "action": "recall",
        "confidence": 0.95, "source": "jarvis_memory",
    }


def _action_to_domain(action: str) -> str:
    _MAP = {
        "analyze": "finance", "scan": "finance", "news": "general",
        "pipeline": "system",  "agents": "system",  "golf": "golf",
        "workspace": "workspace", "medical": "medical",
        "legal": "legal", "fitness": "fitness", "coach": "general",
    }
    return _MAP.get(action, "general")


# ================================================================
# USER PROFILE — built from memory patterns, injected into prompts
# ================================================================
def _build_user_profile(message: str) -> str:
    """
    Analyses last 20 memory entries to derive user preferences,
    recurring domains, and behavioural patterns for personalisation.
    Returns compact string suitable for LLM injection (<200 chars).
    """
    try:
        memories = _mem().last_n(20)
        if not memories:
            return ""

        domain_counts: dict[str, int] = {}
        for m in memories:
            d = m.get("domain", "general")
            if d:
                domain_counts[d] = domain_counts.get(d, 0) + 1

        # Top 2 domains
        top_domains = sorted(domain_counts, key=lambda k: -domain_counts[k])[:2]

        # Recency signal
        recent_domains = [m.get("domain", "") for m in memories[-5:] if m.get("domain")]
        latest = recent_domains[0] if recent_domains else ""

        parts = []
        if top_domains:
            parts.append(f"Top interests: {', '.join(top_domains)}")
        if latest and latest not in top_domains:
            parts.append(f"Latest focus: {latest}")

        return "User profile — " + ". ".join(parts) + "." if parts else ""
    except Exception:
        return ""


def _detect_feedback_signal(message: str) -> str:
    """
    Returns 'repeat' if user appears to re-ask (agent failed),
    'expand' if user is building on a previous answer,
    'new' otherwise.
    Drives self-improvement signal tracking.
    """
    low = message.lower()

    repeat_signals = [
        "no entendí", "no entendiste", "didn't understand", "explain again",
        "explica de nuevo", "that's not", "eso no", "no respondiste",
        "didn't answer", "wrong", "incorrecto", "no es eso", "not what i asked",
    ]
    expand_signals = [
        "and also", "y también", "what about", "qué hay de", "more detail",
        "más detalle", "expand on", "amplía", "tell me more", "cuéntame más",
        "además", "furthermore", "building on that",
    ]

    if any(s in low for s in repeat_signals):
        return "repeat"
    if any(s in low for s in expand_signals):
        return "expand"
    return "new"


# ================================================================
# CONTEXT — pipeline + news, 2-min TTL, never blocks the endpoint
# ================================================================
_ctx_cache: dict = {"data": "", "ts": 0.0}
_CTX_TTL = 120.0


def _get_context() -> str:
    now = time.monotonic()
    if _ctx_cache["data"] and (now - _ctx_cache["ts"]) < _CTX_TTL:
        return _ctx_cache["data"]

    parts: list[str] = []

    try:
        pipe  = orchestrator.pipeline_state()
        stage = pipe.get("stage", "UNKNOWN")
        prog  = pipe.get("progress", 0)
        msg   = pipe.get("message", "")
        parts.append(f"Pipeline: {stage} {int(prog * 100)}% — {msg}")
    except Exception:
        pass

    try:
        items  = news_engine.fetch_categorized(max_per_category=2)
        titles = [n["title"] for n in items[:4]]
        if titles:
            parts.append("Recent headlines: " + " | ".join(titles))
    except Exception:
        pass

    ctx = "\n".join(parts)
    _ctx_cache["data"] = ctx
    _ctx_cache["ts"]   = now
    return ctx


# ================================================================
# DECISION VALIDATION
# ================================================================
_VALID_ACTIONS = frozenset({
    "none",
    # market / finance
    "analyze", "scan", "news",
    # system
    "pipeline", "agents",
    # lifestyle
    "golf", "workspace",
    # specialist agents
    "medical", "legal", "fitness", "coach",
})


def _parse_decision(raw: str) -> dict | None:
    """
    Hardened JSON parser for LLM decision output.
    Handles: markdown fences, leading prose, bad symbols, unknown actions.
    """
    if not raw:
        return None

    text = raw.strip()

    # Strip ```json ... ``` or ``` ... ``` fences
    if text.startswith("```"):
        lines = text.splitlines()
        inner = [l for l in lines[1:] if l.strip() != "```"]
        text  = "\n".join(inner).strip()

    data: dict | None = None
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        # Fall back: extract first {...} block
        start = text.find("{")
        end   = text.rfind("}") + 1
        if 0 <= start < end:
            try:
                data = json.loads(text[start:end])
            except Exception:
                return None
        else:
            return None

    if not isinstance(data, dict):
        return None

    action = (data.get("action") or "none").lower().strip()
    if action not in _VALID_ACTIONS:
        action = "none"

    # Validate symbol: alphanumeric-ish, max 10 chars, not the string "null"/"none"
    raw_sym = data.get("symbol")
    symbol: str | None = None
    if raw_sym and str(raw_sym).strip().lower() not in ("null", "none", ""):
        sym   = str(raw_sym).upper().strip().strip("\"'")
        clean = sym.replace("=", "").replace("^", "").replace("-", "").replace(".", "")
        if clean.isalnum() and 1 <= len(sym) <= 10:
            symbol = sym

    return {
        "action": action,
        "symbol": symbol,
        "reason": str(data.get("reason") or "")[:200].strip(),
        "reply":  str(data.get("reply")  or "")[:800].strip(),
    }


# ================================================================
# KEYWORD FALLBACK — intent detection + dispatch (Tier 2 only)
# ================================================================
_KNOWN_SYMBOLS = {
    "NVDA", "AAPL", "MSFT", "AMZN", "META", "TSLA", "PLTR", "COIN",
    "SMCI", "XOM", "CVX", "BTC", "ETH", "SPY", "QQQ", "GOOGL", "AMD",
    "NFLX", "GOOG", "UBER", "SBUX", "DIS", "BA", "GLD", "SLV",
}

_SYMBOL_ALIASES: dict[str, str] = {
    "tesla": "TSLA", "apple": "AAPL", "microsoft": "MSFT",
    "amazon": "AMZN", "google": "GOOGL", "alphabet": "GOOGL",
    "nvidia": "NVDA", "meta": "META", "netflix": "NFLX",
    "bitcoin": "BTC", "btc": "BTC", "ethereum": "ETH", "eth": "ETH",
    "palantir": "PLTR", "coinbase": "COIN", "uber": "UBER",
    "disney": "DIS", "boeing": "BA", "exxon": "XOM",
    "amd": "AMD", "starbucks": "SBUX", "gold": "GLD",
}


def _detect_intent(message: str) -> str:
    """
    Keyword-based intent detection — Tier 2 fallback only.
    Ordered most-specific → least-specific to prevent false matches.
    """
    low = message.lower()

    # Golf first — "golf hoy" contains "hoy" which is also a workspace trigger
    if any(w in low for w in ["golf", "cancha", "hoyo", "swing", "campo de golf"]):
        return "golf"

    # Specialist agents
    if any(w in low for w in [
        "médico", "medico", "doctor", "salud", "síntoma", "sintoma",
        "fiebre", "dolor", "enferm", "symptom", "health", "longevidad",
        "fever", "pain", "sick", "ill", "malestar", "no me siento",
    ]):
        return "medical"

    if any(w in low for w in [
        "legal", "abogado", "contrato", "ley ", "demanda", "derecho",
        "contrato", "lawyer", "compliance", "jurídico", "juridico",
        "impuesto", "tribut", "dian",
    ]):
        return "legal"

    if any(w in low for w in [
        "fitness", "ejercicio", "entrenamiento", "gym", "deporte",
        "nutrición", "nutricion", "proteína", "proteina",
        "perder peso", "bajar de peso", "training", "muscle",
        "físico", "fisico", "músculo", "musculo", "entrenar",
        "cuerpo", "shape", "bajar grasa", "grasa",
    ]):
        return "fitness"

    if any(w in low for w in [
        "coach", "actúa como", "actua como", "mentor", "estrategia personal",
        "ayúdame a decidir", "ayudame a decidir", "consejo de vida",
    ]):
        return "coach"

    # Finance / market — specific asset queries
    if any(w in low for w in [
        "analiz", "analyze", "trade", "setup", "entry", "chart",
        "signal", "precio de", "price of", "cuánto cuesta", "cuanto cuesta",
        "cuánto vale", "cuanto vale", "valor de", "cotiza",
        "buy", "sell", "comprar", "vender", "debería comprar", "deberia comprar",
    ]):
        return "analyze"

    if any(w in low for w in [
        "oportunidad", "oportunidades", "recommend", "recomend",
        "mejores", "top pick", "scan", "qué comprar", "que comprar",
    ]):
        return "recommend"

    if any(w in low for w in [
        "news", "noticias", "headline", "latest", "que paso", "qué paso",
        "what happened", "mercado", "bolsa", "pasando", "pasó",
    ]):
        return "news"

    # System
    if any(w in low for w in [
        "pipeline", "qué hace el sistema", "que hace el sistema",
        "estado del sistema", "proceso", "corriendo",
    ]):
        return "pipeline"

    if any(w in low for w in [
        "agentes", "agents", "qué agentes", "que agentes",
        "activos", "agent status", "workers",
    ]):
        return "agents"

    if any(w in low for w in [
        "agenda", "tengo", "mis tareas", "tarea", "task",
        "meeting", "reunión", "reuniones", "workspace", "schedule",
    ]):
        return "workspace"

    return "general"


def _extract_symbol(message: str) -> str | None:
    for word in message.upper().split():
        clean = word.strip(".,!?;:()")
        if clean in _KNOWN_SYMBOLS:
            return clean
    for word in message.lower().split():
        clean = word.strip(".,!?;:()")
        if clean in _SYMBOL_ALIASES:
            return _SYMBOL_ALIASES[clean]
    return None


def _dispatch_tool(intent: str, message: str) -> dict | None:
    """Execute the tool for a keyword intent. Returns None on any failure."""
    try:
        if intent == "analyze":
            sym = _extract_symbol(message)
            if sym:
                return brain.trader(sym)
        elif intent in ("recommend", "scan"):
            return brain_pro.auto_scan()
        elif intent == "news":
            return {"items": news_engine.fetch_categorized(max_per_category=4)}
        elif intent == "pipeline":
            return orchestrator.pipeline_state()
        elif intent == "agents":
            return {"items": orchestrator.agent_status_snapshot()}
        elif intent == "golf":
            return golf_engine.dashboard_summary(max_courses=4)
        elif intent == "workspace":
            return workspace.home("Juan Camilo")
        elif intent == "medical":
            return orchestrator.execute(message, "medical")
        elif intent == "legal":
            return orchestrator.execute(message, "legal")
        elif intent == "fitness":
            return orchestrator.execute(message, "fitness")
        elif intent == "coach":
            return orchestrator.execute(message, "coach")
    except Exception:
        pass
    return None


# ================================================================
# PROMPTS
# ================================================================

_DECISION_PROMPT = """\
You are the JARVIS routing engine for Juan Camilo Montenegro.
Your only job: read the user message and decide which tool (if any) to call.

Available tools:
  analyze   → analyze_asset(symbol)   — technical signal analysis for a specific stock or crypto (NVDA, BTC, AAPL…)
  scan      → market_scan()           — full market intelligence: top setups, macro regime, best opportunities
  news      → get_news()              — latest financial and market headlines
  pipeline  → get_pipeline()          — current JARVIS system state: stage, progress, what is running
  agents    → get_agents()            — status snapshot of all AI agents in JARVIS
  golf      → golf_dashboard()        — golf course conditions, weather, player stats and insights
  workspace → workspace_home()        — today's tasks, meetings, agenda, and priorities
  medical   → medical_agent()         — health questions, symptoms, triage, medical and longevity advice
  legal     → legal_agent()           — legal questions, contracts, compliance, Colombian law and taxes
  fitness   → fitness_agent()         — fitness plans, training, nutrition, body performance
  coach     → council_agent()         — strategic coaching, life decisions, multi-perspective council advice

Routing rules:
- "analyze"   → user asks about a specific asset: ticker (NVDA, BTC, TSLA) OR company name (Tesla→TSLA, Apple→AAPL, Bitcoin→BTC, Nvidia→NVDA, Amazon→AMZN). Always resolve company name to ticker in the "symbol" field.
- "scan"      → "oportunidades", "mejores acciones", "qué comprar", "recomiéndame", "market overview", "setups"
- "news"      → "noticias", "qué está pasando", "mercado", "headlines", "what's happening", "bolsa hoy"
- "pipeline"  → "qué hace el sistema", "estado del sistema", "qué está corriendo", "pipeline"
- "agents"    → "agentes", "qué agentes", "activos", "agent status", "workers"
- "golf"      → "golf", "cancha", "hoyo", "swing", "campo", "golf hoy"
- "workspace" → "qué tengo hoy", "agenda", "mis tareas", "reuniones", "meetings", "schedule"
- "medical"   → health symptoms, "médico", "doctor", "dolor", "salud", "fiebre", medical advice, longevity
- "legal"     → "legal", "abogado", "contrato", "ley", "demanda", compliance, taxes, "impuesto"
- "fitness"   → "ejercicio", "entrenamiento", "gym", "nutrición", fitness, training, "perder peso"
- "coach"     → "actúa como coach", strategic advice, "ayúdame a decidir", life decisions, personal strategy
- "none"      → greetings, general questions, opinions, philosophy, definitions, anything else

Critical: Respond ONLY with valid JSON — no markdown, no explanation, no extra text.

{
  "action": "none | analyze | scan | news | pipeline | agents | golf | workspace | medical | legal | fitness | coach",
  "symbol": "UPPERCASE_TICKER or null",
  "reason": "one sentence",
  "reply":  "natural answer in user language — fill ONLY when action is none, else empty string"
}\
"""

_SYNTHESIS_PROMPT = """\
You are JARVIS — the AI operating system for Juan Camilo Montenegro, a Colombian investor, entrepreneur, and high-performer.
A real-time specialist agent just ran. Its output is injected below.
Your job: synthesise that data into a sharp, expert-level, actionable answer.

Style rules:
- Maximum 4 sentences unless the user asked for more detail
- Lead with the most important finding — number, score, or key signal first
- Short, punchy sentences. Natural rhythm. Sounds like a sharp advisor, not a report
- Respond in the exact same language the user wrote in (Spanish if they wrote Spanish)
- Medical/legal: one-line disclaimer at the end
- Never fabricate — if data is sparse, say exactly what you know and stop
- If [Memory] is provided: personalise naturally — reference past context without quoting verbatim
- If [User Profile] is provided: adapt tone and depth to their domain expertise
- If [Secondary Context] is provided: make ONE cross-domain connection where genuinely useful

Cross-domain intelligence:
- Medical + Fitness: connect symptom to recovery or performance implication
- Legal + Strategy: legal risk has strategic consequences — name them
- Finance + Risk: any trade setup should note the macro risk environment
- Never force a cross-domain connection — only when it adds real value\
"""

_FALLBACK_PROMPT = """\
You are JARVIS, an AI operating system for Juan Camilo Montenegro.
You have access to real-time system context injected below.
Be concise (2–3 sentences), direct, and actionable.
Respond in the user's language. Use exact numbers from context. Never fabricate.\
"""


# ================================================================
# DEGRADED REPLY — when synthesis LLM fails but tool already ran
# ================================================================
def _degrade_reply(action: str, symbol: str | None, tool: dict) -> str:
    # Orchestrator-wrapped results (medical/legal/fitness/coach)
    if action in ("medical", "legal", "fitness", "coach"):
        inner = tool.get("result") or {}

        if action == "medical":
            triage = inner.get("triage", "")
            recs   = inner.get("recommendation", [])
            if triage and recs:
                return f"Triage: {triage}. {recs[0]}"
            return recs[0] if recs else "Consulta médica iniciada. Visita un médico licenciado."

        if action == "legal":
            domain  = inner.get("domain", "legal")
            sources = inner.get("official_sources", [])
            src     = sources[0].get("name", "") if sources else ""
            return (f"Dominio legal: {domain}. Fuente oficial: {src}."
                    if src else f"Consulta legal clasificada como {domain}. Verificar con fuente oficial.")

        if action == "fitness":
            recs = inner.get("recommendations", [])
            plan = inner.get("weekly_plan", [])
            if recs:
                return recs[0]
            return ("Plan semanal: " + ", ".join(plan[:3])) if plan else "Plan de fitness generado."

        if action == "coach":
            consensus = inner.get("consensus", "")
            steps     = inner.get("recommended_next_steps", [])
            if consensus:
                return consensus + (" Primer paso: " + steps[0] if steps else "")
            return "Council consultado. Revisa los próximos pasos recomendados."

    # Direct tool results
    if action == "scan":
        summary = tool.get("summary", "")
        acts    = tool.get("actions", [])
        return (summary + " — " + acts[0]) if acts else summary

    if action == "analyze":
        score = tool.get("setup_score") or tool.get("score", "")
        sym   = symbol or tool.get("symbol", "")
        return f"Setup score for {sym}: {score}/100." if score else ""

    if action == "pipeline":
        stage = tool.get("stage", "UNKNOWN")
        prog  = int(tool.get("progress", 0) * 100)
        msg   = tool.get("message", "")
        return f"Pipeline: {stage} at {prog}%. {msg}".strip()

    if action == "agents":
        items  = tool.get("items", [])
        active = [i.get("name", "") for i in items if i.get("status") == "active"]
        return (f"{len(active)} agent(s) active: {', '.join(active[:4])}."
                if active else f"{len(items)} agents registered in JARVIS.")

    if action == "workspace":
        tasks    = tool.get("tasks", [])
        meetings = tool.get("meetings", [])
        return f"Tienes {len(tasks)} tarea(s) y {len(meetings)} reunión(es) hoy."

    if action == "golf":
        insights = tool.get("insights", [])
        return insights[0] if insights else "Datos de golf disponibles."

    if action == "news":
        items  = tool.get("items", [])
        titles = [i.get("title", "") for i in items[:2] if i.get("title")]
        return ("Últimas noticias: " + " | ".join(titles)) if titles else ""

    return ""


# ================================================================
# AGENT CHAT — Tier 1: two-pass autonomous agent
# Pass 1: LLM decides tool → Pass 2: LLM synthesises with data
# ================================================================
def _agent_chat(message: str) -> dict | None:
    # Memory recall shortcut — bypass LLM routing for explicit recall queries
    msg_low = message.lower()
    if any(t in msg_low for t in _RECALL_TRIGGERS):
        return _handle_recall_query(message)

    context = _get_context()
    mem_ctx = _mem().as_context_string(message)

    # ── PASS 1: routing decision ──────────────────────────────
    decision_system = _DECISION_PROMPT
    if context:
        decision_system += f"\n\n[Live System Context]\n{context}"

    decision_messages = [
        {"role": "system", "content": decision_system},
        *list(_chat_history),
        {"role": "user", "content": message},
    ]

    raw      = generate_response(decision_messages, json_mode=True)
    decision = _parse_decision(raw or "")
    if not decision:
        return None

    action       = decision["action"]
    symbol       = decision["symbol"]
    direct_reply = decision["reply"]

    # No tool needed → return direct LLM answer immediately
    if action == "none":
        if not direct_reply:
            return None
        _push_history("user", message)
        _push_history("assistant", direct_reply)
        return {
            "type":       "llm_agent",
            "reply":      direct_reply,
            "summary":    direct_reply[:120] + ("..." if len(direct_reply) > 120 else ""),
            "details":    {},
            "action":     "",
            "confidence": 0.75,
            "source":     "llm_agent",
        }

    # ── TOOL EXECUTION ────────────────────────────────────────
    tool_result: dict | None = None
    _COLLABORATED = {"medical", "fitness", "legal", "coach"}

    try:
        if action == "analyze":
            sym = symbol or _extract_symbol(message)
            if sym:
                tool_result = brain.trader(sym)
        elif action == "scan":
            tool_result = brain_pro.auto_scan()
        elif action == "news":
            tool_result = {"items": news_engine.fetch_categorized(max_per_category=4)}
        elif action == "pipeline":
            tool_result = orchestrator.pipeline_state()
        elif action == "agents":
            tool_result = {"items": orchestrator.agent_status_snapshot()}
        elif action == "golf":
            tool_result = golf_engine.dashboard_summary(max_courses=4)
        elif action == "workspace":
            tool_result = workspace.home("Juan Camilo")
        elif action in _COLLABORATED:
            # Use collaborated execute for cross-domain depth
            tool_result = orchestrator.execute_collaborated(
                message, _action_to_domain(action)
            )
    except Exception:
        pass

    # ── PASS 2: synthesis ─────────────────────────────────────
    feedback = _detect_feedback_signal(message)
    profile  = _build_user_profile(message)

    synthesis_system = _SYNTHESIS_PROMPT
    if context:
        synthesis_system += f"\n\n[Live System Context]\n{context}"
    if profile:
        synthesis_system += f"\n\n[User Profile]\n{profile}"
    if mem_ctx:
        synthesis_system += f"\n\n[Memory]\n{mem_ctx}"
    if feedback == "repeat":
        synthesis_system += "\n\n[Feedback signal: user is re-asking — previous answer missed the mark. Be more specific, direct, and concrete this time.]"
    elif feedback == "expand":
        synthesis_system += "\n\n[Feedback signal: user wants more depth — expand key points with specifics.]"
    if tool_result:
        # Extract secondary context if present (from collaborate execution)
        sec = tool_result.pop("secondary_context", None) if isinstance(tool_result, dict) else None
        snippet = json.dumps(tool_result, default=str)[:1400]
        synthesis_system += f"\n\n[Tool: {action}]\n{snippet}"
        if sec:
            sec_snippet = json.dumps(sec.get("result", {}), default=str)[:600]
            synthesis_system += f"\n\n[Secondary Context — {sec.get('domain', '')}]\n{sec_snippet}"

    synthesis_messages = [
        {"role": "system", "content": synthesis_system},
        *list(_chat_history),
        {"role": "user", "content": message},
    ]

    final_reply = generate_response(synthesis_messages, json_mode=False)

    # Synthesis failed but tool ran → produce minimal degraded reply
    if not final_reply and tool_result:
        final_reply = _degrade_reply(action, symbol, tool_result)

    if not final_reply:
        return None

    _push_history("user", message)
    _push_history("assistant", final_reply)
    _push_memory(message, final_reply, agent=action, domain=_action_to_domain(action))

    action_tag = f"{action}:{symbol}" if (action == "analyze" and symbol) else action
    confidence = 0.92 if tool_result else 0.78

    return {
        "type":       "llm_agent",
        "reply":      final_reply,
        "summary":    final_reply[:120] + ("..." if len(final_reply) > 120 else ""),
        "details":    tool_result or {},
        "action":     action_tag,
        "confidence": confidence,
        "source":     "llm_agent",
    }


# ================================================================
# KEYWORD CHAT — Tier 2: keyword intent → tool → single LLM pass
# Only reached when _agent_chat returns None.
# ================================================================
def _llm_chat(message: str) -> dict | None:
    intent      = _detect_intent(message)
    tool_result = _dispatch_tool(intent, message)
    context     = _get_context()
    mem_ctx     = _mem().as_context_string(message)

    system_content = _FALLBACK_PROMPT
    if context:
        system_content += f"\n\n[Live System Context]\n{context}"
    if mem_ctx:
        system_content += f"\n\n[Memory]\n{mem_ctx}"
    if tool_result:
        snippet = json.dumps(tool_result, default=str)[:1400]
        system_content += f"\n\n[Tool Result — {intent}]\n{snippet}"

    messages = [{"role": "system", "content": system_content}]
    messages.extend(list(_chat_history))
    messages.append({"role": "user", "content": message})

    reply = generate_response(messages)
    if not reply:
        if tool_result:
            sym   = _extract_symbol(message)
            reply = _degrade_reply(intent, sym, tool_result)
        if not reply:
            return None

    _push_history("user", message)
    _push_history("assistant", reply)
    _push_memory(message, reply, agent=intent, domain=intent)

    sym = _extract_symbol(message)
    action_map = {
        "analyze":   f"analyze:{sym}" if sym else "analyze",
        "recommend": "scan",
        "scan":      "scan",
        "news":      "news",
        "pipeline":  "pipeline",
        "agents":    "agents",
        "golf":      "golf",
        "workspace": "workspace",
        "medical":   "medical",
        "legal":     "legal",
        "fitness":   "fitness",
        "coach":     "coach",
    }
    action_tag = action_map.get(intent, "")

    return {
        "type":       "llm_chat",
        "reply":      reply,
        "summary":    reply[:120] + ("..." if len(reply) > 120 else ""),
        "details":    tool_result or {},
        "action":     action_tag,
        "confidence": 0.88 if tool_result else 0.68,
        "source":     "llm_fallback",
    }


# ================================================================
# PYDANTIC MODELS
# ================================================================
class ChatRequest(BaseModel):
    message: str
    domain: str | None = "general"


# ================================================================
# ROUTES — unchanged
# ================================================================
@app.get("/")
def root():
    return {"status": "JARVIS RUNNING"}


@app.get("/health")
def health():
    return {"status": "ok", "brain": brain.health()}


@app.get("/dashboard")
def dashboard():
    if DASHBOARD_HTML.exists():
        return FileResponse(DASHBOARD_HTML)
    raise HTTPException(status_code=404, detail="Dashboard not found")


# =========================
# HOME
# =========================
@app.get("/dashboard/home")
def dashboard_home(current_user: dict = Depends(get_optional_user)):
    uid = current_user["user_id"]
    try:
        return _ws(uid).home(_user_name(uid))
    except Exception:
        return {
            "greeting":     "JARVIS ready",
            "date":         datetime.now().strftime("%A %d %B %Y"),
            "owner_name":   _user_name(uid),
            "top_priority": "Protect capital",
            "tasks_open":   0,
            "assets_count": 0,
            "next_meeting": None,
            "tasks":        [],
            "meetings":     [],
        }


# =========================
# CHAT — 3-tier fallback chain
# Tier 1: _agent_chat  (LLM decides tool autonomously, two-pass)
# Tier 2: _llm_chat    (keyword intent → tool → single LLM pass)
# Tier 3: brain.chat() (deterministic ProductBrain, no LLM)
# =========================
@app.post("/chat")
def chat(req: ChatRequest):
    try:
        result = _agent_chat(req.message)

        if result is None:
            result = _llm_chat(req.message)

        if result is None:
            result = brain.chat(req.message)

        return JSONResponse(
            content={
                "status":     "ok",
                "response":   result,
                "reply":      result.get("reply", ""),
                "summary":    result.get("summary", ""),
                "type":       result.get("type", "chat"),
                "details":    result.get("details", {}),
                "action":     result.get("action", ""),
                "confidence": result.get("confidence", 0.0),
                "source":     result.get("source", "brain"),
            },
            media_type="application/json; charset=utf-8",
        )

    except Exception as e:
        return JSONResponse(
            content={
                "status": "error",
                "response": {
                    "type":       "error",
                    "reply":      f"Error en chat: {e}",
                    "summary":    f"Error en chat: {e}",
                    "details":    {},
                    "action":     "",
                    "confidence": 0.1,
                    "source":     "main_chat_handler",
                },
            },
            media_type="application/json; charset=utf-8",
        )


# =========================
# AUTO JARVIS
# =========================
@app.post("/jarvis/auto")
def jarvis_auto():
    try:
        result     = brain_pro.auto_scan()
        summary    = result.get("summary", "")
        actions    = result.get("actions", [])
        confidence = result.get("confidence", 0.0)
        meta       = result.get("meta", {})
        generated  = result.get("generated_at", datetime.utcnow().isoformat())

        reply = summary
        if actions:
            reply += " Top actions: " + " | ".join(actions[:3])

        return {
            "reply":        reply or "No high-conviction setups detected right now.",
            "summary":      summary,
            "actions":      actions,
            "confidence":   confidence,
            "meta":         meta,
            "generated_at": generated,
        }

    except Exception as e:
        return {
            "reply":        f"Auto JARVIS error: {e}",
            "summary":      "",
            "actions":      [],
            "confidence":   0.0,
            "meta":         {},
            "generated_at": datetime.utcnow().isoformat(),
        }


# =========================
# TRADER
# =========================
@app.post("/dashboard/trader")
def trader(data: dict):
    try:
        symbol = data.get("symbol", "AAPL")
        return brain.trader(symbol)
    except Exception as e:
        return {"error": str(e)}


# =========================
# RECOMMENDATIONS
# =========================
@app.get("/dashboard/recommendations")
def recommendations():
    try:
        return brain.recommendations()
    except Exception as e:
        return {"items": [], "error": str(e)}


# =========================
# TASKS
# =========================
@app.post("/dashboard/tasks")
def add_task(data: dict, current_user: dict = Depends(get_optional_user)):
    uid = current_user["user_id"]
    try:
        text     = (data.get("text") or "").strip()
        priority = (data.get("priority") or "medium").strip().lower()
        day      = (data.get("day") or "today").strip().lower()
        category = (data.get("category") or "general").strip().lower()
        if not text:
            raise HTTPException(status_code=400, detail="text is required")
        if priority not in ["high", "medium", "low"]:
            priority = "medium"
        return _ws(uid).add_task(text, priority, day, category)
    except HTTPException:
        raise
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@app.post("/dashboard/tasks/{task_id}/toggle")
def toggle_task(task_id: str, current_user: dict = Depends(get_optional_user)):
    uid = current_user["user_id"]
    try:
        return _ws(uid).toggle_task(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.delete("/dashboard/tasks/{task_id}")
def delete_daily_task(task_id: str, current_user: dict = Depends(get_optional_user)):
    uid = current_user["user_id"]
    try:
        return _ws(uid).delete_task(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.patch("/dashboard/tasks/{task_id}")
def edit_task(task_id: str, data: dict, current_user: dict = Depends(get_optional_user)):
    uid = current_user["user_id"]
    try:
        return _ws(uid).edit_task(task_id, data)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# =========================
# MEETINGS
# =========================
@app.post("/dashboard/meetings")
def add_meeting(data: dict, current_user: dict = Depends(get_optional_user)):
    uid = current_user["user_id"]
    try:
        title      = (data.get("title") or "").strip()
        time_value = (data.get("time") or "").strip()
        notes      = (data.get("notes") or "").strip()
        if not title or not time_value:
            raise HTTPException(status_code=400, detail="title and time are required")
        return _me(uid).add_meeting(title, time_value, notes)
    except HTTPException:
        raise
    except Exception as e:
        return {"status": "error", "detail": str(e)}


# =========================
# SCHEDULE MEETING
# =========================
@app.post("/dashboard/schedule-meeting")
def schedule_meeting(data: dict, current_user: dict = Depends(get_optional_user)):
    uid = current_user["user_id"]
    try:
        objective      = (data.get("objective") or "").strip()
        datetime_value = (data.get("datetime") or "").strip()
        if not objective or not datetime_value:
            raise HTTPException(status_code=400, detail="objective and datetime are required")
        meeting = _me(uid).add_meeting_datetime(
            title=objective,
            datetime_value=datetime_value,
            notes="Scheduled via dashboard",
        )
        return {"status": "ok", "meeting_created": meeting}
    except HTTPException:
        raise
    except Exception as e:
        return {"status": "error", "detail": str(e)}


# =========================
# ASSETS
# =========================
@app.get("/dashboard/assets")
def assets():
    try:
        return workspace.list_assets()
    except Exception:
        return {"assets": []}


@app.post("/dashboard/upload")
async def upload_asset(file: UploadFile = File(...)):
    try:
        filename    = (file.filename or "asset.bin").replace("/", "_").replace("\\", "_")
        output_path = UPLOADS_DIR / filename

        with output_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        item = workspace.register_asset(
            filename=filename,
            stored_path=str(output_path),
            mime_type=file.content_type,
            size_bytes=output_path.stat().st_size,
        )
        return {"status": "ok", "asset": item}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@app.get("/dashboard/uploads/{filename:path}")
def serve_upload(filename: str):
    path = UPLOADS_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="file not found")
    return FileResponse(path)


# =========================
# SYSTEM METRICS
# =========================
@app.get("/dashboard/system")
def system_metrics():
    try:
        perf_stats = orchestrator.agent_performance_stats()
        mem_stats  = _mem().stats()

        # Intelligence level from avg reputation across active agents
        rep_values = list(orchestrator.agent_reputation.values())
        avg_rep    = round(sum(rep_values) / len(rep_values), 3) if rep_values else 0.80

        # Derive overall system health
        total_calls = sum(p.get("calls", 0) for p in perf_stats)
        total_errors = sum(
            round(p.get("error_rate", 0) * p.get("calls", 0))
            for p in perf_stats
        )
        error_rate_pct = round(total_errors / total_calls * 100, 1) if total_calls else 0

        intelligence_level = (
            "elite"    if avg_rep >= 0.90 else
            "advanced" if avg_rep >= 0.85 else
            "solid"    if avg_rep >= 0.80 else
            "learning"
        )

        # Last 3 decisions from memory
        recent_mem = _mem().last_n(3)
        last_decisions = [
            {"domain": m.get("domain", ""), "summary": m.get("user", "")[:60], "ts": m.get("ts", "")[:10]}
            for m in reversed(recent_mem)
        ]

        return {
            "signals":           total_calls,
            "accuracy":          f"{round((1 - error_rate_pct/100) * 100, 1)}%",
            "risk":              "medium",
            "exposure":          "45%",
            "intelligence_level": intelligence_level,
            "avg_agent_reputation": avg_rep,
            "memory_entries":    mem_stats.get("total_entries", 0),
            "memory_vector_ready": mem_stats.get("vector_ready", False),
            "memory_domains":    mem_stats.get("domains", []),
            "agent_calls_total": total_calls,
            "agent_error_rate":  f"{error_rate_pct}%",
            "last_decisions":    last_decisions,
            "top_agents":        perf_stats[:3],
        }
    except Exception as e:
        return {
            "signals":  0,
            "accuracy": "N/A",
            "risk":     "medium",
            "exposure": "45%",
            "error":    str(e),
        }


# =========================
# PIPELINE
# =========================
@app.get("/dashboard/pipeline")
def pipeline():
    try:
        return orchestrator.pipeline_state()
    except Exception:
        return {
            "stage":        "SCAN",
            "progress":     0.05,
            "active_agent": "market_intelligence",
            "message":      "Pipeline state unavailable",
        }


# =========================
# AGENTS
# =========================
@app.get("/dashboard/agents")
def agents():
    try:
        items = orchestrator.agent_status_snapshot()
        return {"items": items}
    except Exception as e:
        return {"items": [], "error": str(e)}


# =========================
# NEWS FEED
# =========================
@app.get("/dashboard/news")
def news():
    try:
        items = news_engine.fetch_categorized(max_per_category=5)
        return {"items": items}
    except Exception as e:
        return {"items": [], "error": str(e)}


# =========================
# GOLF
# =========================
@app.get("/dashboard/golf")
def golf():
    try:
        return golf_engine.dashboard_summary(max_courses=6)
    except Exception as e:
        return {
            "courses":      [],
            "insights":     ["Golf data temporarily unavailable."],
            "player":       {},
            "generated_at": datetime.now().isoformat(),
            "error":        str(e),
        }


# =========================
# MARKET SNAPSHOT
# =========================
@app.get("/api/markets/snapshot")
def markets_snapshot():
    if not _MKT_AVAILABLE or _mkt_engine is None:
        return {"status": "unavailable", "items": [], "regime": "unknown", "timestamp": datetime.now().isoformat()}
    try:
        data = _mkt_engine.snapshot()
        items = data.get("items", [])
        vix_item = next((x for x in items if x["label"] == "VIX"), None)
        spy_item = next((x for x in items if x["label"] == "SPY"), None)

        vix = vix_item["price"] if vix_item else None
        spy_chg = spy_item["change_pct"] if spy_item else None

        if vix is None:
            regime = "unknown"
        elif vix > 35:
            regime = "FEAR"
        elif vix > 25 and spy_chg is not None and spy_chg < 0:
            regime = "RISK_OFF"
        elif vix > 20:
            regime = "CAUTION"
        else:
            regime = "NORMAL"

        return {
            "status": "ok",
            "items": items,
            "regime": regime,
            "vix": vix,
            "timestamp": data.get("timestamp", datetime.now().isoformat()),
        }
    except Exception as e:
        return {"status": "error", "items": [], "regime": "unknown", "error": str(e), "timestamp": datetime.now().isoformat()}


# =========================
# GOLF API
# =========================
@app.get("/api/golf/courses")
def golf_courses_search(q: str = "", limit: int = 10):
    try:
        if not q.strip():
            items = golf_engine.db.get_all_courses()[:limit]
        else:
            items = golf_engine.search_courses(q.strip(), limit=limit)
        return {"status": "ok", "query": q, "items": items, "count": len(items)}
    except Exception as e:
        return {"status": "error", "items": [], "error": str(e)}


@app.post("/api/golf/caddy")
def golf_caddy(data: dict):
    try:
        distance = float(data.get("distance") or 150)
        wind_mph = float(data.get("wind_mph") or 0)
        wind_direction = str(data.get("wind_direction") or "neutral")
        elevation_delta = float(data.get("elevation_delta_yards") or 0)
        lie = str(data.get("lie") or "fairway")
        temperature_c = float(data.get("temperature_c") or 22)
        result = golf_engine.caddie(
            distance=distance,
            wind_mph=wind_mph,
            wind_direction=wind_direction,
            elevation_delta_yards=elevation_delta,
            lie=lie,
            temperature_c=temperature_c,
        )
        return {"status": "ok", **result}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.get("/api/golf/profile")
def golf_profile():
    try:
        return {"status": "ok", "profile": golf_engine.get_profile()}
    except Exception as e:
        return {"status": "error", "profile": {}, "error": str(e)}


@app.post("/api/golf/profile/round")
def golf_log_round(data: dict):
    try:
        score = int(data.get("score") or 0)
        course_name = str(data.get("course_name") or "Unknown course")
        notes = str(data.get("notes") or "")
        if score < 18 or score > 200:
            raise HTTPException(status_code=400, detail="score must be between 18 and 200")
        stats = golf_engine.log_round(score, course_name, notes)
        return {"status": "ok", "profile": stats}
    except HTTPException:
        raise
    except Exception as e:
        return {"status": "error", "error": str(e)}


# =========================
# AGENT PERFORMANCE STATS
# =========================
@app.get("/jarvis/agents/performance")
def agent_performance():
    try:
        return {"items": orchestrator.agent_performance_stats()}
    except Exception as e:
        return {"items": [], "error": str(e)}


# =========================
# COUNCIL ENDPOINT (Phase 3B)
# =========================
class CouncilRequest(BaseModel):
    query: str
    domain: str = "general"

@app.post("/api/council")
def council_execute(req: CouncilRequest):
    """
    Multi-agent council: runs all domain agents, detects conflicts,
    returns confidence-weighted synthesis with full traceability.
    """
    try:
        return orchestrator.execute_council(req.query, req.domain)
    except Exception as e:
        return {
            "query":   req.query,
            "domain":  req.domain,
            "council": {"council_action": "Council failed", "weighted_confidence": 0.0},
            "error":   str(e),
        }


# =========================
# MEMORY STATS
# =========================
@app.get("/jarvis/memory/stats")
def memory_stats():
    try:
        return _mem().stats()
    except Exception as e:
        return {"total_entries": 0, "vector_ready": False, "error": str(e)}


# ================================================================
# VOICE API
# ================================================================
class VoiceSpeakRequest(BaseModel):
    text: str
    priority: str = "normal"
    interrupt: bool = False


@app.get("/api/voice/status")
def voice_status():
    return get_voice_service().status()


@app.post("/api/voice/speak")
def voice_speak(req: VoiceSpeakRequest):
    svc = get_voice_service()
    if not svc.configured:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "reason": "ELEVENLABS_API_KEY not configured", "fallback": True},
        )
    audio = svc.speak(req.text)
    if audio is None:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "reason": "TTS generation failed — check API key and quota", "fallback": True},
        )
    return Response(content=audio, media_type="audio/mpeg")


# ── Phase 5J: Voice Engine endpoints ─────────────────────────────────

class _VoiceCommandRequest(BaseModel):
    transcript: str
    source: str = "mic"          # "mic" | "whisper" | "text"
    speak_response: bool = False  # if True, return audio/mpeg instead of JSON

class _VoiceSettingsUpdate(BaseModel):
    language:          Optional[str]  = None
    auto_speak:        Optional[bool] = None
    speed:             Optional[float]= None
    wake_word_enabled: Optional[bool] = None
    wake_word:         Optional[str]  = None
    use_whisper:       Optional[bool] = None
    voice_id:          Optional[str]  = None


@app.post("/api/voice/transcribe")
async def voice_transcribe(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_optional_user),
):
    """Accept a WebM/WAV/MP4 audio blob and return Whisper transcript."""
    llm = _get_llm()
    if llm is None:
        raise HTTPException(503, "OPENAI_API_KEY not configured — Whisper unavailable")
    try:
        audio_bytes = await file.read()
        import io
        audio_file  = io.BytesIO(audio_bytes)
        audio_file.name = file.filename or "audio.webm"
        transcript = llm.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
        )
        text = transcript.text.strip()
        return {"status": "ok", "transcript": text, "language": "auto"}
    except Exception as e:
        raise HTTPException(500, f"Whisper transcription failed: {e}")


@app.post("/api/voice/command")
def voice_command(
    req: _VoiceCommandRequest,
    current_user: dict = Depends(get_optional_user),
):
    """Route a voice transcript through the AI orchestrator, log it, optionally TTS."""
    uid = current_user["user_id"]
    ve  = _voice_engine(uid)

    # Route through orchestrator
    ctx  = _build_orchestrator_context(uid)
    result = ai_orchestrator.route(req.transcript, ctx)
    response_text = result.get("response", "")
    domain        = result.get("domain", "general")

    # Log to voice history
    ve.log_command(
        transcript = req.transcript,
        response   = response_text,
        domain     = domain,
        source     = req.source,
    )

    # Optionally return TTS audio
    if req.speak_response:
        svc = get_voice_service()
        if svc.configured:
            audio = svc.speak(response_text)
            if audio:
                return Response(content=audio, media_type="audio/mpeg")

    return {
        "status":   "ok",
        "domain":   domain,
        "response": response_text,
        "agent":    result.get("agent", ""),
        "data":     result.get("data", {}),
    }


@app.get("/api/voice/settings")
def voice_settings_get(current_user: dict = Depends(get_optional_user)):
    uid = current_user["user_id"]
    return {"status": "ok", "settings": _voice_engine(uid).get_settings()}


@app.put("/api/voice/settings")
def voice_settings_update(
    body: _VoiceSettingsUpdate,
    current_user: dict = Depends(get_optional_user),
):
    uid     = current_user["user_id"]
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    updated = _voice_engine(uid).update_settings(updates)
    return {"status": "ok", "settings": updated}


@app.get("/api/voice/history")
def voice_history(
    limit:  int = 20,
    offset: int = 0,
    domain: str = "",
    source: str = "",
    current_user: dict = Depends(get_optional_user),
):
    uid = current_user["user_id"]
    return {"status": "ok", **_voice_engine(uid).get_history(limit, offset, domain, source)}


# ================================================================
# QUERY API  (normalised chat endpoint for external integrations)
# ================================================================
class QueryRequest(BaseModel):
    message: str
    domain: str = "auto"
    user_id: str = "owner"


@app.post("/api/query")
def api_query(req: QueryRequest):
    try:
        result = _agent_chat(req.message)
        if result is None:
            result = _llm_chat(req.message)
        if result is None:
            result = brain.chat(req.message)
        reply = result.get("reply", "") or result.get("summary", "")
        return {
            "status":     "ok",
            "reply":      reply,
            "agent":      result.get("action", ""),
            "confidence": result.get("confidence", 0.0),
            "risk_level": result.get("details", {}).get("risk_level", "medium"),
            "action":     result.get("action", ""),
            "data":       result.get("details", {}),
        }
    except Exception as e:
        return {"status": "error", "reply": str(e), "agent": "", "confidence": 0.0,
                "risk_level": "medium", "action": "", "data": {}}


# ================================================================
# NEWS API
# ================================================================
@app.get("/api/news/feed")
def news_feed(limit: int = 40):
    try:
        items = live_news.fetch(limit_per_source=max(1, limit // len(live_news.SOURCES)))
        return {"status": "ok", "items": items, "count": len(items)}
    except Exception as e:
        return {"status": "error", "items": [], "error": str(e)}


@app.get("/api/news/item")
def news_item(id: str = ""):
    try:
        all_items = live_news.fetch(limit_per_source=8)
        item = next((i for i in all_items if i.get("id") == id), None)
        if not item:
            raise HTTPException(status_code=404, detail="News item not found")
        return {"status": "ok", "item": item}
    except HTTPException:
        raise
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.post("/api/news/analyze")
def news_analyze(data: dict):
    try:
        title   = str(data.get("title", "")).strip()
        summary = str(data.get("summary", "")).strip()
        tickers = data.get("tickers", [])
        query   = f"News analysis: {title}. {summary}"
        if tickers:
            query += f" Tickers mentioned: {', '.join(tickers[:3])}."
        result = orchestrator.execute_council(query, "general")
        council = result.get("council", {})
        return {
            "status":     "ok",
            "insight":    council.get("council_insight", ""),
            "action":     council.get("council_action", ""),
            "confidence": council.get("weighted_confidence", 0.5),
            "agents":     council.get("agents_consulted", []),
        }
    except Exception as e:
        return {"status": "error", "insight": str(e)}


# ================================================================
# GOLF BAG API
# ================================================================
@app.get("/api/golf/bag")
def get_golf_bag(current_user: dict = Depends(get_optional_user)):
    uid = current_user["user_id"]
    try:
        return {"status": "ok", "bag": _ge(uid).get_bag()}
    except Exception as e:
        return {"status": "error", "bag": [], "error": str(e)}


@app.post("/api/golf/bag")
def save_golf_bag(data: dict, current_user: dict = Depends(get_optional_user)):
    uid = current_user["user_id"]
    try:
        clubs = data.get("clubs", [])
        if not isinstance(clubs, list):
            raise HTTPException(status_code=400, detail="clubs must be a list")
        saved = _ge(uid).save_bag(clubs)
        return {"status": "ok", "bag": saved}
    except HTTPException:
        raise
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.put("/api/golf/bag/{club_name}")
def update_club(club_name: str, data: dict, current_user: dict = Depends(get_optional_user)):
    uid = current_user["user_id"]
    try:
        result = _ge(uid).upsert_club(club_name, data)
        return {"status": "ok", "club": result}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.delete("/api/golf/bag/{club_name}")
def delete_golf_club(club_name: str, current_user: dict = Depends(get_optional_user)):
    uid = current_user["user_id"]
    try:
        removed = _ge(uid).delete_club(club_name)
        if not removed:
            raise HTTPException(status_code=404, detail=f"Club '{club_name}' not found in bag")
        return {"status": "ok", "removed": club_name}
    except HTTPException:
        raise
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.get("/api/golf/courses/all")
def golf_courses_all():
    try:
        grouped = golf_engine.get_all_courses_grouped()
        all_flat = golf_engine.db.get_all_courses()
        return {"status": "ok", "grouped": grouped, "all": all_flat, "count": len(all_flat)}
    except Exception as e:
        return {"status": "error", "grouped": {}, "all": [], "error": str(e)}


@app.get("/api/golf/courses/{course_id}")
def golf_course_detail(course_id: int):
    try:
        conn = golf_engine.db._connect()
        cur  = conn.cursor()
        cur.execute("SELECT * FROM courses WHERE id = ?", (course_id,))
        row = cur.fetchone()
        conn.close()
        if not row:
            raise HTTPException(status_code=404, detail="Course not found")
        cols = [d[0] for d in cur.description]
        course = dict(zip(cols, row))
        return {"status": "ok", "course": course}
    except HTTPException:
        raise
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ================================================================
# MEETINGS DELETE
# ================================================================
@app.delete("/api/meetings/{meeting_id}")
def delete_meeting(meeting_id: str, current_user: dict = Depends(get_optional_user)):
    uid = current_user["user_id"]
    try:
        removed = _me(uid).delete_meeting(meeting_id)
        if not removed:
            raise HTTPException(status_code=404, detail=f"Meeting '{meeting_id}' not found")
        return {"status": "ok", "removed": meeting_id}
    except HTTPException:
        raise
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ================================================================
# UPLOADS DELETE
# ================================================================
@app.delete("/api/uploads/{filename:path}")
def delete_upload(filename: str):
    try:
        safe_name = Path(filename).name   # strip any path traversal
        file_path = UPLOADS_DIR / safe_name
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        file_path.unlink()
        workspace.delete_asset_by_filename(safe_name)
        return {"status": "ok", "deleted": safe_name}
    except HTTPException:
        raise
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ================================================================
# STOCKS API
# ================================================================
@app.get("/api/stocks/{ticker}")
def stock_detail(ticker: str):
    try:
        sym = ticker.upper().strip()
        result = brain.trader(sym)
        return {"status": "ok", **result}
    except Exception as e:
        return {"status": "error", "symbol": ticker, "error": str(e)}


# ================================================================
# PROJECT PLANNER
# ================================================================
class _ProjectCreate(BaseModel):
    name: str
    description: str = ""
    color: str = "cyan"

class _TaskCreate(BaseModel):
    title: str
    description: str = ""
    status: str = "todo"
    urgency: str = "medium"
    due_date: str = ""

class _TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None
    urgency: str | None = None
    due_date: str | None = None

class _AITasksRequest(BaseModel):
    description: str

@app.get("/api/projects")
def list_projects(current_user: dict = Depends(get_optional_user)):
    uid = current_user["user_id"]
    try:
        return {"status": "ok", "projects": planner.list_projects(user_id=uid)}
    except Exception as e:
        return {"status": "error", "error": str(e)}

@app.post("/api/projects")
def create_project(body: _ProjectCreate, current_user: dict = Depends(get_optional_user)):
    uid = current_user["user_id"]
    try:
        p = planner.create_project(body.name, body.description, body.color, user_id=uid)
        return {"status": "ok", "project": p}
    except Exception as e:
        return {"status": "error", "error": str(e)}

@app.delete("/api/projects/{project_id}")
def delete_project(project_id: str, current_user: dict = Depends(get_optional_user)):
    uid = current_user["user_id"]
    try:
        ok = planner.delete_project(project_id, user_id=uid)
        if not ok:
            raise HTTPException(status_code=404, detail="Project not found")
        return {"status": "ok", "deleted": project_id}
    except HTTPException:
        raise
    except Exception as e:
        return {"status": "error", "error": str(e)}

@app.get("/api/projects/{project_id}/tasks")
def get_project_tasks(project_id: str, current_user: dict = Depends(get_optional_user)):
    uid = current_user["user_id"]
    try:
        tasks = planner.get_tasks(project_id, user_id=uid)
        return {"status": "ok", "tasks": tasks}
    except Exception as e:
        return {"status": "error", "error": str(e)}

@app.post("/api/projects/{project_id}/task")
def create_project_task(project_id: str, body: _TaskCreate, current_user: dict = Depends(get_optional_user)):
    uid = current_user["user_id"]
    try:
        t = planner.create_task(
            project_id=project_id,
            title=body.title,
            description=body.description,
            status=body.status,
            urgency=body.urgency,
            due_date=body.due_date,
            user_id=uid,
        )
        return {"status": "ok", "task": t}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        return {"status": "error", "error": str(e)}

@app.put("/api/projects/{project_id}/task/{task_id}")
def update_project_task(project_id: str, task_id: str, body: _TaskUpdate, current_user: dict = Depends(get_optional_user)):
    uid = current_user["user_id"]
    try:
        # Verify project ownership before allowing task update
        if not planner.get_project(project_id, user_id=uid):
            raise HTTPException(status_code=404, detail="Project not found")
        updates = {k: v for k, v in body.model_dump().items() if v is not None}
        t = planner.update_task(task_id, updates)
        return {"status": "ok", "task": t}
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        return {"status": "error", "error": str(e)}

@app.delete("/api/projects/{project_id}/task/{task_id}")
def delete_project_task(project_id: str, task_id: str, current_user: dict = Depends(get_optional_user)):
    uid = current_user["user_id"]
    try:
        if not planner.get_project(project_id, user_id=uid):
            raise HTTPException(status_code=404, detail="Project not found")
        ok = planner.delete_task(task_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Task not found")
        return {"status": "ok", "deleted": task_id}
    except HTTPException:
        raise
    except Exception as e:
        return {"status": "error", "error": str(e)}

@app.post("/api/projects/{project_id}/ai-tasks")
def ai_generate_tasks(project_id: str, body: _AITasksRequest, current_user: dict = Depends(get_optional_user)):
    uid = current_user["user_id"]
    try:
        proj = planner.get_project(project_id, user_id=uid)
        if not proj:
            raise HTTPException(status_code=404, detail="Project not found")
        prompt = (
            f"You are a project manager. Generate 5 actionable tasks for this project.\n"
            f"Project: {proj['name']}\n"
            f"Description: {body.description or proj.get('description','')}\n\n"
            f"Return ONLY a JSON array with objects: "
            f"{{\"title\": str, \"description\": str, \"urgency\": \"critical|high|medium|low\", \"due_date\": \"\"}}. "
            f"No markdown, no explanation."
        )
        raw = generate_response([{"role": "user", "content": prompt}], json_mode=True)
        if not raw:
            raise ValueError("LLM unavailable")
        parsed = json.loads(raw) if isinstance(raw, str) else raw
        task_defs = parsed if isinstance(parsed, list) else parsed.get("tasks", [])
        created = planner.create_tasks_bulk(project_id, task_defs, user_id=uid)
        return {"status": "ok", "created": len(created), "tasks": created}
    except HTTPException:
        raise
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ================================================================
# AUTH — Phase 5A
# ================================================================
class _RegisterRequest(BaseModel):
    name: str
    email: str
    password: str
    role: str = "user"

class _LoginRequest(BaseModel):
    email: str
    password: str

class _UpdateMeRequest(BaseModel):
    name: str | None = None
    email: str | None = None
    preferences: dict | None = None

@app.post("/api/auth/register")
def auth_register(body: _RegisterRequest):
    try:
        result = auth_engine.register(body.name, body.email, body.password, body.role)
        return {"status": "ok", **result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        return {"status": "error", "error": str(e)}

@app.post("/api/auth/login")
def auth_login(body: _LoginRequest):
    result = auth_engine.login(body.email, body.password)
    if not result:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return {"status": "ok", **result}

@app.get("/api/auth/me")
def auth_me(current_user: dict = Depends(get_current_user)):
    user = auth_engine.get_me(current_user["user_id"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"status": "ok", "user": user}

@app.put("/api/auth/me")
def auth_update_me(body: _UpdateMeRequest, current_user: dict = Depends(get_current_user)):
    try:
        updates = {k: v for k, v in body.model_dump().items() if v is not None}
        user = auth_engine.update_me(current_user["user_id"], updates)
        return {"status": "ok", "user": user}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ================================================================
# CALENDAR — Phase 5C
# ================================================================
class _EventCreate(BaseModel):
    title:             str
    start:             str                    # ISO or "YYYY-MM-DD HH:MM"
    end:               str = ""
    duration_minutes:  int = 60
    description:       str = ""
    timezone:          str = "America/Bogota"
    participants:      list[str] = []
    linked_project_id: str | None = None
    linked_task_id:    str | None = None
    reminder_minutes:  int = 30

class _EventUpdate(BaseModel):
    title:             str | None = None
    start:             str | None = None
    end:               str | None = None
    description:       str | None = None
    timezone:          str | None = None
    participants:      list[str] | None = None
    linked_project_id: str | None = None
    linked_task_id:    str | None = None
    reminder_minutes:  int | None = None

@app.get("/api/calendar/events")
def cal_list(
    range: str = "",
    from_date: str = "",
    to_date: str = "",
    current_user: dict = Depends(get_optional_user),
):
    uid = current_user["user_id"]
    try:
        events = _cal(uid).list_events(
            range_name=range,
            from_date=from_date,
            to_date=to_date,
        )
        return {"status": "ok", "events": events, "count": len(events)}
    except Exception as e:
        return {"status": "error", "events": [], "error": str(e)}

@app.post("/api/calendar/events")
def cal_create(body: _EventCreate, current_user: dict = Depends(get_optional_user)):
    uid = current_user["user_id"]
    try:
        ev = _cal(uid).create_event(
            title=body.title,
            start=body.start,
            end=body.end,
            duration_minutes=body.duration_minutes,
            description=body.description,
            timezone_str=body.timezone,
            participants=body.participants,
            linked_project_id=body.linked_project_id,
            linked_task_id=body.linked_task_id,
            reminder_minutes=body.reminder_minutes,
        )
        return {"status": "ok", "event": ev}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        return {"status": "error", "error": str(e)}

@app.put("/api/calendar/events/{event_id}")
def cal_update(
    event_id: str,
    body: _EventUpdate,
    current_user: dict = Depends(get_optional_user),
):
    uid = current_user["user_id"]
    try:
        updates = {k: v for k, v in body.model_dump().items() if v is not None}
        ev = _cal(uid).update_event(event_id, updates)
        return {"status": "ok", "event": ev}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        return {"status": "error", "error": str(e)}

@app.delete("/api/calendar/events/{event_id}")
def cal_delete(event_id: str, current_user: dict = Depends(get_optional_user)):
    uid = current_user["user_id"]
    try:
        ok = _cal(uid).delete_event(event_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Event not found")
        return {"status": "ok", "deleted": event_id}
    except HTTPException:
        raise
    except Exception as e:
        return {"status": "error", "error": str(e)}

# ================================================================
# MEMORY  — Phase 5D
# ================================================================

class _MemSave(BaseModel):
    content:    str
    type:       str = "interaction"   # interaction|decision|event|insight|preference
    importance: int = 5               # 1–10
    tags:       List[str] = []
    metadata:   dict = {}

class _InsightCreate(BaseModel):
    content:    str
    importance: int = 7

@app.post("/api/memory/save")
def memory_save(body: _MemSave, current_user: dict = Depends(get_optional_user)):
    uid = current_user["user_id"]
    try:
        entry = _memory(uid).save(
            content=body.content,
            entry_type=body.type,
            importance=body.importance,
            tags=body.tags,
            metadata=body.metadata,
        )
        return {"status": "ok", "entry": entry}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        return {"status": "error", "error": str(e)}

@app.get("/api/memory/context")
def memory_context(
    limit: int = 20,
    min_importance: int = 4,
    current_user: dict = Depends(get_optional_user),
):
    uid = current_user["user_id"]
    try:
        ctx = _memory(uid).get_context(limit=limit, min_importance=min_importance)
        return {"status": "ok", **ctx}
    except Exception as e:
        return {"status": "error", "error": str(e)}

@app.get("/api/memory/history")
def memory_history(
    limit:          int = 50,
    offset:         int = 0,
    type:           str = "",
    min_importance: int = 1,
    since:          str = "",
    current_user: dict = Depends(get_optional_user),
):
    uid = current_user["user_id"]
    try:
        result = _memory(uid).get_history(
            limit=limit,
            offset=offset,
            entry_type=type,
            min_importance=min_importance,
            since=since,
        )
        return {"status": "ok", **result}
    except Exception as e:
        return {"status": "error", "error": str(e)}

@app.post("/api/memory/insight")
def memory_insight(body: _InsightCreate, current_user: dict = Depends(get_optional_user)):
    uid = current_user["user_id"]
    try:
        ins = _memory(uid).add_insight(body.content, body.importance)
        return {"status": "ok", "insight": ins}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        return {"status": "error", "error": str(e)}

@app.get("/api/memory/stats")
def memory_stats(current_user: dict = Depends(get_optional_user)):
    uid = current_user["user_id"]
    try:
        return {"status": "ok", **_memory(uid).stats()}
    except Exception as e:
        return {"status": "error", "error": str(e)}

# ================================================================
# NOTIFICATIONS  — Phase 5E
# ================================================================

class _NotifCreate(BaseModel):
    title:      str
    message:    str = ""
    type:       str = "general"     # task_reminder|meeting_alert|ai_insight|system_alert|general
    priority:   str = "medium"      # low|medium|high|critical
    source_id:  str = ""
    action_url: str = ""
    deduplicate: bool = True

@app.get("/api/notifications")
def notif_list(
    unread_only: bool = False,
    limit:       int  = 50,
    offset:      int  = 0,
    type:        str  = "",
    priority:    str  = "",
    current_user: dict = Depends(get_optional_user),
):
    uid = current_user["user_id"]
    try:
        result = _notif(uid).list_notifications(
            unread_only=unread_only,
            limit=limit,
            offset=offset,
            notif_type=type,
            priority=priority,
        )
        return {"status": "ok", **result}
    except Exception as e:
        return {"status": "error", "error": str(e)}

@app.post("/api/notifications")
def notif_create(body: _NotifCreate, current_user: dict = Depends(get_optional_user)):
    uid = current_user["user_id"]
    try:
        n = _notif(uid).create(
            title=body.title,
            message=body.message,
            notif_type=body.type,
            priority=body.priority,
            source_id=body.source_id,
            action_url=body.action_url,
            deduplicate=body.deduplicate,
        )
        return {"status": "ok", "notification": n}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        return {"status": "error", "error": str(e)}

@app.put("/api/notifications/{notif_id}/read")
def notif_mark_read(notif_id: str, current_user: dict = Depends(get_optional_user)):
    uid = current_user["user_id"]
    try:
        n = _notif(uid).mark_read(notif_id)
        return {"status": "ok", "notification": n}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        return {"status": "error", "error": str(e)}

@app.put("/api/notifications/read-all")
def notif_read_all(current_user: dict = Depends(get_optional_user)):
    uid = current_user["user_id"]
    try:
        count = _notif(uid).mark_all_read()
        return {"status": "ok", "marked_read": count}
    except Exception as e:
        return {"status": "error", "error": str(e)}

@app.delete("/api/notifications/{notif_id}")
def notif_delete(notif_id: str, current_user: dict = Depends(get_optional_user)):
    uid = current_user["user_id"]
    try:
        ok = _notif(uid).delete(notif_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Notification not found")
        return {"status": "ok", "deleted": notif_id}
    except HTTPException:
        raise
    except Exception as e:
        return {"status": "error", "error": str(e)}

@app.get("/api/notifications/unread-count")
def notif_unread_count(current_user: dict = Depends(get_optional_user)):
    uid = current_user["user_id"]
    try:
        return {"status": "ok", "unread": _notif(uid).unread_count()}
    except Exception as e:
        return {"status": "error", "error": str(e)}

# ================================================================
# AI ORCHESTRATOR  — Phase 5F
# ================================================================

class _OrchestratorRequest(BaseModel):
    message:     str
    include_data: bool = True   # whether to fetch live context data

def _build_orchestrator_context(uid: str, include_data: bool = True) -> dict:
    """
    Assembles context dict from live JARVIS data + Phase 5D memory.
    Designed to be fast: each fetch is try/except guarded.
    """
    ctx: dict = {}

    # Phase 5D memory context
    try:
        ctx["memory_context"] = _memory(uid).get_context(limit=15, min_importance=4).get("context", [])
    except Exception:
        ctx["memory_context"] = []

    if not include_data:
        return ctx

    # Notifications
    try:
        ctx["unread_notifications"] = _notif(uid).unread_count()
    except Exception:
        ctx["unread_notifications"] = 0

    # Memory stats
    try:
        ctx["memory_stats"] = _memory(uid).stats()
    except Exception:
        ctx["memory_stats"] = {}

    # Daily tasks & meetings (productivity agent)
    try:
        ws = _ws(uid)
        ws_data = ws.home(_user_name(uid))
        ctx["tasks"]    = ws_data.get("tasks", [])
        ctx["meetings"] = ws_data.get("meetings", [])
    except Exception:
        ctx["tasks"] = []
        ctx["meetings"] = []

    # Today's calendar events
    try:
        ctx["calendar_events"] = _cal(uid).get_today_events()
    except Exception:
        ctx["calendar_events"] = []

    # Projects
    try:
        ctx["projects"] = planner.list_projects(user_id=uid)
    except Exception:
        ctx["projects"] = []

    # Golf bag (lightweight summary)
    try:
        clubs = _ge(uid).get_bag()
        ctx["golf_bag"] = {"clubs": clubs if isinstance(clubs, list) else []}
    except Exception:
        ctx["golf_bag"] = {}

    return ctx

@app.post("/api/orchestrator/chat")
def orchestrator_chat(
    body: _OrchestratorRequest,
    current_user: dict = Depends(get_optional_user),
):
    uid = current_user["user_id"]
    try:
        context = _build_orchestrator_context(uid, include_data=body.include_data)
        result  = ai_orchestrator.route(body.message, context)
        # Auto-save interaction to Phase 5D memory at low importance
        try:
            _memory(uid).auto_save_interaction(
                body.message,
                result.get("response", ""),
                importance=3,
            )
        except Exception:
            pass
        return {"status": "ok", **result}
    except Exception as e:
        return {"status": "error", "error": str(e)}

@app.get("/api/orchestrator/classify")
def orchestrator_classify(
    message: str,
    current_user: dict = Depends(get_optional_user),
):
    try:
        return {"status": "ok", **ai_orchestrator.classify(message)}
    except Exception as e:
        return {"status": "error", "error": str(e)}

@app.get("/api/orchestrator/health")
def orchestrator_health(current_user: dict = Depends(get_optional_user)):
    try:
        return {"status": "ok", **ai_orchestrator.health()}
    except Exception as e:
        return {"status": "error", "error": str(e)}

@app.get("/api/orchestrator/audit")
def orchestrator_audit(
    limit: int = 20,
    current_user: dict = Depends(get_optional_user),
):
    try:
        return {"status": "ok", "log": ai_orchestrator.audit_log(limit=limit)}
    except Exception as e:
        return {"status": "error", "error": str(e)}

# ================================================================
# AUTOMATIONS  — Phase 5G
# ================================================================

class _AutoCreate(BaseModel):
    name:          str
    trigger_type:  str        = "manual"   # time | event | manual
    trigger_value: str        = ""         # "09:00" for time, event name for event
    conditions:    List[dict] = []
    actions:       List[dict] = []         # [{type, config}]
    cooldown_min:  int        = 5
    enabled:       bool       = True

class _AutoUpdate(BaseModel):
    name:          Optional[str]       = None
    trigger_type:  Optional[str]       = None
    trigger_value: Optional[str]       = None
    conditions:    Optional[List[dict]] = None
    actions:       Optional[List[dict]] = None
    cooldown_min:  Optional[int]       = None
    enabled:       Optional[bool]      = None

class _AutoRunBody(BaseModel):
    context: dict = {}
    force:   bool = True   # manual runs bypass cooldown by default

@app.get("/api/automations")
def auto_list(
    enabled_only: bool = False,
    trigger_type: str  = "",
    current_user: dict = Depends(get_optional_user),
):
    uid = current_user["user_id"]
    try:
        items = _auto(uid).list_automations(enabled_only=enabled_only,
                                             trigger_type=trigger_type)
        return {"status": "ok", "automations": items, "total": len(items)}
    except Exception as e:
        return {"status": "error", "error": str(e)}

@app.post("/api/automations")
def auto_create(body: _AutoCreate, current_user: dict = Depends(get_optional_user)):
    uid = current_user["user_id"]
    try:
        item = _auto(uid).create(
            name=body.name,
            trigger_type=body.trigger_type,
            trigger_value=body.trigger_value,
            conditions=body.conditions,
            actions=body.actions,
            cooldown_min=body.cooldown_min,
            enabled=body.enabled,
        )
        return {"status": "ok", "automation": item}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        return {"status": "error", "error": str(e)}

@app.put("/api/automations/{automation_id}")
def auto_update(
    automation_id: str,
    body: _AutoUpdate,
    current_user: dict = Depends(get_optional_user),
):
    uid = current_user["user_id"]
    try:
        updates = {k: v for k, v in body.model_dump().items() if v is not None}
        item = _auto(uid).update(automation_id, updates)
        return {"status": "ok", "automation": item}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        return {"status": "error", "error": str(e)}

@app.delete("/api/automations/{automation_id}")
def auto_delete(automation_id: str, current_user: dict = Depends(get_optional_user)):
    uid = current_user["user_id"]
    try:
        ok = _auto(uid).delete(automation_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Automation not found")
        return {"status": "ok", "deleted": automation_id}
    except HTTPException:
        raise
    except Exception as e:
        return {"status": "error", "error": str(e)}

@app.post("/api/automations/{automation_id}/run")
def auto_run(
    automation_id: str,
    body: _AutoRunBody,
    current_user: dict = Depends(get_optional_user),
):
    uid = current_user["user_id"]
    try:
        result = _auto(uid).run(automation_id, context=body.context, force=body.force)
        return {"status": "ok", **result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        return {"status": "error", "error": str(e)}

@app.post("/api/automations/fire-event")
def auto_fire_event(
    event_name:   str,
    context:      dict = {},
    current_user: dict = Depends(get_optional_user),
):
    uid = current_user["user_id"]
    try:
        results = _auto(uid).fire_event(event_name, context=context)
        return {"status": "ok", "fired": len(results), "results": results}
    except Exception as e:
        return {"status": "error", "error": str(e)}

@app.get("/api/automations/log")
def auto_log(limit: int = 20, current_user: dict = Depends(get_optional_user)):
    uid = current_user["user_id"]
    try:
        return {"status": "ok", "log": _auto(uid).execution_log(limit=limit)}
    except Exception as e:
        return {"status": "error", "error": str(e)}

@app.get("/api/automations/stats")
def auto_stats(current_user: dict = Depends(get_optional_user)):
    uid = current_user["user_id"]
    try:
        return {"status": "ok", **_auto(uid).stats()}
    except Exception as e:
        return {"status": "error", "error": str(e)}

# ================================================================
# INTEGRATIONS HUB  — Phase 5H
# ================================================================

class _ConnectBody(BaseModel):
    provider:     str
    redirect_uri: str = "http://localhost:8000/api/integrations/callback"
    state:        str = ""

class _CallbackBody(BaseModel):
    provider:     str
    code:         str
    redirect_uri: str = "http://localhost:8000/api/integrations/callback"

class _SyncBody(BaseModel):
    provider: str

@app.get("/api/integrations/status")
def integrations_status(current_user: dict = Depends(get_optional_user)):
    """Return connection status for all providers."""
    uid = current_user["user_id"]
    try:
        ts  = _tok(uid)
        out = {}
        for provider in _PROVIDERS:
            intg = _integration(uid, provider)
            st   = intg.status()
            st["configured"] = intg._configured() if hasattr(intg, "_configured") else True
            out[provider]    = st
        return {"status": "ok", "integrations": out}
    except Exception as e:
        return {"status": "error", "error": str(e)}

@app.post("/api/integrations/connect")
def integrations_connect(
    body: _ConnectBody,
    current_user: dict = Depends(get_optional_user),
):
    """Return OAuth authorisation URL for the requested provider."""
    uid = current_user["user_id"]
    if body.provider not in _PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {body.provider}")
    try:
        intg     = _integration(uid, body.provider)
        auth_url = intg.get_auth_url(body.redirect_uri, body.state)
        return {"status": "ok", "provider": body.provider, "auth_url": auth_url}
    except _IntegrationConfigError as e:
        return {
            "status":       "not_configured",
            "provider":     body.provider,
            "message":      str(e),
            "auth_url":     None,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}

@app.post("/api/integrations/callback")
def integrations_callback(
    body: _CallbackBody,
    current_user: dict = Depends(get_optional_user),
):
    """Exchange OAuth code for tokens and persist them."""
    uid = current_user["user_id"]
    if body.provider not in _PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {body.provider}")
    try:
        intg   = _integration(uid, body.provider)
        result = intg.exchange_code(body.code, body.redirect_uri)
        # Auto-save connection event to memory
        try:
            _memory(uid).save(
                content    = f"Connected integration: {body.provider}",
                entry_type = "event",
                importance = 6,
                tags       = ["integration", body.provider],
            )
        except Exception:
            pass
        return {"status": "ok", **result}
    except _IntegrationConfigError as e:
        return {"status": "not_configured", "message": str(e)}
    except Exception as e:
        return {"status": "error", "error": str(e)}

@app.post("/api/integrations/sync")
def integrations_sync(
    body: _SyncBody,
    current_user: dict = Depends(get_optional_user),
):
    """Trigger a data sync for a connected provider."""
    uid = current_user["user_id"]
    if body.provider not in _PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {body.provider}")
    try:
        intg   = _integration(uid, body.provider)
        result = intg.sync(
            calendar = _cal(uid),
            memory   = _memory(uid),
        )
        return {"status": "ok", "provider": body.provider, **result}
    except Exception as e:
        return {"status": "error", "error": str(e)}

@app.delete("/api/integrations/{provider}")
def integrations_disconnect(
    provider: str,
    current_user: dict = Depends(get_optional_user),
):
    """Revoke tokens and disconnect a provider."""
    uid = current_user["user_id"]
    if provider not in _PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")
    try:
        intg = _integration(uid, provider)
        ok   = intg.revoke()
        if not ok:
            return {"status": "not_connected", "provider": provider}
        try:
            _memory(uid).save(
                content    = f"Disconnected integration: {provider}",
                entry_type = "event",
                importance = 5,
                tags       = ["integration", provider],
            )
        except Exception:
            pass
        return {"status": "ok", "disconnected": provider}
    except Exception as e:
        return {"status": "error", "error": str(e)}

# ================================================================
# ANALYTICS  — Phase 5I
# ================================================================

def _fetch_analytics_context(uid: str) -> dict:
    """Gather all data needed for analytics in one place."""
    ctx: dict = {}
    try:
        ws      = _ws(uid)
        ws_data = ws.home(_user_name(uid))
        ctx["tasks"]    = ws_data.get("tasks", [])
        ctx["meetings"] = ws_data.get("meetings", [])
    except Exception:
        ctx["tasks"] = []
        ctx["meetings"] = []

    try:
        ctx["events"] = _cal(uid).get_today_events()
    except Exception:
        ctx["events"] = []

    try:
        ctx["projects"] = planner.list_projects(user_id=uid)
    except Exception:
        ctx["projects"] = []

    try:
        ge = _ge(uid)
        ctx["bag"]    = ge.get_bag() if hasattr(ge, "get_bag") else []
        ctx["rounds"] = ge.get_rounds() if hasattr(ge, "get_rounds") else []
    except Exception:
        ctx["bag"]    = []
        ctx["rounds"] = []

    try:
        ctx["memory_stats"] = _memory(uid).stats()
    except Exception:
        ctx["memory_stats"] = {}

    try:
        ctx["notif_unread"] = _notif(uid).unread_count()
    except Exception:
        ctx["notif_unread"] = 0

    return ctx

@app.get("/api/analytics/summary")
def analytics_summary(current_user: dict = Depends(get_optional_user)):
    uid = current_user["user_id"]
    try:
        ctx = _fetch_analytics_context(uid)
        result = _analytics.full_summary(
            tasks    = ctx["tasks"],
            meetings = ctx["meetings"],
            projects = ctx["projects"],
            rounds   = ctx["rounds"],
            bag      = ctx["bag"],
            events   = ctx["events"],
            memory_stats  = ctx["memory_stats"],
            notif_unread  = ctx["notif_unread"],
        )
        return {"status": "ok", **result}
    except Exception as e:
        return {"status": "error", "error": str(e)}

@app.get("/api/analytics/productivity")
def analytics_productivity(current_user: dict = Depends(get_optional_user)):
    uid = current_user["user_id"]
    try:
        ctx = _fetch_analytics_context(uid)
        result = _analytics.productivity_metrics(
            tasks    = ctx["tasks"],
            meetings = ctx["meetings"],
            events   = ctx["events"],
        )
        return {"status": "ok", **result}
    except Exception as e:
        return {"status": "error", "error": str(e)}

@app.get("/api/analytics/golf")
def analytics_golf(current_user: dict = Depends(get_optional_user)):
    uid = current_user["user_id"]
    try:
        ctx = _fetch_analytics_context(uid)
        result = _analytics.golf_metrics(rounds=ctx["rounds"], bag=ctx["bag"])
        return {"status": "ok", **result}
    except Exception as e:
        return {"status": "error", "error": str(e)}

@app.get("/api/analytics/projects")
def analytics_projects(current_user: dict = Depends(get_optional_user)):
    uid = current_user["user_id"]
    try:
        ctx = _fetch_analytics_context(uid)
        result = _analytics.project_metrics(projects=ctx["projects"])
        return {"status": "ok", **result}
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ── Phase 5K: WOW Layer endpoints ─────────────────────────────────────

@app.get("/api/wow/insights")
def wow_insights(current_user: dict = Depends(get_optional_user)):
    uid = current_user["user_id"]
    try:
        ctx = _fetch_analytics_context(uid)
        insights = _wow.generate_insights(ctx)
        return {"status": "ok", "insights": insights, "count": len(insights)}
    except Exception as e:
        return {"status": "error", "error": str(e), "insights": []}


@app.get("/api/wow/briefing")
def wow_briefing(current_user: dict = Depends(get_optional_user)):
    uid = current_user["user_id"]
    try:
        ctx = _fetch_analytics_context(uid)
        briefing = _wow.generate_briefing(ctx)
        return {"status": "ok", **briefing}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.get("/api/wow/suggestions")
def wow_suggestions(current_user: dict = Depends(get_optional_user)):
    uid = current_user["user_id"]
    try:
        ctx = _fetch_analytics_context(uid)
        suggestions = _wow.smart_suggestions(ctx)
        return {"status": "ok", "suggestions": suggestions}
    except Exception as e:
        return {"status": "error", "error": str(e), "suggestions": []}


# ── Phase 5K-2: Golf Swing Vision Pro endpoints ───────────────────────

class _VisionFrameRequest(BaseModel):
    landmarks: list   # 33 × {x, y, z, visibility}

class _VisionSwingRequest(BaseModel):
    frames: list      # [{landmarks: [...], frame_time: float}, ...]
    club:   str  = "unknown"
    fps:    float = 30.0


@app.post("/api/golf/vision/analyze")
def golf_vision_analyze(
    req: _VisionFrameRequest,
    current_user: dict = Depends(get_optional_user),
):
    uid = current_user["user_id"]
    try:
        result = _gve(uid).analyze_frame(req.landmarks)
        return result
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.post("/api/golf/vision/swing")
def golf_vision_swing(
    req: _VisionSwingRequest,
    current_user: dict = Depends(get_optional_user),
):
    uid = current_user["user_id"]
    try:
        result = _gve(uid).analyze_swing_sequence(req.frames, req.club, req.fps)
        return result
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.get("/api/golf/vision/history")
def golf_vision_history(
    limit:  int = 10,
    offset: int = 0,
    current_user: dict = Depends(get_optional_user),
):
    uid = current_user["user_id"]
    try:
        return {"status": "ok", **_gve(uid).get_history(limit, offset)}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.get("/api/golf/vision/drills")
def golf_vision_drills(current_user: dict = Depends(get_optional_user)):
    uid = current_user["user_id"]
    try:
        # Pass last swing as context for targeted drills
        history = _gve(uid).get_history(limit=1)
        last    = history["items"][0] if history["items"] else None
        drills  = _gve(uid).get_drills(last)
        return {"status": "ok", "drills": drills}
    except Exception as e:
        return {"status": "error", "error": str(e), "drills": []}
