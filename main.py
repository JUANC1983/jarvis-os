from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import asyncio
import json
import logging
import os
import shutil
import threading
import time
import uuid as _uuid_mod

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

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
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
from core.golf_swing_elite import GolfSwingElite as _GolfSwingElite
from core.fitness_engine import FitnessEngine as _FitnessEngine
from core.weather_engine import weather_engine as _weather_engine
from core.family_engine import FamilyEngine as _FamilyEngine
from core.office_engine import OfficeEngine as _OfficeEngine

# ── Outlook / Microsoft Graph integration ───────────────────────────────
try:
    from opsx.connectors.outlook_auth    import (
        token_store as _ms_token_store,
        get_login_url as _ms_login_url,
        exchange_code as _ms_exchange_code,
        get_valid_token as _ms_get_token,
        is_configured as _ms_configured,
        TokenExpiredError as _ms_TokenExpiredError,
        verify_graph_token as _ms_verify_token,
    )
    from opsx.connectors.outlook_webhook import (
        subscription_store as _ms_sub_store,
        create_subscription as _ms_create_sub,
        renew_subscription  as _ms_renew_sub,
        delete_subscription as _ms_delete_sub,
        validate_client_state as _ms_validate_state,
        start_renewal_loop  as _ms_start_renewal,
        stop_renewal_loop   as _ms_stop_renewal,
    )
    from opsx.connectors.outlook_email   import (
        fetch_email  as _ms_fetch_email,
        list_inbox   as _ms_list_inbox,
        count_unread as _ms_count_unread,
        mark_as_read as _ms_mark_read,
    )
    from opsx.agents.email_agent         import process_email as _ms_process_email
    from opsx.services.email_actions     import (
        email_store            as _ms_email_store,
        store_processed_email  as _ms_store_email,
        send_approved_reply    as _ms_send_reply,
        delete_approved_email  as _ms_delete_email,
        ignore_email           as _ms_ignore_email,
        mark_email_read        as _ms_mark_email_read,
        update_reply_draft     as _ms_update_draft,
        create_task_from_email           as _ms_task_from_email,
        create_calendar_event_from_email as _ms_event_from_email,
    )
    from opsx.core.event_queue import event_queue as _ms_event_queue
    _OUTLOOK_AVAILABLE = True
except Exception as _e:
    _OUTLOOK_AVAILABLE = False
    logging.getLogger("jarvis").warning("Outlook integration unavailable: %s", _e)

# ── Graph Memory System ──────────────────────────────────────────────────────
try:
    import opsx.memory as _graph_mem
    _GRAPH_MEM_AVAILABLE = True
except Exception as _gme:
    _graph_mem = None
    _GRAPH_MEM_AVAILABLE = False
    logging.getLogger("jarvis").warning("Graph Memory unavailable: %s", _gme)

_analytics = _AnalyticsEngine()
_wow       = _WowEngine()

# ── Fitness engine cache ─────────────────────────────────────────────
_fit_cache: dict = {}
def _fit(user_id: str) -> _FitnessEngine:
    if user_id not in _fit_cache:
        base = BASE_DIR / "data" / "fitness" / user_id
        _fit_cache[user_id] = _FitnessEngine(str(base), user_id)
    return _fit_cache[user_id]

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

# Per-user weather context: {uid: {lat, lon, data, ts}}
_weather_user_cache: dict = {}

# ── Family / Office engine caches ────────────────────────────────────────────
_family_cache: dict = {}
_office_cache: dict = {}

def _family(user_id: str) -> _FamilyEngine:
    if user_id not in _family_cache:
        path = BASE_DIR / "data" / "family" / user_id
        _family_cache[user_id] = _FamilyEngine(str(path), user_id)
    return _family_cache[user_id]

def _office(user_id: str) -> _OfficeEngine:
    if user_id not in _office_cache:
        path = BASE_DIR / "data" / "office" / user_id
        _office_cache[user_id] = _OfficeEngine(str(path), user_id)
    return _office_cache[user_id]


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

    # Weather (injected if user has a cached location)
    try:
        for uid_w, wc in _weather_user_cache.items():
            ws = _weather_engine.as_context_string(wc["lat"], wc["lon"])
            if ws:
                parts.append(ws)
            break  # only need one (single-user system)
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
    # life modules
    "family", "office",
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

    if any(w in low for w in [
        "familia", "family", "hijo", "hija", "esposa", "esposo", "mama", "papa",
        "cumpleaños", "birthday", "aniversario", "anniversary", "colegio", "school",
        "niños", "ninos", "kids", "evento familiar",
    ]):
        return "family"

    if any(w in low for w in [
        "oficina", "office", "colega", "colleague", "compañero", "companero",
        "gasto laboral", "expense", "reembolso", "departamento", "jefe",
        "tarea de trabajo", "work task", "equipo de trabajo",
    ]):
        return "office"

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
        elif intent == "family":
            return _family("owner").summary()
        elif intent == "office":
            return _office("owner").summary()
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
  family    → family_agent()          — family members, birthdays, events, notes, kids schedule
  office    → office_agent()          — colleagues, work tasks, expenses, office management

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
- "family"    → "familia", "hijo", "cumpleaños", "birthday", "colegio", kids schedule, family events
- "office"    → "oficina", "colega", "gasto", "expense", "compañero de trabajo", work tasks, expenses
- "none"      → greetings, general questions, opinions, philosophy, definitions, anything else

Critical: Respond ONLY with valid JSON — no markdown, no explanation, no extra text.

{
  "action": "none | analyze | scan | news | pipeline | agents | golf | workspace | medical | legal | fitness | coach | family | office",
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


@app.get("/api/health")
def system_health():
    """Comprehensive system health check — all modules, no secrets exposed."""
    import os
    report: dict = {"status": "ok", "systems": {}, "timestamp": datetime.utcnow().isoformat()}

    # Markets
    report["systems"]["markets"] = {
        "available":   _MKT_AVAILABLE,
        "engine":      _mkt_engine is not None,
    }
    try:
        if _mkt_engine:
            snap = _mkt_engine.snapshot()
            report["systems"]["markets"]["items_count"] = len(snap.get("items", []))
            report["systems"]["markets"]["status"] = "ok" if snap.get("items") else "no_data"
        else:
            report["systems"]["markets"]["status"] = "unavailable"
    except Exception as e:
        report["systems"]["markets"]["status"] = f"error: {e}"

    # Outlook
    report["systems"]["outlook"] = {
        "module_loaded": _OUTLOOK_AVAILABLE,
        "client_id_set": bool(os.getenv("OUTLOOK_CLIENT_ID") or os.getenv("OUTLOOK_APPLICATION")),
        "secret_set":    bool(os.getenv("OUTLOOK_CLIENT_SECRET")),
    }

    # Graph Memory
    report["systems"]["graph_memory"] = {
        "available": _GRAPH_MEM_AVAILABLE,
        "mode":      _graph_mem.GRAPH_MEMORY_MODE if _GRAPH_MEM_AVAILABLE else "OFF",
    }
    if _GRAPH_MEM_AVAILABLE and _graph_mem.get_engine():
        e = _graph_mem.get_engine()
        report["systems"]["graph_memory"]["nodes"] = e.node_count()
        report["systems"]["graph_memory"]["edges"] = e.edge_count()

    # Notifications
    try:
        notif = _notif("owner")
        report["systems"]["notifications"] = {"status": "ok", "unread": notif.unread_count()}
    except Exception as e:
        report["systems"]["notifications"] = {"status": f"error: {e}"}

    # Calendar
    try:
        cal = _cal("owner")
        events = cal.get_events(upcoming_days=7)
        report["systems"]["calendar"] = {"status": "ok", "upcoming_events": len(events)}
    except Exception as e:
        report["systems"]["calendar"] = {"status": f"error: {e}"}

    # News
    try:
        report["systems"]["news"] = {"status": "ok", "engine": news_engine is not None}
    except Exception:
        report["systems"]["news"] = {"status": "error"}

    # Brain
    try:
        bh = brain.health()
        report["systems"]["brain"] = {"status": "ok", "available": bh.get("available", True)}
    except Exception:
        report["systems"]["brain"] = {"status": "error"}

    failing = [k for k, v in report["systems"].items() if "error" in str(v.get("status", ""))]
    if failing:
        report["status"] = "degraded"
        report["failing"] = failing

    return report


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
def chat(req: ChatRequest, current_user: dict = Depends(get_optional_user)):
    try:
        uid = current_user["user_id"]

        # ── Side effect: execute any detected action through central brain
        cmd_result = _execute_command_action(req.message, uid)

        # ── AI reply (3-tier fallback) ────────────────────────────────
        result = _agent_chat(req.message)
        if result is None:
            result = _llm_chat(req.message)
        if result is None:
            result = brain.chat(req.message)

        # ── Pure-action intents: prefer action reply, skip noisy AI ─────
        _PURE_ACTION_INTENTS = {"shopping_list", "reminder", "task", "meeting",
                                "calendar_query", "calendar_delete", "email",
                                "portfolio_query"}
        action_reply = cmd_result.get("reply", "")
        if cmd_result["action_result"] and not cmd_result["action_result"].get("error") \
                and cmd_result["intent"] in _PURE_ACTION_INTENTS and action_reply:
            final_reply = action_reply
        else:
            final_reply = (result or {}).get("reply", "") or (result or {}).get("summary", "") \
                          or action_reply

        return JSONResponse(
            content={
                "status":        "ok",
                "response":      result,
                "reply":         final_reply,
                "summary":       (result or {}).get("summary", ""),
                "type":          (result or {}).get("type", "chat"),
                "details":       (result or {}).get("details", {}),
                "action":        (result or {}).get("action", ""),
                "confidence":    (result or {}).get("confidence", 0.0),
                "source":        (result or {}).get("source", "brain"),
                "action_result": cmd_result.get("action_result"),
                "action_id":     cmd_result.get("action_id"),
                "undo_available": cmd_result.get("undo_available", False),
                "intent":        cmd_result.get("intent", "general"),
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
    """
    Route a voice transcript through the central command router (same as chat).
    Executes backend actions (shopping, reminders, tasks) directly.
    Optionally speaks the response via ElevenLabs TTS.
    """
    uid = current_user["user_id"]
    ve  = _voice_engine(uid)
    raw = req.transcript
    print(f"[VOICE COMMAND] transcript={raw!r} source={req.source}")

    # ── Route through central brain (same as command_route) ───────────
    exec_result   = _execute_command_action(raw, uid)
    matched_tab   = exec_result["tab"]
    matched_intent = exec_result["intent"]
    action_result = exec_result["action_result"]
    response_text = exec_result["reply"]

    # ── AI reply if no action-specific reply ──────────────────────────
    if not response_text:
        try:
            ctx = _build_orchestrator_context(uid, include_data=False)
            ctx["action_executed"] = action_result
            result        = ai_orchestrator.route(raw, ctx)
            response_text = result.get("response", "") or result.get("reply", "")
        except Exception:
            result = {}
    else:
        result = {}

    domain = result.get("domain", matched_intent)
    print(f"[VOICE COMMAND] intent={matched_intent} action={action_result} response={response_text[:80]!r}")

    ve.log_command(
        transcript = raw,
        response   = response_text,
        domain     = domain,
        source     = req.source,
    )

    if req.speak_response:
        svc = get_voice_service()
        if svc.configured:
            audio = svc.speak(response_text)
            if audio:
                return Response(content=audio, media_type="audio/mpeg")
        return {
            "status":        "ok",
            "domain":        domain,
            "response":      response_text,
            "tts_available": False,
            "tts_reason":    "ELEVENLABS_API_KEY not configured",
            "tab":           matched_tab,
            "intent":        matched_intent,
            "action_result": action_result,
            "action_id":     exec_result.get("action_id", ""),
            "undo_available": exec_result.get("undo_available", False),
        }

    return {
        "status":        "ok",
        "domain":        domain,
        "response":      response_text,
        "reply":         response_text,
        "agent":         result.get("agent", ""),
        "tab":           matched_tab,
        "intent":        matched_intent,
        "action_result": action_result,
        "action_id":     exec_result.get("action_id", ""),
        "undo_available": exec_result.get("undo_available", False),
        "data":          result.get("data", {}),
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


@app.get("/api/voice/qa")
def voice_qa(current_user: dict = Depends(get_optional_user)):
    """
    Full voice system health check.
    Probes ElevenLabs TTS with a short phrase to verify end-to-end connectivity.
    Returns structured result — never exposes secrets.
    """
    import os as _os
    svc = get_voice_service()

    result: dict = {
        "configured":            svc.configured,
        "elevenlabs_key_present": bool(_os.getenv("ELEVENLABS_API_KEY", "").strip()),
        "voice_id_present":       bool(_os.getenv("ELEVENLABS_VOICE_ID", "").strip()),
        "voice_id_in_use":        svc.voice_id,
        "model_in_use":           svc.model_id,
        "status_endpoint_ok":     True,
        "settings_endpoint_ok":   True,
        "tts_test_ok":            False,
        "tts_bytes":              0,
        "last_error":             None,
    }

    print(f"[VOICE QA] configured={result['configured']} key_present={result['elevenlabs_key_present']}")

    if not svc.configured:
        result["last_error"] = (
            "ELEVENLABS_API_KEY not set. "
            "Add it to Railway environment variables to enable voice."
        )
        print(f"[VOICE QA] FAIL: {result['last_error']}")
        return result

    probe = "JARVIS voice system online."
    print(f"[VOICE TTS] Probe: {probe!r}")
    try:
        audio = svc.speak(probe)
        if audio and len(audio) > 100:
            result["tts_test_ok"] = True
            result["tts_bytes"]   = len(audio)
            print(f"[VOICE TTS] OK — {len(audio)} bytes returned")
        else:
            result["last_error"] = (
                "TTS returned empty or unusable audio. "
                "Verify API key is valid and account has quota."
            )
            print(f"[VOICE ERROR] TTS empty: {audio!r}")
    except Exception as e:
        result["last_error"] = f"TTS probe exception: {e}"
        print(f"[VOICE ERROR] {e}")

    return result


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

@app.get("/api/calendar/status")
def cal_status(current_user: dict = Depends(get_optional_user)):
    """Return calendar connection status. Always returns connected since local calendar is always available."""
    uid = current_user["user_id"]
    try:
        events = _cal(uid).list_events(range_name="day")
        return {
            "status":   "connected",
            "provider": "local",
            "source":   "local",
            "message":  "Calendar connected",
            "events_today": len(events),
        }
    except Exception as e:
        return {
            "status":   "disconnected",
            "provider": None,
            "source":   None,
            "message":  f"Calendar error: {e}",
        }


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
        for ev in events:
            ev.setdefault("provider", "local")
            ev.setdefault("source", "local")
        return {
            "status":   "connected",
            "provider": "local",
            "source":   "local",
            "events":   events,
            "count":    len(events),
        }
    except Exception as e:
        return {"status": "error", "provider": None, "events": [], "error": str(e)}

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
# GRAPH MEMORY  — Phase GM
# ================================================================

class _GMNodeCreate(BaseModel):
    id:         str
    type:       str
    label:      str
    module:     str
    content:    str
    importance: float = 0.5
    tags:       List[str] = []
    metadata:   Dict[str, Any] = {}

class _GMEdgeCreate(BaseModel):
    source_id: str
    target_id: str
    relation:  str
    weight:    float = 0.5
    metadata:  Dict[str, Any] = {}

class _GMBackfillReq(BaseModel):
    modules: List[str] = []


@app.get("/api/graph/status")
def gm_status():
    if not _GRAPH_MEM_AVAILABLE:
        return {"available": False, "mode": "unavailable"}
    try:
        engine = _graph_mem.get_engine()
        mode   = _graph_mem.GRAPH_MEMORY_MODE
        if engine is None:
            return {"available": True, "mode": mode, "nodes": 0, "edges": 0, "active": False}
        return {
            "available": True,
            "mode":      mode,
            "active":    _graph_mem.is_active(),
            "enabled":   _graph_mem.is_enabled(),
            **engine.health(),
        }
    except Exception as e:
        return {"available": False, "error": str(e)}


@app.post("/api/graph/nodes")
def gm_add_node(body: _GMNodeCreate):
    if not _GRAPH_MEM_AVAILABLE or not _graph_mem.get_engine():
        raise HTTPException(status_code=503, detail="Graph Memory not available")
    try:
        node = _graph_mem.get_engine().add_node(
            node_id=body.id, node_type=body.type, label=body.label,
            module=body.module, content=body.content, importance=body.importance,
            tags=body.tags, metadata=body.metadata,
        )
        return {"status": "ok", "node": node.to_dict()}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.get("/api/graph/nodes")
def gm_list_nodes(module: str = "", node_type: str = "", tag: str = "", limit: int = 50):
    if not _GRAPH_MEM_AVAILABLE or not _graph_mem.get_engine():
        return {"status": "ok", "nodes": []}
    try:
        nodes = _graph_mem.get_engine().list_nodes(
            module=module or None, node_type=node_type or None,
            tag=tag or None, limit=limit,
        )
        return {"status": "ok", "nodes": [n.to_dict() for n in nodes], "count": len(nodes)}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.delete("/api/graph/nodes/{node_id}")
def gm_delete_node(node_id: str):
    if not _GRAPH_MEM_AVAILABLE or not _graph_mem.get_engine():
        raise HTTPException(status_code=503, detail="Graph Memory not available")
    deleted = _graph_mem.get_engine().delete_node(node_id)
    return {"status": "ok", "deleted": deleted}


@app.post("/api/graph/edges")
def gm_add_edge(body: _GMEdgeCreate):
    if not _GRAPH_MEM_AVAILABLE or not _graph_mem.get_engine():
        raise HTTPException(status_code=503, detail="Graph Memory not available")
    try:
        edge = _graph_mem.get_engine().add_edge(
            source_id=body.source_id, target_id=body.target_id,
            relation=body.relation, weight=body.weight, metadata=body.metadata,
        )
        if edge is None:
            return {"status": "error", "error": "One or both nodes not found"}
        return {"status": "ok", "edge": edge.to_dict()}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.get("/api/graph/search")
def gm_search(q: str, module: str = "", limit: int = 10):
    if not _GRAPH_MEM_AVAILABLE or not _graph_mem.get_engine():
        return {"status": "ok", "results": []}
    try:
        nodes = _graph_mem.get_engine().search_nodes(q, module=module or None, limit=limit)
        return {"status": "ok", "results": [n.to_dict() for n in nodes], "count": len(nodes)}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.get("/api/graph/context")
def gm_context(module: str = "general", q: str = "", limit: int = 5):
    if not _GRAPH_MEM_AVAILABLE or not _graph_mem.get_engine():
        return {"status": "ok", "items": [], "text": ""}
    try:
        router = _graph_mem.get_router()
        if not router:
            return {"status": "ok", "items": [], "text": ""}
        ctx = router.build_context(module=module, query=q, limit=limit)
        return {"status": "ok", "items": ctx.items, "text": ctx.text, "tokens": ctx.tokens}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.post("/api/graph/backfill")
async def gm_backfill(body: _GMBackfillReq):
    """
    Seed graph memory from existing JARVIS data files.
    Idempotent — upserts on existing node ids.
    """
    if not _GRAPH_MEM_AVAILABLE or not _graph_mem.get_engine():
        raise HTTPException(status_code=503, detail="Graph Memory not available")
    try:
        from opsx.memory.backfill import run_backfill
        result = await run_backfill(_graph_mem.get_engine(), modules=body.modules or None)
        return {"status": "ok", **result}
    except ImportError:
        return {"status": "error", "error": "Backfill module not yet available"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.get("/api/graph/stats")
def gm_stats():
    if not _GRAPH_MEM_AVAILABLE or not _graph_mem.get_engine():
        return {"status": "ok", "available": False}
    try:
        return {"status": "ok", "available": True, **_graph_mem.get_engine().stats()}
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

    # Graph Memory context (ACTIVE mode only — silent fallback)
    try:
        if _GRAPH_MEM_AVAILABLE and _graph_mem.is_active():
            from core.ai_orchestrator import classify_intent as _classify_intent
            # We don't have a query here yet — provide module-level summary
            ctx["graph_memory_context"] = None   # will be enriched per-query if needed
    except Exception:
        pass

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

    # Family context
    try:
        fam = _family(uid)
        ctx["family_members"] = fam.get_members()
        ctx["family_events"]  = fam.get_events(upcoming_days=30)
        ctx["family_summary"] = fam.summary()
    except Exception:
        ctx["family_members"] = []
        ctx["family_events"]  = []
        ctx["family_summary"] = {}

    # Office context
    try:
        off = _office(uid)
        ctx["office_colleagues"] = off.get_colleagues()
        ctx["office_tasks"]      = off.get_tasks()
        ctx["office_expenses"]   = off.get_expenses()
        ctx["office_summary"]    = off.summary()
    except Exception:
        ctx["office_colleagues"] = []
        ctx["office_tasks"]      = []
        ctx["office_expenses"]   = []
        ctx["office_summary"]    = {}

    # Weather context (injected when user has shared location)
    try:
        wc = _weather_user_cache.get(uid) or _weather_user_cache.get("owner")
        if wc:
            ctx["weather"] = _weather_engine.get_current(wc["lat"], wc["lon"])
            ctx["weather_golf"]    = _weather_engine.golf_context(wc["lat"], wc["lon"])
            ctx["weather_running"] = _weather_engine.running_context(wc["lat"], wc["lon"])
        else:
            ctx["weather"] = {"available": False}
    except Exception:
        ctx["weather"] = {"available": False}

    return ctx


# ── Weather context endpoint ─────────────────────────────────────────────────

class _WeatherLocReq(BaseModel):
    lat: float
    lon: float
    city: str = ""

@app.get("/api/context/weather")
def get_weather_context(
    lat: float,
    lon: float,
    city: str = "",
    current_user: dict = Depends(get_optional_user),
):
    uid = current_user["user_id"]
    data = _weather_engine.get_current(lat, lon)
    if data.get("available", False):
        _weather_user_cache[uid] = {"lat": lat, "lon": lon, "city": city}
        _weather_user_cache["owner"] = {"lat": lat, "lon": lon, "city": city}
        # Invalidate system context cache so next LLM call picks up weather
        _ctx_cache["ts"] = 0.0
    forecast = _weather_engine.get_forecast(lat, lon)
    return {
        "status": "ok",
        "current": data,
        "forecast": forecast,
        "golf_context": _weather_engine.golf_context(lat, lon),
        "running_context": _weather_engine.running_context(lat, lon),
    }

@app.post("/api/context/weather")
def post_weather_context(
    body: _WeatherLocReq,
    current_user: dict = Depends(get_optional_user),
):
    return get_weather_context(body.lat, body.lon, body.city, current_user)


@app.post("/api/orchestrator/chat")
def orchestrator_chat(
    body: _OrchestratorRequest,
    current_user: dict = Depends(get_optional_user),
):
    uid = current_user["user_id"]
    try:
        context = _build_orchestrator_context(uid, include_data=body.include_data)

        # Inject graph memory context if ACTIVE (per-query, silent fallback)
        try:
            if _GRAPH_MEM_AVAILABLE and _graph_mem.is_active():
                from core.ai_orchestrator import classify_intent as _ci
                _gm_module = _graph_mem.get_router().route_text(body.message)
                _gm_items  = _graph_mem.get_context(_gm_module, body.message, limit=5)
                if _gm_items:
                    context["memory_context"] = context.get("memory_context", []) + [
                        {"content": it["content"], "type": it["type"],
                         "importance": int(it["importance"] * 10), "source": "graph"}
                        for it in _gm_items
                    ]
        except Exception:
            pass

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


# ══════════════════════════════════════════════════════════════════════
# GOLF ELITE v9 ENDPOINTS
# ══════════════════════════════════════════════════════════════════════

class _EliteAnalyzeRequest(BaseModel):
    frames: List[Dict[str, Any]] = []
    club:   str   = "unknown"
    fps:    float = 30.0
    lang:   str   = "es"

class _EliteLiveRequest(BaseModel):
    landmarks: List[Dict[str, Any]] = []
    lang:      str = "es"


@app.post("/api/golf/elite/analyze")
def golf_elite_analyze(
    req: _EliteAnalyzeRequest,
    current_user: dict = Depends(get_optional_user),
):
    uid = current_user["user_id"]
    try:
        ve    = _gve(uid)
        elite = _GolfSwingElite(ve)
        result = elite.analyze(req.frames, req.club, req.fps, req.lang)
        return result
    except Exception as e:
        return {"status": "error", "error": str(e)[:120]}


@app.post("/api/golf/elite/live")
def golf_elite_live(
    req: _EliteLiveRequest,
    current_user: dict = Depends(get_optional_user),
):
    uid = current_user["user_id"]
    try:
        ve    = _gve(uid)
        elite = _GolfSwingElite(ve)
        return {"status": "ok", **elite.live_cue(req.landmarks, req.lang)}
    except Exception as e:
        return {"status": "error", "cue": "Otra vez", "color": "#888"}


@app.get("/api/golf/elite/progress")
def golf_elite_progress(
    lang:   str = "es",
    limit:  int = 10,
    current_user: dict = Depends(get_optional_user),
):
    uid = current_user["user_id"]
    try:
        ve    = _gve(uid)
        elite = _GolfSwingElite(ve)
        hist  = ve.get_history(limit=limit)
        report = elite.progress_report(hist.get("items", []), lang)
        return {"status": "ok", **report}
    except Exception as e:
        return {"status": "error", "available": False, "error": str(e)[:80]}


# ══════════════════════════════════════════════════════════════════════
# FITNESS ENDPOINTS  (running, cycling, gym, tennis)
# ══════════════════════════════════════════════════════════════════════

class _WorkoutLog(BaseModel):
    date:        str = ""
    # running / cycling
    distance_km: Optional[float] = None
    duration_min: Optional[float] = None
    pace_min_km: Optional[float] = None
    avg_speed_kmh: Optional[float] = None
    elevation_m: Optional[float] = None
    heart_rate: Optional[int] = None
    route: Optional[str] = None
    # gym
    exercises: Optional[list] = None
    muscle_groups: Optional[str] = None
    # tennis
    result:   Optional[str] = None
    opponent: Optional[str] = None
    score:    Optional[str] = None
    # common
    notes: Optional[str] = None


@app.get("/api/fitness/{sport}/stats")
def fitness_stats(sport: str, current_user: dict = Depends(get_optional_user)):
    try:
        return {"status": "ok", **_fit(current_user["user_id"]).get_stats(sport)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.get("/api/fitness/{sport}/history")
def fitness_history(sport: str, limit: int = 10, offset: int = 0,
                    current_user: dict = Depends(get_optional_user)):
    try:
        return {"status": "ok", **_fit(current_user["user_id"]).get_history(sport, limit, offset)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.post("/api/fitness/{sport}/log")
def fitness_log(sport: str, body: _WorkoutLog,
                current_user: dict = Depends(get_optional_user)):
    try:
        data = {k: v for k, v in body.model_dump().items() if v is not None}
        entry = _fit(current_user["user_id"]).log_workout(sport, data)
        return {"status": "ok", "entry": entry}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.get("/api/fitness/{sport}/tips")
def fitness_tips(sport: str, current_user: dict = Depends(get_optional_user)):
    try:
        tips = _fit(current_user["user_id"]).get_tips(sport)
        return {"status": "ok", "sport": sport, "tips": tips}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.get("/api/fitness-overview")
def fitness_all_stats(current_user: dict = Depends(get_optional_user)):
    try:
        return {"status": "ok", "sports": _fit(current_user["user_id"]).all_stats()}
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ── Personality / tone endpoint ───────────────────────────────────────

class _PersonalityRequest(BaseModel):
    message: str
    context: Optional[str] = "general"
    tone:    Optional[str] = "professional"  # professional | coach | friendly


@app.post("/api/personality/respond")
def personality_respond(body: _PersonalityRequest,
                        current_user: dict = Depends(get_optional_user)):
    """Wrap a raw message with a chosen JARVIS personality tone."""
    tone_prompts = {
        "professional": (
            "You are JARVIS, a sharp, direct AI executive assistant. "
            "Respond in 1-3 sentences. Be concise, data-driven, and actionable. "
            "No filler. No pleasantries beyond a single opener."
        ),
        "coach": (
            "You are JARVIS in Coach mode. "
            "You motivate, challenge, and guide the user with energy and precision. "
            "Use short, punchy sentences. Be direct. End with an action or challenge."
        ),
        "friendly": (
            "You are JARVIS, a warm, encouraging AI companion. "
            "Be conversational, supportive, and clear. "
            "Keep it short and human."
        ),
    }
    system = tone_prompts.get(body.tone or "professional", tone_prompts["professional"])
    try:
        if not _OPENAI_AVAILABLE:
            return {"status": "ok", "reply": body.message, "tone": body.tone}
        client = _OpenAI()
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": body.message},
            ],
            max_tokens=200, temperature=0.7,
        )
        return {
            "status": "ok",
            "reply": resp.choices[0].message.content.strip(),
            "tone": body.tone,
        }
    except Exception as e:
        return {"status": "error", "error": str(e), "reply": body.message}


# ── Command intent router (for global command bar) ────────────────────
import unicodedata as _ud

def _normalize_cmd(text: str) -> str:
    """Lowercase + strip accents/diacritics for language-agnostic keyword matching."""
    nfkd = _ud.normalize("NFKD", text)
    stripped = "".join(c for c in nfkd if not _ud.combining(c))
    return stripped.lower().replace("¿", "").replace("¡", "")


class _CommandRequest(BaseModel):
    command: str
    context: Optional[str] = ""


# Each entry: intent → (tab, [english keywords], [spanish keywords])
_COMMAND_ROUTES = {
    "shopping_list": ("life", [
        "add to shopping", "shopping list", "buy milk", "buy eggs", "grocery",
        "add to groceries",
    ], [
        "agrega", "agregar", "lista del mercado", "lista de compras", "mercado",
        "comprar", "comida", "supermercado", "necesito comprar", "anade",
        "pon en la lista", "al mercado",
    ]),
    "reminder": ("life", [
        "remind me", "reminder", "set reminder", "dont forget", "alert me",
    ], [
        "recuerdame", "recuerda que", "recuerdame que", "no olvides",
        "avisame", "avísame", "recordatorio", "pon recordatorio",
    ]),
    "task": ("productivity", [
        "add task", "create task", "new task", "todo", "to-do",
        "plan my day", "plan day", "my tasks", "pending tasks",
    ], [
        "crear tarea", "nueva tarea", "tengo que", "debo hacer",
        "hay que", "apuntar", "anotar", "pendiente", "necesito",
        "me falta", "debo", "tarea",
    ]),
    "meeting": ("calendar", [
        "meeting", "schedule", "appointment",
    ], [
        "reunion", "cita", "agenda", "agendar", "programar", "llamada",
        "videollamada", "junta",
    ]),
    "calendar_query": ("calendar", [
        "what do i have today", "what is on my calendar", "my schedule",
        "show calendar", "today events", "upcoming events",
    ], [
        "que tengo hoy", "que hay hoy", "mi agenda", "mi calendario",
        "eventos de hoy", "que tengo mañana", "que hay mañana",
        "ver calendario", "muestra calendario",
    ]),
    "calendar_delete": ("calendar", [
        "delete event", "remove event", "cancel event",
    ], [
        "borra el evento", "borra ese evento", "elimina el evento",
        "elimina esa reunion", "cancela la reunion", "borra la reunion",
        "borra esa cita",
    ]),
    "email": ("outlook", [
        "email", "inbox", "check mail", "unread", "messages",
    ], [
        "correo", "correos", "email", "bandeja", "mensajes", "revisa correos",
        "lee correos", "tengo correos", "mail",
    ]),
    "market": ("markets", [
        "stock", "market", "price", "trade", "buy", "sell", "analyse", "analyze",
        "chart", "signal", "ticker", "analyse market", "analyze market",
    ], [
        "accion", "bolsa", "precio", "comprar", "vender", "analizar",
        "cotizacion", "invertir", "inversion", "analiza", "que hace",
    ]),
    "portfolio_query": ("markets", [
        "my portfolio", "portfolio summary", "how am i doing", "my investments",
        "daily pnl", "how much did i make", "how much did i lose",
        "portfolio risk", "biggest risk", "broker exposure", "my positions",
        "sector exposure", "paper trade", "paper trading",
    ], [
        "mi portafolio", "como voy hoy", "cuanto llevo", "cuanto perdi",
        "cuanto gane", "mi exposicion", "cual es mi riesgo", "mayor riesgo",
        "que broker", "que porcentaje tecnologia", "estoy concentrado",
        "como esta mi riesgo", "que harias en paper", "simula comprar",
        "simula reducir", "parte debil del portafolio", "analiza mi portafolio",
        "resumen del portafolio", "estado del portafolio",
    ]),
    "golf": ("golf", [
        "golf", "swing", "round", "handicap", "birdie", "par", "course", "putt",
    ], [
        "golf", "swing", "ronda", "hoyo", "green", "campo", "handicap",
        "birdie", "eagle", "putt", "putter",
    ]),
    "running": ("fitness", [
        "run", "jog", "km", "mile", "pace", "marathon", "5k", "10k",
    ], [
        "correr", "carrera", "kilómetros", "kilometros", "ritmo", "trote",
        "maraton", "corri", "sali a correr",
    ]),
    "cycling": ("fitness", [
        "bike", "cycle", "cycling", "ride", "cadence",
    ], [
        "bicicleta", "cicla", "ciclismo", "pedalear", "rodada", "salida en bici",
    ]),
    "gym": ("fitness", [
        "gym", "workout", "lift", "bench", "squat", "deadlift", "exercise", "weights",
    ], [
        "gimnasio", "ejercicio", "entreno", "entrenamiento", "pesas", "sentadilla",
        "press", "levantamiento", "fui al gym", "entrene",
    ]),
    "tennis": ("fitness", [
        "tennis", "match", "serve", "rally", "set",
    ], [
        "tenis", "partido", "saque", "raqueta", "volea", "jugar tenis",
    ]),
    "chat": ("chat", [
        "chat", "ask", "what", "who", "when", "how", "why", "help", "tell me",
    ], [
        "que", "quien", "como", "cuando", "por que", "ayuda", "dime", "explicame",
        "cuanto", "donde", "informacion",
    ]),
    "analytics": ("analytics", [
        "analytics", "stats", "statistics", "report", "summary", "dashboard",
    ], [
        "estadisticas", "reporte", "resumen", "analitica", "metricas",
        "rendimiento", "cuanto llevo",
    ]),
    "project": ("projects", [
        "project", "board", "kanban", "sprint",
    ], [
        "proyecto", "tablero", "sprint", "proyectos",
    ]),
    "news": ("intelligence", [
        "news", "headline", "article", "feed",
    ], [
        "noticias", "titulares", "articulo", "novedades",
    ]),
    "system": ("system", [
        "system", "health", "pipeline", "status", "agents",
    ], [
        "sistema", "salud del sistema", "estado", "agentes",
    ]),
}

# ══════════════════════════════════════════════════════════════════════
# CENTRAL BRAIN — Context Memory + Shared Executor + Command History
# ══════════════════════════════════════════════════════════════════════

_user_ctx:        dict = {}   # uid → {last_task, last_reminder, ...}
_cmd_history:     dict = {}   # uid → [{id, command, intent, ...}]
_pending_actions: dict = {}   # token → {uid, intent, payload, preview}
_undo_registry:   dict = {}   # action_id → callable

_FOLLOWUP_WORDS = [
    "cambialo", "cambia", "editalo", "edita", "borralo", "borra",
    "eliminalo", "elimina", "modifica", "ponle", "agregale",
    "change it", "edit it", "delete it", "update it",
]

def _get_ctx(uid: str) -> dict:
    if uid not in _user_ctx:
        _user_ctx[uid] = {}
    return _user_ctx[uid]

def _update_ctx(uid: str, module: str, entity: dict) -> None:
    ctx = _get_ctx(uid)
    ctx[f"last_{module}"] = entity
    ctx["last_module"]    = module

def _log_cmd(uid: str, command: str, intent: str, action_type: str,
             status: str, result: Optional[dict] = None,
             error: Optional[str] = None) -> str:
    cmd_id = _uuid_mod.uuid4().hex[:12]
    if uid not in _cmd_history:
        _cmd_history[uid] = []
    _cmd_history[uid].insert(0, {
        "id":          cmd_id,
        "command":     command,
        "intent":      intent,
        "action_type": action_type,
        "status":      status,
        "timestamp":   datetime.utcnow().isoformat(),
        "result":      result,
        "error":       error,
    })
    _cmd_history[uid] = _cmd_history[uid][:50]
    return cmd_id

def _register_undo(action_id: str, fn) -> None:
    _undo_registry[action_id] = fn


def _execute_command_action(raw: str, uid: str) -> dict:
    """
    Shared command executor used by command_route, voice_command, and /chat.
    Normalises → detects intent → handles follow-ups → executes → logs history.
    Returns enriched dict with action_id, preview, undo_available, reply.
    """
    import re as _re_cmd
    from datetime import timedelta as _td_cmd
    cmd = _normalize_cmd(raw)

    # ── Intent detection ─────────────────────────────────────────────
    matched_tab    = "chat"
    matched_intent = "general"
    confidence     = 0.5
    for intent, (tab, en_kws, es_kws) in _COMMAND_ROUTES.items():
        for kw in en_kws + es_kws:
            if kw in cmd:
                matched_tab    = tab
                matched_intent = intent
                confidence     = 0.85
                break
        if confidence > 0.5:
            break

    # ── Follow-up check ──────────────────────────────────────────────
    ctx = _get_ctx(uid)
    is_followup = any(w in cmd for w in _FOLLOWUP_WORDS)

    action_result:  Optional[dict] = None
    action_id      = ""
    preview        = ""
    undo_available = False
    reply          = ""

    # ── Execute action ────────────────────────────────────────────────
    if matched_intent == "shopping_list":
        try:
            parsed    = _parse_life_text(raw)
            item_name = parsed.get("title") or raw
            item_name = _re_cmd.sub(
                r"\s+(a la lista.*|al mercado.*|a la compra.*)$",
                "", item_name, flags=_re_cmd.IGNORECASE
            ).strip() or raw
            # Strip shopping command prefixes
            for _pfx in ["agrega ", "agregar ", "pon ", "add ", "buy ", "comprar ",
                         "necesito ", "falta ", "ponle ", "quiero "]:
                if item_name.lower().startswith(_pfx):
                    item_name = item_name[len(_pfx):].strip(); break
            created   = _life(uid).add_shopping(name=item_name)
            action_id = _uuid_mod.uuid4().hex[:10]
            preview   = f"Agregar '{item_name}' a la lista del mercado"
            item_id   = (created or {}).get("id", "")
            _register_undo(action_id, lambda _id=item_id: _life(uid).delete_shopping(_id))
            action_result  = {"module": "shopping", "item": created}
            undo_available = True
            _update_ctx(uid, "shopping", created or {})
            reply = f"Listo, '{item_name}' agregado a la lista. Deshacer disponible."
        except Exception as _e:
            action_result = {"module": "shopping", "error": str(_e)}
            reply = f"No pude agregar a la lista: {_e}"

    elif matched_intent == "reminder":
        try:
            parsed = _parse_life_text(raw)
            title  = parsed.get("title") or raw
            # Strip reminder command words
            for _pfx in ["recuerdame ", "recordatorio: ", "recuerda que ", "remind me ",
                         "set reminder ", "avisame ", "no olvides ", "recuerdame que "]:
                if title.lower().startswith(_pfx):
                    title = title[len(_pfx):].strip(); break
            due    = parsed.get("due") or ""
            if not due:
                due = (datetime.utcnow() + _td_cmd(hours=1)).isoformat()
            created   = _life(uid).add_reminder(title, due)
            action_id = _uuid_mod.uuid4().hex[:10]
            preview   = f"Crear recordatorio: '{title}'"
            item_id   = (created or {}).get("id", "")
            _register_undo(action_id, lambda _id=item_id: _life(uid).delete_reminder(_id))
            action_result  = {"module": "reminder", "item": created}
            undo_available = True
            _update_ctx(uid, "reminder", created or {})
            reply = f"Recordatorio creado: '{title}'. Listo."
        except Exception as _e:
            action_result = {"module": "reminder", "error": str(_e)}
            reply = f"No pude crear el recordatorio: {_e}"

    elif matched_intent == "task":
        try:
            parsed = _parse_life_text(raw)
            title  = parsed.get("title") or raw
            # Strip command words from title
            for _pfx in ["crea una tarea ", "crear tarea ", "nueva tarea ", "add task ",
                         "create task ", "tarea: ", "new task ", "debo hacer ",
                         "tengo que ", "hay que ", "apuntar ", "anotar "]:
                if title.lower().startswith(_pfx):
                    title = title[len(_pfx):].strip(); break
            t      = _ws(uid).add_task(title, priority="medium", day="today", category="general")
            action_id = _uuid_mod.uuid4().hex[:10]
            preview   = f"Crear tarea: '{title}'"
            task_id   = (t or {}).get("id", "")
            _register_undo(action_id, lambda _id=task_id: _ws(uid).delete_task(_id))
            action_result  = {"module": "task", "item": t}
            undo_available = True
            _update_ctx(uid, "task", t or {})
            reply = f"Tarea creada: '{title}'. Esta en tu lista de hoy."
        except Exception as _e:
            action_result = {"module": "task", "error": str(_e)}
            reply = f"No pude crear la tarea: {_e}"

    elif matched_intent == "meeting":
        try:
            parsed  = _parse_life_text(raw)
            title   = parsed.get("title") or raw
            for _pfx in ["agenda una reunion ", "agenda reunion ", "agendar reunion ",
                         "programa reunion ", "crea reunion ", "nueva reunion ",
                         "schedule meeting ", "add meeting ", "meeting: ",
                         "reunion con ", "reunion sobre "]:
                if title.lower().startswith(_pfx):
                    title = title[len(_pfx):].strip(); break
            dt_val  = parsed.get("due") or (datetime.utcnow() + _td_cmd(hours=1)).isoformat()
            created = _me(uid).add_meeting_datetime(title=title, datetime_value=dt_val)
            action_id     = _uuid_mod.uuid4().hex[:10]
            preview       = f"Agendar: '{title}'"
            action_result = {"module": "meeting", "item": created}
            _update_ctx(uid, "meeting", created or {})
            reply = f"Reunion agendada: '{title}'."
        except Exception as _e:
            action_result = {"module": "meeting", "error": str(_e)}
            reply = f"No pude agendar la reunion: {_e}"

    elif matched_intent == "calendar_query":
        try:
            events = _cal(uid).list_events(range_name="day")
            count  = len(events)
            if count == 0:
                reply = "No tienes eventos hoy en tu calendario."
            elif count == 1:
                ev = events[0]
                reply = f"Tienes 1 evento hoy: '{ev.get('title','?')}' a las {ev.get('start','?')[:16]}."
            else:
                titles = ", ".join(f"'{e.get('title','?')}'" for e in events[:3])
                more   = f" y {count-3} más" if count > 3 else ""
                reply  = f"Tienes {count} eventos hoy: {titles}{more}. Ver en Calendario."
            action_result = {"module": "calendar", "action": "query", "count": count}
        except Exception as _e:
            reply = f"No pude consultar el calendario: {_e}"
            action_result = {"module": "calendar", "error": str(_e)}

    elif matched_intent == "calendar_delete":
        ctx_meeting = ctx.get("last_meeting", {})
        last_title  = ctx_meeting.get("title", "")
        reply = (
            f"Para borrar '{last_title}', ve a Calendario, selecciona el evento y presiona Delete."
            if last_title else
            "Ve a Calendario, selecciona el evento que deseas borrar y presiona Delete. Pedirá confirmación."
        )
        action_result = {"module": "calendar", "action": "delete_prompt"}

    elif matched_intent == "email":
        cmd_l = cmd.lower()
        if any(w in cmd_l for w in ["muestra", "ver", "show", "inbox", "bandeja", "revisa", "lee"]):
            action_result = {"module": "email", "action": "show_inbox"}
            reply = "Abriendo tu bandeja de entrada de Outlook."
        elif any(w in cmd_l for w in ["ignora", "ignore"]):
            ctx_email = ctx.get("last_email", {})
            mid = ctx_email.get("message_id", "")
            reply = f"Para ignorar un correo específico, selecciónalo en la bandeja de Outlook."
            action_result = {"module": "email", "action": "ignore_prompt", "last_email_id": mid}
        elif any(w in cmd_l for w in ["responde", "responder", "reply", "contesta"]):
            ctx_email = ctx.get("last_email", {})
            mid = ctx_email.get("message_id", "")
            reply = "Para responder, selecciona el correo en la bandeja y usa el botón 'AI Reply'."
            action_result = {"module": "email", "action": "reply_prompt", "last_email_id": mid}
        else:
            action_result = {"module": "email", "action": "show_inbox"}
            reply = "Abriendo Outlook — tus correos más recientes."

    elif matched_intent == "portfolio_query":
        try:
            matched_tab = "markets"
            if _PORTFOLIO_AVAILABLE and _unified_portfolio and _portfolio_intel:
                snapshot = _build_unified_snapshot()
                intel    = _portfolio_intel.analyze(snapshot)
                total    = snapshot.get("total_portfolio_value", 0)
                daily    = snapshot.get("total_daily_pnl", 0)
                score    = intel.get("portfolio_score", 0)
                risk     = intel.get("risk_level", "unknown")
                summary  = intel.get("summary", "")
                top_risk = intel.get("top_risks", [""])
                action_result = {"module": "portfolio", "snapshot": snapshot, "analysis": intel}
                reply = (
                    f"Portafolio: ${total:,.0f} | P&L hoy: ${daily:+,.0f} | "
                    f"Score: {score}/100 ({risk.upper()}). {summary[:120]}"
                )
                if top_risk and top_risk[0]:
                    reply += f" — {top_risk[0]}"
            else:
                reply = "Módulo de portafolio no disponible. Verifica los conectores IBKR y Hapi."
                action_result = {"module": "portfolio", "error": "modules_unavailable"}
        except Exception as _e:
            action_result = {"module": "portfolio", "error": str(_e)}
            reply = f"No pude consultar el portafolio: {_e}"

    elif matched_intent in ("market", "analyze"):
        sym = _extract_symbol(raw)
        if sym:
            try:
                data          = brain.trader(sym)
                action_result = {"module": "market", "data": data, "symbol": sym}
                matched_tab   = "markets"
                _update_ctx(uid, "analysis", {"symbol": sym, **(data or {})})
                sig = (data or {}).get("signal", (data or {}).get("trend", ""))
                prc = (data or {}).get("price", "")
                reply = f"{sym}: {sig} — ${prc}. Ver analisis en Markets."
            except Exception as _e:
                action_result = {"module": "market", "error": str(_e)}

    # ── Log ──────────────────────────────────────────────────────────
    err_msg = (action_result or {}).get("error")
    status  = "error" if err_msg else ("executed" if action_result else "routed")
    cmd_id  = _log_cmd(uid, raw, matched_intent,
                       (action_result or {}).get("module", matched_intent),
                       status, action_result, err_msg)

    return {
        "intent":        matched_intent,
        "tab":           matched_tab,
        "confidence":    confidence,
        "action_result": action_result,
        "action_id":     action_id,
        "action_type":   (action_result or {}).get("module", matched_intent),
        "preview":       preview,
        "status":        status,
        "undo_available": undo_available,
        "reply":         reply,
        "cmd_id":        cmd_id,
        "command":       raw,
    }


@app.post("/api/command/route")
def command_route(body: _CommandRequest,
                  current_user: dict = Depends(get_optional_user)):
    """
    Central command router — single source of truth for all action commands.
    Used by global command bar, voice, and chat.
    """
    raw = body.command
    uid = current_user["user_id"]

    exec_result = _execute_command_action(raw, uid)

    # ── AI reply (enrich with human language if no action reply) ─────
    reply = exec_result["reply"]
    if not reply:
        try:
            ctx    = {"user_id": uid, "action_executed": exec_result["action_result"]}
            ai_res = ai_orchestrator.route(raw, ctx)
            reply  = ai_res.get("reply") or ai_res.get("response") or ai_res.get("answer") or ""
        except Exception:
            pass
    if not reply:
        reply = f"Entendido — abriendo {exec_result['tab']}…"

    return {
        "status":        "ok",
        "tab":           exec_result["tab"],
        "intent":        exec_result["intent"],
        "confidence":    exec_result["confidence"],
        "reply":         reply,
        "command":       raw,
        "action_result": exec_result["action_result"],
        "action_id":     exec_result["action_id"],
        "action_type":   exec_result["action_type"],
        "preview":       exec_result["preview"],
        "undo_available": exec_result["undo_available"],
        "cmd_id":        exec_result["cmd_id"],
    }


# ── Command history ───────────────────────────────────────────────────
@app.get("/api/command/history")
def command_history(limit: int = 20,
                    current_user: dict = Depends(get_optional_user)):
    uid = current_user["user_id"]
    items = (_cmd_history.get(uid) or [])[:limit]
    return {"status": "ok", "items": items, "count": len(items)}


# ── Undo last action ──────────────────────────────────────────────────
@app.post("/api/command/undo/{action_id}")
def command_undo(action_id: str,
                 current_user: dict = Depends(get_optional_user)):
    fn = _undo_registry.pop(action_id, None)
    if fn is None:
        return JSONResponse({"status": "error", "error": "Action not found or already undone"},
                            status_code=404)
    try:
        fn()
        return {"status": "ok", "message": "Accion deshecha correctamente."}
    except Exception as exc:
        return JSONResponse({"status": "error", "error": str(exc)}, status_code=500)


# ── Commander Brief (Daily Executive Summary) ─────────────────────────
@app.get("/api/commander/brief")
async def commander_brief(current_user: dict = Depends(get_optional_user)):
    """Aggregate daily executive brief from all modules."""
    uid   = current_user["user_id"]
    today = datetime.now().strftime("%A %d %B %Y")

    tasks_open: list = []
    reminders:  list = []
    events:     list = []
    payments:   list = []
    news_items: list = []
    market_sig: dict = {}

    try:
        home       = _ws(uid).home(_user_name(uid))
        all_tasks  = home.get("tasks", [])
        tasks_open = [t for t in all_tasks if not t.get("done")][:4]
    except Exception:
        pass

    try:
        life_data  = _life(uid).get_reminders(only_pending=True)
        reminders  = (life_data or [])[:3]
    except Exception:
        pass

    try:
        pay_data = _life(uid).get_payments(only_pending=True)
        payments = (pay_data or [])[:3]
    except Exception:
        pass

    try:
        cal_data = CalendarEngine(uid).events_for_today()
        events   = (cal_data or [])[:4]
    except Exception:
        pass

    try:
        raw_news   = news_engine.fetch_categorized(max_per_category=2)
        news_items = (raw_news or [])[:5] if isinstance(raw_news, list) else []
    except Exception:
        pass

    try:
        ctx_analysis = _get_ctx(uid).get("last_analysis", {})
        if ctx_analysis.get("symbol"):
            market_sig = {
                "symbol": ctx_analysis.get("symbol"),
                "signal": ctx_analysis.get("signal"),
                "price":  ctx_analysis.get("price"),
            }
    except Exception:
        pass

    priority_msg = ""
    if tasks_open:
        priority_msg = tasks_open[0].get("text", "")
    elif reminders:
        priority_msg = f"Recordatorio: {(reminders[0] or {}).get('title', '')}"

    return {
        "status": "ok",
        "date":   today,
        "summary": {
            "tasks_open":      len(tasks_open),
            "top_tasks":       tasks_open,
            "reminders":       reminders,
            "payments":        payments,
            "events":          events,
            "news":            news_items,
            "market_signal":   market_sig,
            "priority_message": priority_msg,
        },
    }


# ── Global Command Search ─────────────────────────────────────────────
@app.get("/api/command/search")
def command_search(q: str = "",
                   current_user: dict = Depends(get_optional_user)):
    """Search across tasks, reminders, shopping, news. q = query string."""
    uid = current_user["user_id"]
    if not q.strip():
        return {"status": "ok", "results": [], "query": q}

    ql = q.lower()
    results: list = []

    try:
        home   = _ws(uid).home(_user_name(uid))
        tasks  = [t for t in home.get("tasks", []) if ql in (t.get("text") or "").lower()]
        results += [{"type": "task", "label": t.get("text"), "id": t.get("id")} for t in tasks[:3]]
    except Exception:
        pass

    try:
        rems = _life(uid).get_reminders()
        results += [{"type": "reminder", "label": r.get("title"), "id": r.get("id")}
                    for r in (rems or []) if ql in (r.get("title") or "").lower()][:3]
    except Exception:
        pass

    try:
        shop = _life(uid).get_shopping()
        results += [{"type": "shopping", "label": s.get("name"), "id": s.get("id")}
                    for s in (shop or []) if ql in (s.get("name") or "").lower()][:3]
    except Exception:
        pass

    try:
        raw_news   = news_engine.fetch_categorized(max_per_category=6)
        news_items = raw_news if isinstance(raw_news, list) else []
        results   += [{"type": "news", "label": n.get("title"), "url": n.get("url")}
                      for n in news_items if ql in (n.get("title") or "").lower()][:3]
    except Exception:
        pass

    return {"status": "ok", "results": results[:12], "query": q}


# ══════════════════════════════════════════════════════════════════════
# DEMO MODE + SEED  (Phase 6Y)
# ══════════════════════════════════════════════════════════════════════

from core.demo_engine import DemoEngine as _DemoEngine

_MODE_FILE = BASE_DIR / "data" / "jarvis_mode.json"

def _read_mode() -> dict:
    try:
        return json.loads(_MODE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"mode": "demo", "seeded": False}

def _write_mode(data: dict) -> None:
    _MODE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _MODE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


@app.get("/api/mode")
def get_mode(current_user: dict = Depends(get_optional_user)):
    return {"status": "ok", **_read_mode()}


class _ModeSet(BaseModel):
    mode: str  # "demo" or "real"


@app.post("/api/mode")
def set_mode(body: _ModeSet, current_user: dict = Depends(get_optional_user)):
    d = _read_mode()
    d["mode"] = body.mode
    _write_mode(d)
    return {"status": "ok", "mode": body.mode}


@app.post("/api/demo/seed")
def demo_seed(
    force: bool = False,
    current_user: dict = Depends(get_optional_user),
):
    """Seed demo data for the current user. Safe to call multiple times."""
    uid  = current_user["user_id"]
    eng  = _DemoEngine(uid)
    report = eng.seed_all(force=force)
    d = _read_mode()
    d["seeded"] = True
    d["mode"]   = "demo"
    _write_mode(d)
    return {"status": "ok", "report": report, "mode": "demo"}


@app.get("/api/demo/status")
def demo_status(current_user: dict = Depends(get_optional_user)):
    """Check whether demo data has been seeded and what mode is active."""
    mode_data = _read_mode()
    return {
        "status": "ok",
        "mode":   mode_data.get("mode", "demo"),
        "seeded": mode_data.get("seeded", False),
    }


# ── 1-Click Action endpoints (Phase 6Y) ──────────────────────────────

class _QuickActionRequest(BaseModel):
    action: str          # plan_day | analyze_market | create_tasks | start_workout
    params: Optional[dict] = None


@app.post("/api/quick-action")
def quick_action(body: _QuickActionRequest,
                 current_user: dict = Depends(get_optional_user)):
    """Execute a 1-click action and return structured result + next step."""
    uid = current_user["user_id"]
    action = body.action

    _QUICK_ACTIONS = {
        "plan_day": {
            "label":    "Plan My Day",
            "message":  "Good morning! Here's your day plan: check your top tasks, review today's meetings, and prioritise your 3 most important items. Start with the hardest task first (eat the frog). Your focus window is 90 min — protect it.",
            "tab":      "productivity",
            "chips":    ["View tasks", "Check calendar", "Ask JARVIS for priorities"],
        },
        "analyze_market": {
            "label":    "Market Analysis",
            "message":  "Market analysis initiated. Check the Markets tab for live indices, run the Trader Analysis for any symbol, and review AI-generated signals. Key levels and recommended setups are updated in real-time.",
            "tab":      "markets",
            "chips":    ["Go to Markets", "Analyse AAPL", "View signals"],
        },
        "create_tasks": {
            "label":    "Create Tasks",
            "message":  "Ready to capture your priorities! Add tasks in the Productivity tab, or tell me what you need to do and I'll structure them for you. Use the AI task generator in Projects for complex work.",
            "tab":      "productivity",
            "chips":    ["Add task", "AI task generation", "View backlog"],
        },
        "start_workout": {
            "label":    "Start Workout",
            "message":  "Let's go! Choose your workout type: Running, Cycling, Gym, or Tennis. Log your session afterward to track progress and get personalised coaching tips from JARVIS.",
            "tab":      "fitness",
            "chips":    ["Log a run", "Log gym session", "View this week's stats"],
        },
    }

    if action not in _QUICK_ACTIONS:
        raise HTTPException(status_code=400, detail=f"Unknown action '{action}'")

    result = _QUICK_ACTIONS[action]

    # Try to enrich the message with live orchestrator data
    try:
        live = ai_orchestrator.route(result["message"], {"user_id": uid})
        enriched = live.get("reply") or live.get("response") or ""
        if enriched and len(enriched) > 30:
            result = {**result, "message": enriched}
    except Exception:
        pass

    return {"status": "ok", **result, "action": action}


# ══════════════════════════════════════════════════════════════════════
# LIFE AUTOMATION SYSTEM  (Phase 6Z-4)
# ══════════════════════════════════════════════════════════════════════

import asyncio as _asyncio
from core.life_engine import LifeEngine as _LifeEngine, parse_life_text as _parse_life_text

_life_cache: dict = {}

def _life(user_id: str) -> _LifeEngine:
    if user_id not in _life_cache:
        path = BASE_DIR / "data" / "life" / user_id
        _life_cache[user_id] = _LifeEngine(str(path), user_id)
    return _life_cache[user_id]


class _LifeTaskReq(BaseModel):
    text: str

class _ReminderReq(BaseModel):
    title: str
    due: str
    repeat: Optional[str] = None
    notes: str = ""

class _ShoppingReq(BaseModel):
    name: str
    qty: int = 1
    category: str = "general"
    notes: str = ""

class _CallReq(BaseModel):
    contact: str
    due: str
    notes: str = ""
    phone: str = ""

class _PaymentReq(BaseModel):
    title: str
    amount: float
    due: str
    recurrence: Optional[str] = None
    currency: str = "COP"


@app.post("/api/life/task")
def life_task(body: _LifeTaskReq, current_user: dict = Depends(get_optional_user)):
    uid    = current_user["user_id"]
    parsed = _parse_life_text(body.text)
    engine = _life(uid)
    created = []

    if parsed["type"] == "payment":
        item = engine.add_payment(parsed["title"], parsed["amount"] or 0.0, parsed["due"])
        created.append({"module": "payment", "item": item})
        try:
            from datetime import datetime as _dt, timedelta as _td
            remind_dt = (_dt.fromisoformat(parsed["due"]) - _td(days=1)).isoformat()
            rem = engine.add_reminder(f"Pagar: {parsed['title']}", remind_dt)
            created.append({"module": "reminder", "item": rem})
        except Exception:
            pass
    elif parsed["type"] == "call":
        item = engine.add_call(parsed["contact"] or parsed["title"], parsed["due"], parsed["raw"])
        created.append({"module": "call", "item": item})
    elif parsed["type"] == "shopping":
        item = engine.add_shopping(name=parsed["title"])
        created.append({"module": "shopping", "item": item})
    else:
        item = engine.add_reminder(parsed["title"], parsed["due"], notes=parsed["raw"])
        created.append({"module": "reminder", "item": item})

    return {"status": "ok", "parsed": parsed, "created": created}


@app.post("/api/life/reminder")
def add_reminder(body: _ReminderReq, current_user: dict = Depends(get_optional_user)):
    from core.life_engine import _parse_due
    due = body.due if "T" in body.due else _parse_due(body.due)
    item = _life(current_user["user_id"]).add_reminder(body.title, due, body.repeat, body.notes)
    return {"status": "ok", "item": item}

@app.get("/api/life/reminders")
def get_reminders(include_done: bool = False, current_user: dict = Depends(get_optional_user)):
    items = _life(current_user["user_id"]).get_reminders(include_done)
    return {"status": "ok", "items": items, "count": len(items)}

@app.post("/api/life/reminder/{item_id}/done")
def complete_reminder(item_id: str, current_user: dict = Depends(get_optional_user)):
    item = _life(current_user["user_id"]).complete_reminder(item_id)
    if not item: raise HTTPException(404, "Reminder not found")
    return {"status": "ok", "item": item}

@app.delete("/api/life/reminder/{item_id}")
def delete_reminder(item_id: str, current_user: dict = Depends(get_optional_user)):
    ok = _life(current_user["user_id"]).delete_reminder(item_id)
    return {"status": "ok" if ok else "not_found"}


@app.post("/api/life/shopping")
def add_shopping(body: _ShoppingReq, current_user: dict = Depends(get_optional_user)):
    item = _life(current_user["user_id"]).add_shopping(body.name, body.qty, body.category, body.notes)
    return {"status": "ok", "item": item}

@app.get("/api/life/shopping")
def get_shopping(current_user: dict = Depends(get_optional_user)):
    items = _life(current_user["user_id"]).get_shopping()
    return {"status": "ok", "items": items, "count": len(items)}

@app.post("/api/life/shopping/{item_id}/toggle")
def toggle_shopping(item_id: str, current_user: dict = Depends(get_optional_user)):
    item = _life(current_user["user_id"]).toggle_shopping(item_id)
    if not item: raise HTTPException(404, "Item not found")
    return {"status": "ok", "item": item}

@app.delete("/api/life/shopping/{item_id}")
def delete_shopping(item_id: str, current_user: dict = Depends(get_optional_user)):
    ok = _life(current_user["user_id"]).delete_shopping(item_id)
    return {"status": "ok" if ok else "not_found"}

@app.post("/api/life/shopping/clear-checked")
def clear_checked_shopping(current_user: dict = Depends(get_optional_user)):
    n = _life(current_user["user_id"]).clear_checked()
    return {"status": "ok", "cleared": n}


@app.post("/api/life/call")
def add_call(body: _CallReq, current_user: dict = Depends(get_optional_user)):
    from core.life_engine import _parse_due
    due = body.due if "T" in body.due else _parse_due(body.due)
    item = _life(current_user["user_id"]).add_call(body.contact, due, body.notes, body.phone)
    return {"status": "ok", "item": item}

@app.get("/api/life/calls")
def get_calls(include_done: bool = False, current_user: dict = Depends(get_optional_user)):
    items = _life(current_user["user_id"]).get_calls(include_done)
    return {"status": "ok", "items": items, "count": len(items)}

@app.post("/api/life/call/{item_id}/done")
def complete_call(item_id: str, current_user: dict = Depends(get_optional_user)):
    item = _life(current_user["user_id"]).complete_call(item_id)
    if not item: raise HTTPException(404, "Call not found")
    return {"status": "ok", "item": item}

@app.delete("/api/life/call/{item_id}")
def delete_call(item_id: str, current_user: dict = Depends(get_optional_user)):
    ok = _life(current_user["user_id"]).delete_call(item_id)
    return {"status": "ok" if ok else "not_found"}


@app.post("/api/life/payment")
def add_payment(body: _PaymentReq, current_user: dict = Depends(get_optional_user)):
    from core.life_engine import _parse_due
    due = body.due if "T" in body.due else _parse_due(body.due)
    item = _life(current_user["user_id"]).add_payment(
        body.title, body.amount, due, body.recurrence, body.currency)
    return {"status": "ok", "item": item}

@app.get("/api/life/payments")
def get_payments(include_done: bool = False, current_user: dict = Depends(get_optional_user)):
    items = _life(current_user["user_id"]).get_payments(include_done)
    return {"status": "ok", "items": items, "count": len(items)}

@app.post("/api/life/payment/{item_id}/done")
def complete_payment(item_id: str, current_user: dict = Depends(get_optional_user)):
    item = _life(current_user["user_id"]).complete_payment(item_id)
    if not item: raise HTTPException(404, "Payment not found")
    return {"status": "ok", "item": item}

@app.delete("/api/life/payment/{item_id}")
def delete_payment(item_id: str, current_user: dict = Depends(get_optional_user)):
    ok = _life(current_user["user_id"]).delete_payment(item_id)
    return {"status": "ok" if ok else "not_found"}


@app.get("/api/life/summary")
def life_summary(current_user: dict = Depends(get_optional_user)):
    return {"status": "ok", **_life(current_user["user_id"]).summary()}


async def _reminder_scheduler() -> None:
    while True:
        try:
            engine = _life("owner")
            for item in engine.check_due():
                try:
                    _notif("owner").create(
                        title=f"Recordatorio: {item['title']}",
                        message=item.get("notes", ""),
                        notif_type="reminder",
                        priority="high",
                        action_url="life",
                    )
                    engine.complete_reminder(item["id"])
                except Exception:
                    pass
        except Exception:
            pass
        await _asyncio.sleep(60)


async def _graph_memory_startup_backfill() -> None:
    """On startup, auto-seed graph memory if ACTIVE and store is empty."""
    _gm_log = logging.getLogger("jarvis.graph_memory")
    try:
        if not _GRAPH_MEM_AVAILABLE or not _graph_mem.is_enabled():
            return
        engine = _graph_mem.get_engine()
        if engine is None or engine.node_count() > 0:
            _gm_log.info("Graph Memory: %d nodes already in store — skipping backfill", engine.node_count() if engine else 0)
            return
        _gm_log.info("Graph Memory: store empty — running startup backfill")
        from opsx.memory.backfill import run_backfill
        result = await run_backfill(engine)
        _gm_log.info("Graph Memory backfill complete: %d nodes from %s", result.get("nodes_upserted", 0), result.get("modules_run", []))
    except Exception as exc:
        logging.getLogger("jarvis.graph_memory").warning("Startup backfill failed (non-fatal): %s", exc)


@app.on_event("startup")
async def _start_scheduler() -> None:
    _asyncio.create_task(_reminder_scheduler())
    asyncio.create_task(_calendar_reminder_scheduler())
    asyncio.create_task(_graph_memory_startup_backfill())


_OUTLOOK_POLL_INTERVAL = int(os.getenv("OUTLOOK_POLL_INTERVAL", "90"))  # seconds

async def _outlook_smart_poll_loop() -> None:
    """
    Smart polling loop — primary email delivery for personal MSA accounts.
    - Runs every OUTLOOK_POLL_INTERVAL seconds (default 90s).
    - Only fetches unread, skips already-processed message IDs (zero token waste).
    - Does NOT run AI twice on the same message.
    - Only activates when a valid token exists.
    """
    _plog = logging.getLogger("jarvis.outlook.poll_loop")
    _plog.info("Smart polling loop started — interval=%ds", _OUTLOOK_POLL_INTERVAL)
    while True:
        try:
            await asyncio.sleep(_OUTLOOK_POLL_INTERVAL)
            if not _OUTLOOK_AVAILABLE:
                continue
            # Only poll if someone is authenticated
            uid = "owner"
            if not _ms_token_store.is_authenticated(uid):
                continue
            try:
                messages = await _ms_list_inbox(limit=10, user_id=uid, unread_only=True)
            except Exception as exc:
                _plog.debug("Poll failed (will retry): %s", exc)
                continue
            new_count = 0
            for msg in messages:
                msg_id = msg.get("id") or msg.get("message_id")
                if not msg_id or _ms_email_store.get(msg_id):
                    continue   # already processed — zero AI calls
                try:
                    full = await _ms_fetch_email(msg_id, uid)
                    if full:
                        result = await _ms_process_email(full)
                        await _ms_store_email(result)
                        new_count += 1
                except Exception as exc:
                    _plog.debug("Poll: error processing msg=%s: %s", msg_id, exc)
            if new_count:
                _plog.info("Smart poll: %d new email(s) ingested", new_count)
        except asyncio.CancelledError:
            break
        except Exception as exc:
            _plog.warning("Poll loop error (non-fatal): %s", exc)


@app.on_event("startup")
async def _start_outlook_services() -> None:
    if not _OUTLOOK_AVAILABLE:
        return
    # Register the email processing handler on the event queue
    async def _handle_new_email(payload: dict) -> None:
        msg_id  = payload.get("message_id")
        user_id = payload.get("user_id", "owner")
        if not msg_id:
            return
        email = await _ms_fetch_email(msg_id, user_id)
        if not email:
            logging.getLogger("jarvis.outlook").warning("Could not fetch message %s", msg_id)
            return
        result = await _ms_process_email(email)
        await _ms_store_email(result)
        logging.getLogger("jarvis.outlook").info(
            "Email processed and stored: %s priority=%s", msg_id, result.get("priority")
        )

    _ms_event_queue.register("new_email", _handle_new_email)
    _ms_event_queue.start()
    _ms_start_renewal()
    logging.getLogger("jarvis").info("Outlook event queue + renewal loop started")
    # Start smart polling loop (primary email delivery for personal MSA accounts)
    asyncio.create_task(_outlook_smart_poll_loop())


@app.on_event("shutdown")
async def _stop_outlook_services() -> None:
    if not _OUTLOOK_AVAILABLE:
        return
    await _ms_stop_renewal()
    await _ms_event_queue.stop()


# ══════════════════════════════════════════════════════════════════════
# FAMILY AGENT ENDPOINTS  (Phase 6Z-6)
# ══════════════════════════════════════════════════════════════════════

class _FamilyMemberReq(BaseModel):
    name: str
    relation: str = "other"
    birthday: str = ""
    phone: str = ""
    email: str = ""
    notes: str = ""

class _FamilyEventReq(BaseModel):
    title: str
    date: str
    event_type: str = "family"
    members: list = []
    notes: str = ""
    repeat_yearly: bool = False

class _FamilyNoteReq(BaseModel):
    content: str
    member_id: str = ""
    tags: list = []


@app.get("/api/family/summary")
def family_summary(current_user: dict = Depends(get_optional_user)):
    return {"status": "ok", **_family(current_user["user_id"]).summary()}

@app.get("/api/family/members")
def family_members(current_user: dict = Depends(get_optional_user)):
    items = _family(current_user["user_id"]).get_members()
    return {"status": "ok", "items": items, "count": len(items)}

@app.post("/api/family/members")
def add_family_member(body: _FamilyMemberReq, current_user: dict = Depends(get_optional_user)):
    item = _family(current_user["user_id"]).add_member(
        body.name, body.relation, body.birthday, body.phone, body.email, body.notes)
    return {"status": "ok", "item": item}

@app.delete("/api/family/members/{member_id}")
def delete_family_member(member_id: str, current_user: dict = Depends(get_optional_user)):
    ok = _family(current_user["user_id"]).delete_member(member_id)
    return {"status": "ok" if ok else "not_found"}

@app.get("/api/family/events")
def family_events(upcoming_days: int = 90, current_user: dict = Depends(get_optional_user)):
    items = _family(current_user["user_id"]).get_events(upcoming_days)
    return {"status": "ok", "items": items, "count": len(items)}

@app.post("/api/family/events")
def add_family_event(body: _FamilyEventReq, current_user: dict = Depends(get_optional_user)):
    item = _family(current_user["user_id"]).add_event(
        body.title, body.date, body.event_type, body.members, body.notes, body.repeat_yearly)
    return {"status": "ok", "item": item}

@app.post("/api/family/events/{event_id}/done")
def complete_family_event(event_id: str, current_user: dict = Depends(get_optional_user)):
    item = _family(current_user["user_id"]).complete_event(event_id)
    if not item: raise HTTPException(404, "Event not found")
    return {"status": "ok", "item": item}

@app.delete("/api/family/events/{event_id}")
def delete_family_event(event_id: str, current_user: dict = Depends(get_optional_user)):
    ok = _family(current_user["user_id"]).delete_event(event_id)
    return {"status": "ok" if ok else "not_found"}

@app.get("/api/family/notes")
def family_notes(member_id: str = "", current_user: dict = Depends(get_optional_user)):
    items = _family(current_user["user_id"]).get_notes(member_id)
    return {"status": "ok", "items": items, "count": len(items)}

@app.post("/api/family/notes")
def add_family_note(body: _FamilyNoteReq, current_user: dict = Depends(get_optional_user)):
    item = _family(current_user["user_id"]).add_note(body.content, body.member_id, body.tags)
    return {"status": "ok", "item": item}

@app.delete("/api/family/notes/{note_id}")
def delete_family_note(note_id: str, current_user: dict = Depends(get_optional_user)):
    ok = _family(current_user["user_id"]).delete_note(note_id)
    return {"status": "ok" if ok else "not_found"}


# ══════════════════════════════════════════════════════════════════════
# OFFICE AGENT ENDPOINTS  (Phase 6Z-6)
# ══════════════════════════════════════════════════════════════════════

class _ColleagueReq(BaseModel):
    name: str
    role: str = ""
    department: str = ""
    email: str = ""
    phone: str = ""
    notes: str = ""

class _OfficeTaskReq(BaseModel):
    title: str
    due: str = ""
    priority: str = "medium"
    assigned_to: str = ""
    project: str = ""
    notes: str = ""

class _ExpenseReq(BaseModel):
    title: str
    amount: float
    category: str = "other"
    currency: str = "COP"
    date: str = ""
    reimbursable: bool = True
    notes: str = ""


@app.get("/api/office/summary")
def office_summary(current_user: dict = Depends(get_optional_user)):
    return {"status": "ok", **_office(current_user["user_id"]).summary()}

@app.get("/api/office/colleagues")
def office_colleagues(current_user: dict = Depends(get_optional_user)):
    items = _office(current_user["user_id"]).get_colleagues()
    return {"status": "ok", "items": items, "count": len(items)}

@app.post("/api/office/colleagues")
def add_colleague(body: _ColleagueReq, current_user: dict = Depends(get_optional_user)):
    item = _office(current_user["user_id"]).add_colleague(
        body.name, body.role, body.department, body.email, body.phone, body.notes)
    return {"status": "ok", "item": item}

@app.delete("/api/office/colleagues/{colleague_id}")
def delete_colleague(colleague_id: str, current_user: dict = Depends(get_optional_user)):
    ok = _office(current_user["user_id"]).delete_colleague(colleague_id)
    return {"status": "ok" if ok else "not_found"}

@app.get("/api/office/tasks")
def office_tasks(include_done: bool = False, current_user: dict = Depends(get_optional_user)):
    items = _office(current_user["user_id"]).get_tasks(include_done=include_done)
    return {"status": "ok", "items": items, "count": len(items)}

@app.post("/api/office/tasks")
def add_office_task(body: _OfficeTaskReq, current_user: dict = Depends(get_optional_user)):
    item = _office(current_user["user_id"]).add_task(
        body.title, body.due, body.priority, body.assigned_to, body.project, body.notes)
    return {"status": "ok", "item": item}

@app.post("/api/office/tasks/{task_id}/status")
def update_office_task_status(task_id: str, status: str, current_user: dict = Depends(get_optional_user)):
    item = _office(current_user["user_id"]).update_task_status(task_id, status)
    if not item: raise HTTPException(404, "Task not found")
    return {"status": "ok", "item": item}

@app.delete("/api/office/tasks/{task_id}")
def delete_office_task(task_id: str, current_user: dict = Depends(get_optional_user)):
    ok = _office(current_user["user_id"]).delete_task(task_id)
    return {"status": "ok" if ok else "not_found"}

@app.get("/api/office/expenses")
def office_expenses(include_closed: bool = False, current_user: dict = Depends(get_optional_user)):
    items = _office(current_user["user_id"]).get_expenses(include_closed)
    return {"status": "ok", "items": items, "count": len(items)}

@app.post("/api/office/expenses")
def add_expense(body: _ExpenseReq, current_user: dict = Depends(get_optional_user)):
    item = _office(current_user["user_id"]).add_expense(
        body.title, body.amount, body.category, body.currency,
        body.date, body.reimbursable, body.notes)
    return {"status": "ok", "item": item}

@app.post("/api/office/expenses/{expense_id}/status")
def update_expense_status(expense_id: str, status: str, current_user: dict = Depends(get_optional_user)):
    item = _office(current_user["user_id"]).update_expense_status(expense_id, status)
    if not item: raise HTTPException(404, "Expense not found")
    return {"status": "ok", "item": item}

@app.delete("/api/office/expenses/{expense_id}")
def delete_expense(expense_id: str, current_user: dict = Depends(get_optional_user)):
    ok = _office(current_user["user_id"]).delete_expense(expense_id)
    return {"status": "ok" if ok else "not_found"}


# ══════════════════════════════════════════════════════════════════════
# OUTLOOK / MICROSOFT GRAPH INTEGRATION
# ══════════════════════════════════════════════════════════════════════

def _outlook_guard():
    if not _OUTLOOK_AVAILABLE:
        raise HTTPException(503, "Outlook integration not available")


# ── OAuth2 ────────────────────────────────────────────────────────────

@app.get("/auth/microsoft/login")
async def ms_login():
    """Redirect the user to Microsoft login. Returns JSON error if misconfigured."""
    _outlook_guard()
    from fastapi.responses import RedirectResponse
    try:
        url, _state = _ms_login_url()
    except ValueError as exc:
        # Never generate a URL with blank client_id — return actionable error
        return JSONResponse({"error": str(exc), "configured": False}, status_code=400)
    return RedirectResponse(url)


@app.get("/auth/microsoft/callback")
async def ms_callback(code: str = "", state: str = "", error: str = "", error_description: str = ""):
    """Handle the OAuth2 callback from Microsoft."""
    _outlook_guard()
    from fastapi.responses import RedirectResponse, HTMLResponse
    if error:
        msg = error_description or error
        return HTMLResponse(
            f'<html><body style="font-family:sans-serif;padding:30px;background:#0f1117;color:#fff">'
            f'<h2>⚠ Microsoft Auth Error</h2><p>{msg}</p>'
            f'<a href="/dashboard" style="color:#44f0ff">← Back to JARVIS</a></body></html>',
            status_code=400,
        )
    if not code:
        raise HTTPException(400, "Missing authorization code")

    user_id = _ms_token_store.consume_state(state)
    if not user_id:
        raise HTTPException(400, "Invalid or expired OAuth state — try connecting again")

    try:
        tokens = await _ms_exchange_code(code)
    except Exception as exc:
        raise HTTPException(500, f"Token exchange failed: {exc}")

    _ms_token_store.save(user_id, tokens)
    print(f"[AUTH] Callback complete — token stored for user={user_id}, access_token_prefix={tokens.get('access_token','')[:20]}...")
    asyncio.create_task(_ms_create_sub(user_id))

    return RedirectResponse("/dashboard?outlook=connected")


@app.get("/api/outlook/status")
async def outlook_status(current_user: dict = Depends(get_optional_user)):
    """
    Return Outlook configuration and connection status — never crashes.

    Status values:
      "disconnected"      — no token stored, user must authenticate
      "expired"           — token present but rejected by Graph after refresh
      "connected_polling" — Graph /me returned 200, real connection confirmed
    """
    if not _OUTLOOK_AVAILABLE:
        return {"status": "disconnected", "configured": False, "connected": False,
                "reason": "Outlook integration module not loaded"}
    try:
        from opsx.connectors.outlook_auth import config_status as _ms_cfg_status
        cfg = _ms_cfg_status()
    except Exception:
        cfg = {"configured": False, "reason": "Config check failed"}

    uid = current_user["user_id"]
    sub = _ms_sub_store.get(uid)

    # ── No token at all ─────────────────────────────────────────────────
    if not _ms_token_store.is_authenticated(uid):
        return {
            "status":         "disconnected",
            "configured":     cfg.get("configured", False),
            "connected":      False,
            "authenticated":  False,
            "token_rejected": False,
            "graph_verified": False,
            "subscription":   bool(sub),
            "unread_count":   0,
            "pending_emails": _ms_email_store.pending_count(),
            "config_detail":  cfg,
        }

    # ── Token present — probe Graph /me ─────────────────────────────────
    graph_info     = {}
    token_rejected = False
    try:
        result = await _ms_verify_token(uid)
        if result.get("valid"):
            graph_info = result
        else:
            # verify returned False without raising — treat as network hiccup,
            # keep "connected" but don't claim graph_verified
            graph_info = result
    except _ms_TokenExpiredError:
        token_rejected = True

    # ── Unread count (best-effort — don't flip auth on network error) ───
    unread = 0
    if not token_rejected:
        try:
            unread = await _ms_count_unread(uid)
        except (_ms_TokenExpiredError, ValueError):
            token_rejected = True
        except Exception:
            pass

    graph_ok = graph_info.get("valid", False) and not token_rejected

    if token_rejected:
        conn_status = "expired"
    elif graph_ok:
        conn_status = "connected_polling"
    else:
        # token present locally but Graph is unreachable — optimistic
        conn_status = "connected_polling"

    return {
        "status":          conn_status,
        "configured":      cfg.get("configured", False),
        "connected":       not token_rejected,
        "authenticated":   not token_rejected,
        "token_rejected":  token_rejected,
        "graph_verified":  graph_ok,
        "graph_user":      graph_info.get("display_name", ""),
        "graph_email":     graph_info.get("email", ""),
        "subscription":    bool(sub),
        "subscription_id": sub.get("id") if sub else None,
        "sub_expires":     sub.get("expirationDateTime") if sub else None,
        "unread_count":    unread,
        "pending_emails":  _ms_email_store.pending_count(),
        "config_detail":   cfg,
    }


@app.get("/api/outlook/token-status")
async def outlook_token_status(current_user: dict = Depends(get_optional_user)):
    """Debug: show token state for the current user. No secrets exposed."""
    if not _OUTLOOK_AVAILABLE:
        return {"available": False}
    uid   = current_user["user_id"]
    store = _ms_token_store
    has_token   = store.is_authenticated(uid)
    is_expired  = store.is_expired(uid) if has_token else True
    token_prefix = ""
    scopes       = ""
    if has_token:
        raw = store.get_access_token(uid)
        if raw:
            token_prefix = raw[:20] + "..."
            try:
                import base64, json as _json
                parts = raw.split(".")
                if len(parts) >= 2:
                    pad = parts[1] + "=" * (4 - len(parts[1]) % 4)
                    payload = _json.loads(base64.urlsafe_b64decode(pad))
                    scopes = payload.get("scp", payload.get("roles", ""))
            except Exception:
                pass
    t = store.get(uid) or {}
    return {
        "user_id":     uid,
        "has_token":   has_token,
        "is_expired":  is_expired,
        "token_prefix": token_prefix,
        "scopes":      scopes,
        "has_refresh": bool(t.get("refresh_token")),
        "saved_at":    t.get("saved_at"),
        "expires_in":  t.get("expires_in"),
    }


@app.get("/api/outlook/config-check")
async def outlook_config_check():
    """Diagnostic: show which env vars are set (no secrets exposed)."""
    import os
    def _set(name: str) -> bool:
        return bool(os.getenv(name, "").strip())
    checks = {
        "OUTLOOK_CLIENT_ID":     _set("OUTLOOK_CLIENT_ID") or _set("OUTLOOK_APPLICATION"),
        "OUTLOOK_CLIENT_SECRET": _set("OUTLOOK_CLIENT_SECRET"),
        "OUTLOOK_TENANT_ID":     _set("OUTLOOK_TENANT_ID") or _set("OUTLOOK_DIRECTORY"),
        "OUTLOOK_REDIRECT_URI":  _set("OUTLOOK_REDIRECT_URI") or _set("REDIRECT_URI"),
        "module_loaded":         _OUTLOOK_AVAILABLE,
    }
    missing = [k for k, v in checks.items() if not v and k != "module_loaded"]
    return {
        "status":    "ok" if not missing else "missing_config",
        "checks":    checks,
        "missing":   missing,
        "ready":     not missing and _OUTLOOK_AVAILABLE,
        "setup_url": "https://portal.azure.com/#blade/Microsoft_AAD_RegisteredApps/ApplicationsListBlade",
    }


@app.get("/api/outlook/graph-qa")
async def outlook_graph_qa(current_user: dict = Depends(get_optional_user)):
    """
    End-to-end Graph API health check.
    Probes /me, /me/messages, /me/mailFolders/Inbox, and /subscriptions.
    Returns decoded token info + real HTTP status for each call.
    Never swallows errors.
    """
    _outlook_guard()
    import base64 as _b64, json as _j, httpx as _httpx

    uid = current_user["user_id"]
    out: dict = {
        "user_id": uid,
        "token_present": False,
        "aud": None,
        "scopes": None,
        "me_status": None,    "me_error": None,
        "messages_status": None, "messages_error": None,
        "inbox_status": None,    "inbox_error": None,
        "raw_errors": [],
    }

    token = await _ms_get_token(uid)
    if not token:
        out["raw_errors"].append("No valid token — user must re-authenticate")
        print("[GRAPH QA] FAIL: no token")
        return out
    out["token_present"] = True

    try:
        parts = token.split(".")
        if len(parts) >= 2:
            pad = parts[1] + "=" * (4 - len(parts[1]) % 4)
            payload = _j.loads(_b64.urlsafe_b64decode(pad))
            out["aud"]    = payload.get("aud")
            out["scopes"] = payload.get("scp", payload.get("roles", ""))
            print(f"[GRAPH QA] aud={out['aud']}  scopes={out['scopes']}")
    except Exception as e:
        out["raw_errors"].append(f"JWT decode failed: {e}")

    _BASE = "https://graph.microsoft.com/v1.0"
    hdrs  = {"Authorization": f"Bearer {token}"}

    async with _httpx.AsyncClient(timeout=20) as client:
        for label, url, params in [
            ("me",       f"{_BASE}/me",             {}),
            ("messages", f"{_BASE}/me/messages",    {"$top": "1"}),
            ("inbox",    f"{_BASE}/me/mailFolders('Inbox')/messages", {"$top": "1"}),
        ]:
            try:
                r = await client.get(url, headers=hdrs, params=params)
                out[f"{label}_status"] = r.status_code
                print(f"[GRAPH QA] GET /{label} → {r.status_code}")
                if r.status_code != 200:
                    err = r.text[:600]
                    out[f"{label}_error"] = err
                    out["raw_errors"].append(f"GET /{label} {r.status_code}: {err[:200]}")
            except Exception as e:
                out[f"{label}_error"] = str(e)
                out["raw_errors"].append(f"GET /{label} exception: {e}")

    return out


@app.get("/api/outlook/subscription-debug")
async def outlook_subscription_debug(current_user: dict = Depends(get_optional_user)):
    """
    Attempt subscription creation in debug mode.
    Tries both resource paths (mailFolders/Inbox and me/messages) and two TTLs.
    Returns the full raw Graph response for every attempt.
    Cleans up any successfully created test subscriptions.
    """
    _outlook_guard()
    import base64 as _b64, json as _j, httpx as _httpx
    from datetime import datetime as _dt, timedelta as _td, timezone as _tz

    uid = current_user["user_id"]
    out: dict = {"user_id": uid, "token_present": False,
                 "aud": None, "scopes": None, "attempts": [], "success": False}

    token = await _ms_get_token(uid)
    if not token:
        out["error"] = "No valid token — authenticate first"
        return out
    out["token_present"] = True

    try:
        parts = token.split(".")
        if len(parts) >= 2:
            pad = parts[1] + "=" * (4 - len(parts[1]) % 4)
            pl = _j.loads(_b64.urlsafe_b64decode(pad))
            out["aud"]    = pl.get("aud")
            out["scopes"] = pl.get("scp", pl.get("roles", ""))
    except Exception as e:
        out["aud_decode_error"] = str(e)

    from opsx.connectors.outlook_webhook import _NOTIFICATION_URL, _CLIENT_STATE
    out["notification_url"] = _NOTIFICATION_URL
    out["client_state"]     = _CLIENT_STATE

    def _exp(minutes: int) -> str:
        dt = _dt.now(_tz.utc) + _td(minutes=minutes)
        return dt.strftime("%Y-%m-%dT%H:%M:%S.0000000Z")

    hdrs = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    async with _httpx.AsyncClient(timeout=30) as client:
        for resource in ["me/mailFolders('Inbox')/messages", "me/messages"]:
            for ttl in [4000, 60]:
                payload = {
                    "changeType":               "created",
                    "notificationUrl":          _NOTIFICATION_URL,
                    "lifecycleNotificationUrl": _NOTIFICATION_URL,
                    "resource":                 resource,
                    "expirationDateTime":       _exp(ttl),
                    "clientState":              _CLIENT_STATE,
                }
                print(f"[SUB DEBUG] resource={resource!r} ttl={ttl}")
                try:
                    r = await client.post(
                        "https://graph.microsoft.com/v1.0/subscriptions",
                        headers=hdrs, json=payload,
                    )
                    attempt = {
                        "resource": resource, "ttl_minutes": ttl,
                        "status_code": r.status_code,
                        "response_text": r.text[:800],
                        "payload_sent": {k: v for k, v in payload.items() if k != "clientState"},
                    }
                    print(f"[SUB DEBUG] → {r.status_code}: {r.text[:300]}")
                    out["attempts"].append(attempt)
                    if r.status_code == 201:
                        out["success"] = True
                        out["working_resource"] = resource
                        out["working_ttl_minutes"] = ttl
                        # Clean up the test subscription
                        sub_id = r.json().get("id")
                        if sub_id:
                            await client.delete(
                                f"https://graph.microsoft.com/v1.0/subscriptions/{sub_id}",
                                headers={"Authorization": f"Bearer {token}"},
                            )
                            out["test_sub_cleaned"] = True
                        return out
                except Exception as e:
                    out["attempts"].append({"resource": resource, "ttl_minutes": ttl, "exception": str(e)})

    return out


@app.post("/api/outlook/subscribe")
async def outlook_subscribe(current_user: dict = Depends(get_optional_user)):
    _outlook_guard()
    uid = current_user["user_id"]
    print(f"[SUBSCRIBE] Triggered for user={uid}")
    existing = _ms_sub_store.get(uid)
    if existing and not _ms_sub_store.is_near_expiry(uid):
        print(f"[SUBSCRIBE] Already active sub_id={existing.get('id')}")
        return {"status": "ok", "message": "Subscription already active", "subscription": existing}
    try:
        sub = await _ms_create_sub(uid)
        if sub:
            print(f"[SUBSCRIBE] Created sub_id={sub.get('id')}")
            return {"status": "ok", "subscription": sub}
        return {"status": "error", "error": "Subscription returned None — check server logs"}
    except ValueError as exc:
        print(f"[SUBSCRIBE] FAILED: {exc}")
        return JSONResponse({"status": "error", "error": str(exc)}, status_code=400)
    except Exception as exc:
        print(f"[SUBSCRIBE] EXCEPTION: {exc}")
        return JSONResponse({"status": "error", "error": str(exc)}, status_code=500)


@app.post("/api/outlook/unsubscribe")
async def outlook_unsubscribe(current_user: dict = Depends(get_optional_user)):
    _outlook_guard()
    ok = await _ms_delete_sub(current_user["user_id"])
    return {"status": "ok" if ok else "error"}


# ── Webhook endpoint ──────────────────────────────────────────────────

@app.api_route("/webhook/outlook", methods=["GET", "POST"])
async def outlook_webhook_legacy(request: Request, validationToken: str = ""):
    """Legacy alias — delegates to the canonical /api/outlook/webhook handler."""
    return await outlook_webhook_canonical(request, validationToken=validationToken)


# ── Inbox / email store ───────────────────────────────────────────────

@app.get("/api/outlook/inbox")
async def outlook_inbox(
    limit: int = 20,
    status: str = "",
    priority: str = "",
    days: int = 7,
    current_user: dict = Depends(get_optional_user),
):
    _outlook_guard()
    uid = current_user["user_id"]
    _has_token  = _ms_token_store.is_authenticated(uid)
    _is_expired = _ms_token_store.is_expired(uid) if _has_token else True
    _token_data = _ms_token_store.get(uid) or {}
    if not _has_token or (_is_expired and not _token_data.get("refresh_token")):
        return {
            "status":  "disconnected",
            "message": "Outlook not connected. Visit /api/outlook/auth-url to authenticate.",
            "items":   [],
            "count":   0,
            "pending": 0,
        }
    from datetime import timedelta
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
    raw_items = _ms_email_store.list(
        status   = status   or None,
        limit    = limit * 3,  # over-fetch before date filter
        priority = priority or None,
    )
    items = []
    for em in raw_items:
        received = em.get("received_at") or em.get("created_at", "")
        if received < cutoff:
            continue
        em.setdefault("is_read",        em.get("read", False))
        em.setdefault("has_attachments", bool(em.get("attachments")))
        em.setdefault("action_status",  em.get("status", "pending_approval"))
        items.append(em)
        if len(items) >= limit:
            break
    return {
        "status":  "ok",
        "items":   items,
        "count":   len(items),
        "pending": _ms_email_store.pending_count(),
        "stats":   _ms_email_store.stats(),
    }


@app.get("/api/outlook/email/{message_id}")
async def outlook_get_email(message_id: str, current_user: dict = Depends(get_optional_user)):
    _outlook_guard()
    rec = _ms_email_store.get(message_id)
    if not rec:
        raise HTTPException(404, "Email not found")
    return {"status": "ok", "email": rec}


@app.post("/api/outlook/email/{message_id}/generate-reply")
async def outlook_generate_reply(message_id: str, current_user: dict = Depends(get_optional_user)):
    """Generate an AI draft reply for a given email. Never sends — preview only."""
    _outlook_guard()
    rec = _ms_email_store.get(message_id)
    if not rec:
        raise HTTPException(404, "Email not found")
    subject = rec.get("subject", "")
    body    = rec.get("body") or rec.get("summary") or ""
    sender  = rec.get("sender_name") or rec.get("sender_email", "")
    existing_draft = rec.get("reply_draft", "")
    if existing_draft:
        return {"status": "ok", "draft": existing_draft, "source": "existing_draft"}
    prompt = (
        f"You are a professional assistant drafting a reply to an email.\n"
        f"From: {sender}\nSubject: {subject}\n\nEmail body:\n{body}\n\n"
        f"Write a concise, professional reply in the same language as the email. "
        f"Max 3 paragraphs. Do not start with 'Dear' if the email is casual."
    )
    draft = ""
    try:
        ai_res = ai_orchestrator.route(prompt, user_id=current_user["user_id"])
        draft = (
            ai_res.get("reply") or ai_res.get("response") or
            ai_res.get("answer") or ai_res.get("text") or ""
        )
    except Exception:
        pass
    if not draft:
        draft = f"Hi {sender},\n\nThank you for your email regarding '{subject}'. I will get back to you shortly.\n\nBest regards"
    _ms_email_store.update(message_id, reply_draft=draft)
    return {"status": "ok", "draft": draft, "source": "ai_generated"}


class _FetchEmailReq(BaseModel):
    message_id: str


@app.post("/api/outlook/fetch")
async def outlook_fetch_now(body: _FetchEmailReq, current_user: dict = Depends(get_optional_user)):
    _outlook_guard()
    uid = current_user["user_id"]
    try:
        email = await _ms_fetch_email(body.message_id, uid)
    except _ms_TokenExpiredError:
        return JSONResponse(
            {"status": "expired", "requires_reauth": True,
             "message": "Session expired — reconnect Outlook"},
            status_code=401,
        )
    if not email:
        raise HTTPException(404, "Message not found in Microsoft Graph")
    result = await _ms_process_email(email)
    saved  = await _ms_store_email(result)
    return {"status": "ok", "email": saved}


@app.get("/api/outlook/live-inbox")
async def outlook_live_inbox(
    limit: int = 15,
    unread_only: bool = False,
    current_user: dict = Depends(get_optional_user),
):
    _outlook_guard()
    try:
        items = await _ms_list_inbox(limit=limit, user_id=current_user["user_id"], unread_only=unread_only)
        return {"status": "ok", "items": items, "count": len(items)}
    except _ms_TokenExpiredError as exc:
        return JSONResponse(
            {"status": "expired", "requires_reauth": True,
             "message": "Session expired — reconnect Outlook"},
            status_code=401,
        )
    except ValueError as exc:
        return JSONResponse({"status": "error", "error": str(exc), "reauth_required": True}, status_code=401)


@app.post("/api/outlook/poll")
async def outlook_poll(current_user: dict = Depends(get_optional_user)):
    """
    Fallback polling: fetch latest unread messages from Graph and enqueue any
    not already stored. Called every 60s from dashboard when webhook is unreliable.
    """
    _outlook_guard()
    uid   = current_user["user_id"]
    _plog = logging.getLogger("jarvis.outlook.poll")
    try:
        messages = await _ms_list_inbox(limit=10, user_id=uid, unread_only=True)
    except _ms_TokenExpiredError:
        _plog.warning("Poll skipped: token expired for user=%s — re-auth required", uid)
        return {"status": "expired", "requires_reauth": True,
                "message": "Session expired — reconnect Outlook", "new": 0}
    except Exception as exc:
        _plog.warning("Poll inbox failed: %s", exc)
        return {"status": "error", "error": str(exc), "new": 0}

    new_count = 0
    for msg in messages:
        msg_id = msg.get("id") or msg.get("message_id")
        if not msg_id:
            continue
        if _ms_email_store.get(msg_id):
            continue   # already in store
        try:
            full = await _ms_fetch_email(msg_id, uid)
            if full:
                result = await _ms_process_email(full)
                await _ms_store_email(result)
                new_count += 1
                _plog.info("Poll: new email ingested id=%s", msg_id)
        except _ms_TokenExpiredError:
            _plog.warning("Poll: token expired while fetching msg=%s — stopping", msg_id)
            break
        except Exception as exc:
            _plog.warning("Poll: error processing msg=%s: %s", msg_id, exc)

    return {"status": "ok", "new": new_count, "checked": len(messages)}


# ── Actions ───────────────────────────────────────────────────────────

class _SendReplyReq(BaseModel):
    message_id: str
    reply_text: str


@app.post("/api/outlook/send-reply")
async def outlook_send_reply(body: _SendReplyReq, current_user: dict = Depends(get_optional_user)):
    """Send a reply — ONLY called after explicit user approval."""
    _outlook_guard()
    try:
        result = await _ms_send_reply(body.message_id, body.reply_text, current_user["user_id"])
    except _ms_TokenExpiredError:
        return JSONResponse(
            {"status": "expired", "requires_reauth": True,
             "message": "Session expired — reconnect Outlook"},
            status_code=401,
        )
    if not result["success"]:
        raise HTTPException(500, result.get("error", "Send failed"))
    return {"status": "ok", **result}


@app.post("/api/outlook/delete/{message_id}")
async def outlook_delete_email(message_id: str, current_user: dict = Depends(get_optional_user)):
    """Delete email — ONLY called after explicit user approval."""
    _outlook_guard()
    try:
        result = await _ms_delete_email(message_id, current_user["user_id"])
    except _ms_TokenExpiredError:
        return JSONResponse(
            {"status": "expired", "requires_reauth": True,
             "message": "Session expired — reconnect Outlook"},
            status_code=401,
        )
    if not result["success"]:
        raise HTTPException(500, result.get("error", "Delete failed"))
    return {"status": "ok", **result}


@app.post("/api/outlook/ignore/{message_id}")
async def outlook_ignore(message_id: str, current_user: dict = Depends(get_optional_user)):
    _outlook_guard()
    try:
        return {"status": "ok", **(await _ms_ignore_email(message_id))}
    except _ms_TokenExpiredError:
        return JSONResponse(
            {"status": "expired", "requires_reauth": True,
             "message": "Session expired — reconnect Outlook"},
            status_code=401,
        )


@app.post("/api/outlook/mark-read/{message_id}")
async def outlook_mark_read(message_id: str, current_user: dict = Depends(get_optional_user)):
    _outlook_guard()
    try:
        return {"status": "ok", **(await _ms_mark_email_read(message_id, current_user["user_id"]))}
    except _ms_TokenExpiredError:
        return JSONResponse(
            {"status": "expired", "requires_reauth": True,
             "message": "Session expired — reconnect Outlook"},
            status_code=401,
        )


class _UpdateDraftReq(BaseModel):
    new_draft: str


@app.patch("/api/outlook/email/{message_id}/draft")
async def outlook_update_draft(
    message_id: str,
    body: _UpdateDraftReq,
    current_user: dict = Depends(get_optional_user),
):
    _outlook_guard()
    return {"status": "ok", **(await _ms_update_draft(message_id, body.new_draft))}


@app.post("/api/outlook/email/{message_id}/create-task")
async def outlook_create_task(message_id: str, current_user: dict = Depends(get_optional_user)):
    _outlook_guard()
    result = await _ms_task_from_email(message_id)
    if result["success"]:
        task = result.get("task", {})
        try:
            _office(current_user["user_id"]).add_task(
                title    = task["title"],
                notes    = task.get("notes", ""),
                priority = task.get("priority", "medium"),
            )
        except Exception:
            pass
    return {"status": "ok", **result}


@app.post("/api/outlook/email/{message_id}/create-event")
async def outlook_create_event(message_id: str, current_user: dict = Depends(get_optional_user)):
    _outlook_guard()
    return {"status": "ok", **(await _ms_event_from_email(message_id))}


# ── Observability ─────────────────────────────────────────────────────

@app.get("/api/outlook/queue-stats")
async def outlook_queue_stats(current_user: dict = Depends(get_optional_user)):
    _outlook_guard()
    return {
        "status":        "ok",
        "queue":         _ms_event_queue.stats(),
        "subscriptions": _ms_sub_store.summary(),
        "email_store":   _ms_email_store.stats(),
    }


# ══════════════════════════════════════════════════════════════════════
# MARKETS API  — overview / recommended / news / analyze aliases
# ══════════════════════════════════════════════════════════════════════

@app.get("/api/markets/overview")
def markets_overview():
    """Full market overview: regime + tickers. Alias wraps /api/markets/snapshot."""
    if not _MKT_AVAILABLE or _mkt_engine is None:
        return {
            "status":  "unavailable",
            "regime":  "unknown",
            "items":   [],
            "reason":  "Market engine not available. Check OPENAI_API_KEY / yfinance.",
            "timestamp": datetime.now().isoformat(),
        }
    try:
        data    = _mkt_engine.snapshot()
        items   = data.get("items", [])
        vix_item = next((x for x in items if x["label"] == "VIX"), None)
        spy_item = next((x for x in items if x["label"] == "SPY"), None)
        vix      = vix_item["price"] if vix_item else None
        spy_chg  = spy_item["change_pct"] if spy_item else None
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
            "status":    "ok",
            "regime":    regime,
            "vix":       vix,
            "items":     items,
            "timestamp": data.get("timestamp", datetime.now().isoformat()),
        }
    except Exception as exc:
        return {"status": "error", "regime": "unknown", "items": [], "error": str(exc),
                "timestamp": datetime.now().isoformat()}


@app.get("/api/markets/recommended")
def markets_recommended():
    """Return recommended stocks from the brain/product engine."""
    try:
        raw = brain.recommendations()
        items = raw.get("items", []) if isinstance(raw, dict) else []
        # Normalise format expected by the dashboard
        normalised = []
        for item in items[:12]:
            normalised.append({
                "symbol":                  item.get("symbol") or item.get("ticker") or "",
                "name":                    item.get("name", ""),
                "signal":                  (item.get("signal")
                                            or item.get("trade_plan", {}).get("action")
                                            or "Watch"),
                "price":                   item.get("price"),
                "setup_score":             item.get("setup_score") or item.get("score"),
                "traffic_light":           item.get("traffic_light", "yellow"),
                "risk":                    item.get("risk") or item.get("risk_level") or "medium",
                "reason":                  item.get("reason") or item.get("rationale") or "",
                "friendly_recommendation": (item.get("friendly_recommendation")
                                            or item.get("reason") or ""),
                "analysis":                (item.get("analysis")
                                            or item.get("friendly_recommendation") or ""),
                "thesis_short":            item.get("thesis_short", ""),
                "catalyst":                item.get("catalyst", ""),
            })
        return {"status": "ok", "items": normalised, "count": len(normalised)}
    except Exception as exc:
        return {"status": "error", "items": [], "error": str(exc)}


@app.get("/api/markets/news")
def markets_news(limit: int = 12):
    """Return market-relevant news from the news engine."""
    try:
        items = news_engine.fetch_categorized(max_per_category=max(2, limit // 3))
        flat  = []
        for cat_items in items.values() if isinstance(items, dict) else [items]:
            if isinstance(cat_items, list):
                flat.extend(cat_items)
        if not flat:
            flat = items if isinstance(items, list) else []
        return {"status": "ok", "items": flat[:limit], "count": len(flat[:limit])}
    except Exception as exc:
        return {"status": "error", "items": [], "error": str(exc)}


class _MarketAnalyzeReq(BaseModel):
    symbol: str = "AAPL"


@app.post("/api/markets/analyze")
def markets_analyze(body: _MarketAnalyzeReq):
    """Analyze a single ticker with technical indicators."""
    sym = (body.symbol or "AAPL").strip().upper()
    if not _MKT_AVAILABLE or _mkt_engine is None:
        # Fallback to yfinance directly when engine is missing
        try:
            import yfinance as yf
            from datetime import datetime as _dt
            t   = yf.Ticker(sym)
            h   = t.history(period="6mo", interval="1d")
            if h.empty or len(h) < 2:
                return {"status": "error", "symbol": sym, "error": "No data returned from yfinance"}
            price  = round(float(h["Close"].iloc[-1]), 2)
            ma20   = round(float(h["Close"].rolling(20).mean().iloc[-1]), 2)
            ma50   = round(float(h["Close"].rolling(50).mean().iloc[-1]), 2)
            trend  = "bullish" if price > ma50 else "bearish"
            return {
                "status": "ok", "symbol": sym, "price": price,
                "ma20": ma20, "ma50": ma50, "trend": trend,
                "timestamp": _dt.utcnow().isoformat(),
            }
        except Exception as exc:
            return {"status": "error", "symbol": sym, "error": str(exc)}
    try:
        result = _mkt_engine.analyze_symbol(sym)
        result["status"] = "ok"
        return result
    except Exception as exc:
        return {"status": "error", "symbol": sym, "error": str(exc)}


class _TraderAnalyzeReq(BaseModel):
    symbol: str = "AAPL"
    with_portfolio_context: bool = True


@app.post("/api/trader/analyze")
def trader_analyze(body: _TraderAnalyzeReq):
    """
    Full institutional-grade trade analysis with regime, portfolio context,
    learning history, and structured explainability.
    """
    from core.trader_alpha_engine import TraderAlphaEngine
    sym = (body.symbol or "AAPL").strip().upper()
    engine = TraderAlphaEngine()
    portfolio_snapshot = None
    if body.with_portfolio_context and _PORTFOLIO_AVAILABLE:
        try:
            portfolio_snapshot = _build_unified_snapshot()
        except Exception:
            portfolio_snapshot = None
    try:
        result = engine.run_with_context(sym, portfolio_snapshot=portfolio_snapshot)
        result["status"] = "ok"
        result["real_trade"] = False
        return result
    except Exception as exc:
        return {"status": "error", "symbol": sym, "error": str(exc), "real_trade": False}


# ══════════════════════════════════════════════════════════════════════
# PORTFOLIO INTELLIGENCE — READ-ONLY — IBKR + HAPI + UNIFIED + PAPER
# ══════════════════════════════════════════════════════════════════════

import os as _os_env

try:
    # Remote bridge mode: Railway → ngrok → secure_bridge → IB Gateway
    # Activate by setting ENABLE_REMOTE_IBKR_BRIDGE=true in Railway env vars.
    if _os_env.getenv("ENABLE_REMOTE_IBKR_BRIDGE", "false").lower() == "true":
        from opsx.connectors.ibkr_bridge_client import ibkr_bridge as _ibkr, TradingBlockedError as _TradingBlockedError
        logging.getLogger("jarvis").info("IBKR mode: REMOTE BRIDGE (%s)",
                                         _os_env.getenv("IBKR_BRIDGE_URL", "NOT_SET"))
    else:
        from opsx.connectors.ibkr_readonly import ibkr as _ibkr, TradingBlockedError as _TradingBlockedError
        logging.getLogger("jarvis").info("IBKR mode: local Client Portal (localhost:5000)")
    from opsx.connectors.hapi_readonly import hapi as _hapi
    from core.unified_portfolio_engine import unified_portfolio as _unified_portfolio
    from core.portfolio_intelligence_engine import portfolio_intelligence as _portfolio_intel
    from core.paper_trading_engine import paper_trading as _paper_trading
    from core.trader_learning_engine import trader_learning as _trader_learning
    _PORTFOLIO_AVAILABLE = True
except Exception as _pe:
    _PORTFOLIO_AVAILABLE = False
    _ibkr = None
    _hapi = None
    _trader_learning = None
    _unified_portfolio = None
    _portfolio_intel = None
    _paper_trading = None
    logging.getLogger("jarvis").warning("Portfolio modules unavailable: %s", _pe)


def _portfolio_guard():
    if not _PORTFOLIO_AVAILABLE:
        raise HTTPException(503, "Portfolio integration modules not loaded")


def _build_unified_snapshot(force_refresh: bool = False) -> Dict:
    """Fetch from brokers and return unified snapshot. Falls back to cache on error."""
    ibkr_data = None
    hapi_data = None
    try:
        if _ibkr:
            ibkr_data = _ibkr.get_full_portfolio()
    except Exception:
        pass
    try:
        if _hapi:
            hapi_data = _hapi.get_full_portfolio()
    except Exception:
        pass
    if ibkr_data or hapi_data:
        return _unified_portfolio.build_snapshot(ibkr_data, hapi_data)
    cached = _unified_portfolio.get_cached_snapshot()
    if cached:
        cached["_from_cache"] = True
        return cached
    return _unified_portfolio.empty_snapshot("no_broker_data")


# ── Portfolio Status ───────────────────────────────────────────────────

@app.get("/api/portfolio/status")
def portfolio_status(current_user: dict = Depends(get_optional_user)):
    """Read-only portfolio connection status for both brokers."""
    if not _PORTFOLIO_AVAILABLE:
        return {"status": "modules_unavailable", "ibkr": "unavailable", "hapi": "unavailable",
                "real_trade": False}
    ibkr_status = _ibkr.health_check() if _ibkr else {"status": "unavailable"}
    hapi_status = _hapi.health_check() if _hapi else {"status": "unavailable"}
    return {
        "status":     "ok",
        "ibkr":       ibkr_status,
        "hapi":       hapi_status,
        "real_trade": False,
    }


# ── IBKR Debug ────────────────────────────────────────────────────────

@app.get("/api/debug/ibkr")
def debug_ibkr(current_user: dict = Depends(get_optional_user)):
    """
    Deep diagnostic: bridge reachability, auth, broker connectivity,
    snapshot freshness, and latency. Safe to call repeatedly — read-only.
    """
    import time as _time
    import os as _os_dbg
    from datetime import datetime as _dt

    remote_mode  = _os_dbg.getenv("ENABLE_REMOTE_IBKR_BRIDGE", "false").lower() == "true"
    bridge_url   = _os_dbg.getenv("IBKR_BRIDGE_URL", "")
    token_set    = bool(_os_dbg.getenv("IBKR_BRIDGE_TOKEN", ""))

    result: Dict = {
        "mode":          "remote_bridge" if remote_mode else "local_client_portal",
        "bridge_url":    bridge_url or "(not set)",
        "token_set":     token_set,
        "real_trade":    False,
        "checked_at":    _dt.utcnow().isoformat(),
    }

    if not _PORTFOLIO_AVAILABLE or not _ibkr:
        result.update({"bridge_reachable": False, "auth_ok": False,
                        "broker_connected": False, "error": "Portfolio modules unavailable"})
        return result

    t0 = _time.monotonic()
    try:
        health = _ibkr.health_check()
        latency_ms = round((_time.monotonic() - t0) * 1000, 1)

        if remote_mode:
            bridge_ok    = health.get("bridge_ok", False)
            ibkr_conn    = health.get("ibkr_connected", False)
            result.update({
                "bridge_reachable": bridge_ok,
                "auth_ok":          bridge_ok and not health.get("error", "").startswith("auth"),
                "broker_connected": ibkr_conn,
                "account_id":       health.get("account", ""),
                "readonly":         health.get("readonly", True),
                "cache_stale":      health.get("cache_stale", True),
                "bridge_latency_ms": latency_ms,
                "paper_only":       True,
            })
        else:
            connected = health.get("status") == "connected"
            result.update({
                "bridge_reachable": True,
                "auth_ok":          True,
                "broker_connected": connected,
                "account_id":       health.get("account_id", health.get("account", "")),
                "readonly":         True,
                "bridge_latency_ms": latency_ms,
                "paper_only":       True,
            })

        # Snapshot freshness
        try:
            snap = _ibkr.get_full_portfolio()
            positions_count = len(snap.get("positions", []))
            result["positions_count"] = positions_count
            result["last_update"]     = snap.get("fetched_at", "")
            result["snapshot_stale"]  = snap.get("_stale", True)
            cache_age = 0
            fetched_at = snap.get("fetched_at", "")
            if fetched_at:
                try:
                    from datetime import timezone
                    delta = _dt.utcnow() - _dt.fromisoformat(fetched_at.replace("Z", ""))
                    cache_age = round(delta.total_seconds(), 1)
                except Exception:
                    pass
            result["cache_age_seconds"] = cache_age
        except Exception as snap_exc:
            result["snapshot_error"] = str(snap_exc)

    except Exception as exc:
        result.update({
            "bridge_reachable": False, "auth_ok": False,
            "broker_connected": False, "error": str(exc),
            "bridge_latency_ms": round((_time.monotonic() - t0) * 1000, 1),
        })

    return result


# ── Unified Portfolio ──────────────────────────────────────────────────

@app.get("/api/portfolio/unified")
def portfolio_unified(current_user: dict = Depends(get_optional_user)):
    """Aggregated view across all connected brokers."""
    _portfolio_guard()
    try:
        snapshot = _build_unified_snapshot()
        snapshot["real_trade"] = False
        return snapshot
    except Exception as exc:
        return {"status": "error", "error": str(exc), "real_trade": False}


@app.get("/api/portfolio/summary")
def portfolio_summary(current_user: dict = Depends(get_optional_user)):
    """High-level portfolio summary — total capital, P&L, risk."""
    _portfolio_guard()
    try:
        snapshot = _build_unified_snapshot()
        return {
            "status":               "ok",
            "total_market_value":   snapshot.get("total_market_value", 0),
            "total_cash":           snapshot.get("total_cash", 0),
            "total_portfolio_value": snapshot.get("total_portfolio_value", 0),
            "total_daily_pnl":      snapshot.get("total_daily_pnl", 0),
            "total_daily_pnl_pct":  snapshot.get("total_daily_pnl_pct", 0),
            "total_unrealized_pnl": snapshot.get("total_unrealized_pnl", 0),
            "position_count":       snapshot.get("position_count", 0),
            "broker_exposure":      snapshot.get("broker_exposure", []),
            "concentration_warnings": snapshot.get("concentration_warnings", []),
            "generated_at":         snapshot.get("generated_at", ""),
            "_from_cache":          snapshot.get("_from_cache", False),
            "real_trade":           False,
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc), "real_trade": False}


@app.get("/api/portfolio/positions")
def portfolio_positions(current_user: dict = Depends(get_optional_user)):
    """All positions across all connected brokers."""
    _portfolio_guard()
    try:
        snapshot = _build_unified_snapshot()
        return {
            "status":     "ok",
            "positions":  snapshot.get("all_positions", []),
            "count":      snapshot.get("position_count", 0),
            "real_trade": False,
        }
    except Exception as exc:
        return {"status": "error", "positions": [], "real_trade": False, "error": str(exc)}


@app.get("/api/portfolio/brokers")
def portfolio_brokers(current_user: dict = Depends(get_optional_user)):
    """Per-broker breakdown with positions and P&L."""
    _portfolio_guard()
    try:
        snapshot = _build_unified_snapshot()
        return {
            "status":     "ok",
            "brokers":    snapshot.get("brokers", {}),
            "real_trade": False,
        }
    except Exception as exc:
        return {"status": "error", "brokers": {}, "real_trade": False, "error": str(exc)}


@app.get("/api/portfolio/exposure")
def portfolio_exposure(current_user: dict = Depends(get_optional_user)):
    """Sector, theme, and asset class exposure breakdown."""
    _portfolio_guard()
    try:
        snapshot = _build_unified_snapshot()
        return {
            "status":                "ok",
            "sector_exposure":       snapshot.get("sector_exposure", []),
            "theme_exposure":        snapshot.get("theme_exposure", []),
            "asset_class_exposure":  snapshot.get("asset_class_exposure", []),
            "broker_exposure":       snapshot.get("broker_exposure", []),
            "real_trade":            False,
        }
    except Exception as exc:
        return {"status": "error", "real_trade": False, "error": str(exc)}


@app.get("/api/portfolio/pnl")
def portfolio_pnl(current_user: dict = Depends(get_optional_user)):
    """Aggregated P&L view — daily and unrealized."""
    _portfolio_guard()
    try:
        snapshot = _build_unified_snapshot()
        return {
            "status":               "ok",
            "total_daily_pnl":      snapshot.get("total_daily_pnl", 0),
            "total_daily_pnl_pct":  snapshot.get("total_daily_pnl_pct", 0),
            "total_unrealized_pnl": snapshot.get("total_unrealized_pnl", 0),
            "by_broker":            {
                name: {
                    "daily_pnl":      b.get("daily_pnl", 0),
                    "unrealized_pnl": b.get("unrealized_pnl", 0),
                }
                for name, b in snapshot.get("brokers", {}).items()
            },
            "real_trade":           False,
        }
    except Exception as exc:
        return {"status": "error", "real_trade": False, "error": str(exc)}


@app.get("/api/portfolio/risk")
def portfolio_risk(current_user: dict = Depends(get_optional_user)):
    """Portfolio risk assessment and concentration warnings."""
    _portfolio_guard()
    try:
        snapshot = _build_unified_snapshot()
        intel    = _portfolio_intel.analyze(snapshot)
        return {
            "status":                  "ok",
            "portfolio_score":         intel.get("portfolio_score", 0),
            "risk_level":              intel.get("risk_level", "unknown"),
            "top_risks":               intel.get("top_risks", []),
            "concentration_warnings":  snapshot.get("concentration_warnings", []),
            "sector_warnings":         intel.get("sector_warnings", []),
            "do_not_touch":            intel.get("do_not_touch", []),
            "limitations":             intel.get("limitations", []),
            "real_trade":              False,
        }
    except Exception as exc:
        return {"status": "error", "real_trade": False, "error": str(exc)}


@app.get("/api/portfolio/analysis")
def portfolio_analysis(current_user: dict = Depends(get_optional_user)):
    """Full AI intelligence analysis of the portfolio."""
    _portfolio_guard()
    try:
        snapshot = _build_unified_snapshot()
        intel    = _portfolio_intel.analyze(snapshot)
        intel["real_trade"] = False
        intel["portfolio_value"] = snapshot.get("total_portfolio_value", 0)
        return intel
    except Exception as exc:
        return {"status": "error", "real_trade": False, "error": str(exc)}


@app.get("/api/proactive/alerts")
def proactive_alerts(current_user: dict = Depends(get_optional_user)):
    """Proactive intelligence alerts — stale tasks, follow-ups, portfolio risk shifts."""
    try:
        from core.proactive_intelligence_engine import proactive_intelligence
        context: Dict = {}
        # Inject portfolio snapshot if available
        if _PORTFOLIO_AVAILABLE:
            try:
                context["portfolio_snapshot"] = _build_unified_snapshot()
            except Exception:
                pass
        return proactive_intelligence.scan(context)
    except Exception as exc:
        return {"alerts": [], "alert_count": 0, "real_trade": False, "error": str(exc)}


@app.post("/api/portfolio/refresh")
def portfolio_refresh(current_user: dict = Depends(get_optional_user)):
    """Force-refresh data from all connected brokers."""
    _portfolio_guard()
    try:
        snapshot = _build_unified_snapshot(force_refresh=True)
        return {
            "status":       "ok",
            "message":      "Portfolio data refreshed",
            "position_count": snapshot.get("position_count", 0),
            "total_value":  snapshot.get("total_portfolio_value", 0),
            "generated_at": snapshot.get("generated_at", ""),
            "real_trade":   False,
        }
    except Exception as exc:
        return {"status": "error", "real_trade": False, "error": str(exc)}


# ── Paper Trading ──────────────────────────────────────────────────────

@app.get("/api/paper/status")
def paper_status(current_user: dict = Depends(get_optional_user)):
    """Paper trading account status."""
    _portfolio_guard()
    return _paper_trading.get_status()


@app.post("/api/paper/import-from-real")
def paper_import_real(current_user: dict = Depends(get_optional_user)):
    """Import real portfolio into paper trading account."""
    _portfolio_guard()
    try:
        snapshot = _build_unified_snapshot()
        return _paper_trading.import_from_real(snapshot)
    except Exception as exc:
        return {"status": "error", "error": str(exc), "real_trade": False}


@app.get("/api/paper/positions")
def paper_positions(current_user: dict = Depends(get_optional_user)):
    """Current paper trading positions."""
    _portfolio_guard()
    return _paper_trading.get_positions()


class _PaperTradeReq(BaseModel):
    symbol:   str
    action:   str = "buy"        # buy | sell | trim | add
    quantity: float = 1.0
    price:    float = 0.0
    thesis:   str = ""


@app.post("/api/paper/simulate-trade")
def paper_simulate_trade(body: _PaperTradeReq, current_user: dict = Depends(get_optional_user)):
    """
    Simulate a paper trade. NO live order placed.
    Returns real_trade: false always.
    """
    _portfolio_guard()
    if body.price <= 0:
        # Try to get live price from yfinance
        try:
            import yfinance as yf
            t = yf.Ticker(body.symbol.upper())
            hist = t.history(period="1d", interval="1m")
            if not hist.empty:
                body = _PaperTradeReq(
                    symbol=body.symbol,
                    action=body.action,
                    quantity=body.quantity,
                    price=round(float(hist["Close"].iloc[-1]), 4),
                    thesis=body.thesis,
                )
        except Exception:
            return {"status": "error", "message": "price required (could not fetch live price)", "real_trade": False}
    return _paper_trading.simulate_trade(body.symbol, body.action, body.quantity, body.price, body.thesis)


class _RebalanceReq(BaseModel):
    target_weights: Dict[str, float]   # {"AAPL": 20.0, "MSFT": 15.0}
    current_prices: Dict[str, float]   # {"AAPL": 185.0}


@app.post("/api/paper/rebalance")
def paper_rebalance(body: _RebalanceReq, current_user: dict = Depends(get_optional_user)):
    """Simulate a portfolio rebalance. No trades executed."""
    _portfolio_guard()
    return _paper_trading.rebalance(body.target_weights, body.current_prices)


@app.get("/api/paper/performance")
def paper_performance(current_user: dict = Depends(get_optional_user)):
    """Paper trading performance metrics."""
    _portfolio_guard()
    return _paper_trading.get_performance()


@app.get("/api/paper/history")
def paper_history(current_user: dict = Depends(get_optional_user)):
    """Full paper trade history."""
    _portfolio_guard()
    return _paper_trading.get_history()


@app.get("/api/paper/compare-real")
def paper_compare_real(current_user: dict = Depends(get_optional_user)):
    """Compare paper portfolio vs real portfolio."""
    _portfolio_guard()
    try:
        snapshot = _build_unified_snapshot()
        return _paper_trading.compare_with_real(snapshot)
    except Exception as exc:
        return {"status": "error", "error": str(exc), "real_trade": False}


@app.post("/api/paper/reset")
def paper_reset(current_user: dict = Depends(get_optional_user)):
    """Reset paper trading account to initial state."""
    _portfolio_guard()
    return _paper_trading.reset()


# ── Paper Analytics (rich computed metrics) ────────────────────────────

def _compute_equity_curve(trades: List[Dict], initial_value: float) -> List[Dict]:
    """Build simplified equity curve from trade history (last 30 data points)."""
    if not trades:
        return [{"date": datetime.utcnow().date().isoformat(), "value": round(initial_value, 2)}]
    from collections import defaultdict
    daily: Dict[str, float] = defaultdict(float)
    for t in trades:
        date = (t.get("timestamp") or "")[:10]
        if not date:
            continue
        val = float(t.get("value", 0))
        if t.get("action") in ("sell", "trim"):
            daily[date] += val
        elif t.get("action") in ("buy", "add"):
            daily[date] -= val
    sorted_dates = sorted(daily.keys())
    if not sorted_dates:
        return [{"date": datetime.utcnow().date().isoformat(), "value": round(initial_value, 2)}]
    running = initial_value
    curve = [{"date": sorted_dates[0], "value": round(running, 2)}]
    for d in sorted_dates:
        running += daily[d]
        curve.append({"date": d, "value": round(max(running, 0), 2)})
    return curve[-30:]


@app.get("/api/paper/analytics")
def paper_analytics(current_user: dict = Depends(get_optional_user)):
    """Rich paper trading analytics — win rate, avg gain/loss, risk/reward, max drawdown, equity curve."""
    _portfolio_guard()
    try:
        perf      = _paper_trading.get_performance()
        hist      = _paper_trading.get_history()
        positions = _paper_trading.get_positions()

        all_trades    = hist.get("trades", [])
        closed_trades = [t for t in all_trades if t.get("action") in ("sell", "trim")]
        pos_list      = positions.get("positions", [])

        # Win / loss from open positions (unrealized P&L proxy)
        winners   = [p for p in pos_list if p.get("unrealized_pnl", 0) > 0]
        losers    = [p for p in pos_list if p.get("unrealized_pnl", 0) < 0]
        n_pos     = len(pos_list)
        win_rate  = round(len(winners) / n_pos * 100, 1) if n_pos else 0
        avg_gain  = round(sum(p.get("unrealized_pnl_pct", 0) for p in winners) / len(winners), 2) if winners else 0
        avg_loss  = round(sum(p.get("unrealized_pnl_pct", 0) for p in losers) / len(losers), 2) if losers else 0
        rr        = round(avg_gain / abs(avg_loss), 2) if avg_loss < 0 else 0

        initial_value = float(perf.get("initial_value", 100_000))
        total_pnl_pct = float(perf.get("total_pnl_pct", 0))
        max_drawdown  = round(min(0.0, total_pnl_pct), 2)

        # Strategy performance
        from collections import defaultdict as _dd
        strat: Dict[str, Any] = _dd(lambda: {"count": 0, "volume": 0.0})
        for t in all_trades:
            key = (t.get("thesis") or "no strategy").strip() or "no strategy"
            strat[key]["count"]  += 1
            strat[key]["volume"] = round(strat[key]["volume"] + float(t.get("value", 0)), 2)
        strategy_list = sorted(
            [{"strategy": k, "trades": v["count"], "volume": v["volume"]} for k, v in strat.items()],
            key=lambda x: x["trades"], reverse=True
        )[:8]

        # Learning confidence
        learning_confidence = 0
        if _trader_learning:
            try:
                lm = _trader_learning.get_metrics()
                learning_confidence = lm.get("learning_quality_score", 0)
            except Exception:
                pass

        equity_curve = _compute_equity_curve(all_trades, initial_value)

        return {
            "status":                   "ok",
            "portfolio_value":          round(float(perf.get("current_value", 0)), 2),
            "initial_value":            round(initial_value, 2),
            "cash":                     round(float(perf.get("cash", 0)), 2),
            "total_pnl":                round(float(perf.get("total_pnl", 0)), 2),
            "total_pnl_pct":            round(total_pnl_pct, 2),
            "trade_count":              len(all_trades),
            "open_positions":           n_pos,
            "closed_trades":            len(closed_trades),
            "win_rate":                 win_rate,
            "winners":                  len(winners),
            "losers":                   len(losers),
            "avg_gain_pct":             avg_gain,
            "avg_loss_pct":             avg_loss,
            "risk_reward":              rr,
            "max_drawdown_pct":         max_drawdown,
            "unrealized_pnl":           round(sum(p.get("unrealized_pnl", 0) for p in pos_list), 2),
            "equity_curve":             equity_curve,
            "strategy_performance":     strategy_list,
            "learning_confidence_score": learning_confidence,
            "real_trade":               False,
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc), "real_trade": False}


# ── Autonomous Paper Trader ────────────────────────────────────────────

try:
    from core.autonomous_paper_trader import autonomous_trader as _auto_trader
    _AUTO_TRADER_AVAILABLE = True
except Exception as _at_err:
    _auto_trader = None
    _AUTO_TRADER_AVAILABLE = False
    logging.getLogger("jarvis").warning("Autonomous trader unavailable: %s", _at_err)


@app.get("/api/paper/autonomous/status")
def autonomous_status(current_user: dict = Depends(get_optional_user)):
    """Autonomous paper trader: current state, regime, scan stats."""
    if not _AUTO_TRADER_AVAILABLE or not _auto_trader:
        return {"status": "unavailable", "real_trade": False}
    return _auto_trader.get_status()


@app.post("/api/paper/autonomous/start")
def autonomous_start(current_user: dict = Depends(get_optional_user)):
    """Start the autonomous paper trading simulation loop."""
    if not _AUTO_TRADER_AVAILABLE or not _auto_trader:
        return {"status": "unavailable", "real_trade": False}
    return _auto_trader.start()


@app.post("/api/paper/autonomous/stop")
def autonomous_stop(current_user: dict = Depends(get_optional_user)):
    """Stop the autonomous paper trading simulation loop."""
    if not _AUTO_TRADER_AVAILABLE or not _auto_trader:
        return {"status": "unavailable", "real_trade": False}
    return _auto_trader.stop()


@app.post("/api/paper/autonomous/scan")
def autonomous_scan(current_user: dict = Depends(get_optional_user)):
    """Trigger an immediate scan cycle (non-blocking)."""
    if not _AUTO_TRADER_AVAILABLE or not _auto_trader:
        return {"status": "unavailable", "real_trade": False}
    return _auto_trader.trigger_scan()


@app.get("/api/paper/autonomous/log")
def autonomous_log(limit: int = 50, current_user: dict = Depends(get_optional_user)):
    """Recent autonomous trade log entries."""
    if not _AUTO_TRADER_AVAILABLE or not _auto_trader:
        return {"trades": [], "total": 0, "real_trade": False}
    return _auto_trader.get_trade_log(limit=min(limit, 200))


# ── Portfolio Cockpit (one-shot combined view) ─────────────────────────

def _build_ai_insights(snapshot: Dict, intel: Dict, paper_status: Dict) -> List[str]:
    """Contextual AI insight strings from live portfolio data."""
    insights: List[str] = []
    positions  = snapshot.get("all_positions", [])
    total_val  = snapshot.get("total_market_value", 0)
    total_port = snapshot.get("total_portfolio_value", 0)

    if positions and total_val > 0:
        top = max(positions, key=lambda p: p.get("market_value", 0))
        top_pct = round(top.get("market_value", 0) / total_val * 100, 1)
        if top_pct > 20:
            insights.append(f"{top['symbol']} represents {top_pct}% of invested portfolio.")

    sectors = snapshot.get("sector_exposure", [])
    if sectors and sectors[0].get("pct", 0) > 40:
        s = sectors[0]
        insights.append(f"{s['label']} sector at {s['pct']}% — concentration risk.")

    daily_pnl = snapshot.get("total_daily_pnl", 0)
    daily_pct = snapshot.get("total_daily_pnl_pct", 0)
    if abs(daily_pct) >= 1:
        direction = "up" if daily_pnl >= 0 else "down"
        insights.append(f"Portfolio {direction} {abs(daily_pct):.1f}% today (${daily_pnl:+,.0f}).")

    paper_pnl_pct = float(paper_status.get("pnl_pct", 0))
    if paper_status.get("total_portfolio", 0) > 0:
        if paper_pnl_pct > 2:
            insights.append(f"Paper Lab +{paper_pnl_pct:.1f}% — simulation outperforming.")
        elif paper_pnl_pct < -2:
            insights.append(f"Paper Lab {paper_pnl_pct:.1f}% — review simulation strategy.")

    if intel.get("risk_level") in ("high", "critical"):
        insights.append(f"Risk level: {intel['risk_level'].upper()} — review concentration and exposure.")

    if total_port > 0:
        cash_pct = snapshot.get("total_cash", 0) / total_port * 100
        if cash_pct > 30:
            insights.append(f"{cash_pct:.0f}% cash — consider gradual deployment.")
        elif cash_pct < 3:
            insights.append(f"Low cash ({cash_pct:.0f}%) — limited flexibility.")

    if not insights:
        insights.append("Connect IBKR or Hapi for live portfolio insights.")
    return insights[:5]


@app.get("/api/portfolio/cockpit")
def portfolio_cockpit(current_user: dict = Depends(get_optional_user)):
    """One-shot cockpit: unified portfolio + intelligence + paper overview."""
    _portfolio_guard()
    try:
        snapshot     = _build_unified_snapshot()
        intel        = _portfolio_intel.analyze(snapshot)
        paper_status = _paper_trading.get_status()
        paper_total  = float(paper_status.get("total_portfolio", 0))
        real_total   = float(snapshot.get("total_portfolio_value", 0))
        return {
            "status": "ok",
            "real": {
                "total_value":     real_total,
                "invested":        snapshot.get("total_market_value", 0),
                "cash":            snapshot.get("total_cash", 0),
                "daily_pnl":       snapshot.get("total_daily_pnl", 0),
                "daily_pnl_pct":   snapshot.get("total_daily_pnl_pct", 0),
                "unrealized_pnl":  snapshot.get("total_unrealized_pnl", 0),
                "position_count":  snapshot.get("position_count", 0),
                "_from_cache":     snapshot.get("_from_cache", False),
            },
            "paper": {
                "total_value":     paper_total,
                "cash":            paper_status.get("cash", 0),
                "pnl_total":       paper_status.get("pnl_total", 0),
                "pnl_pct":         paper_status.get("pnl_pct", 0),
                "trade_count":     paper_status.get("trade_count", 0),
                "position_count":  paper_status.get("position_count", 0),
            },
            "combined_total":      round(real_total + paper_total, 2),
            "intelligence": {
                "portfolio_score": intel.get("portfolio_score", 0),
                "risk_level":      intel.get("risk_level", "unknown"),
                "summary":         intel.get("summary", ""),
                "top_risks":       intel.get("top_risks", [])[:3],
                "opportunities":   intel.get("opportunities", [])[:3],
                "paper_ideas":     intel.get("paper_trade_ideas", [])[:3],
                "ai_insights":     _build_ai_insights(snapshot, intel, paper_status),
            },
            "sector_exposure":         snapshot.get("sector_exposure", [])[:6],
            "asset_class_exposure":    snapshot.get("asset_class_exposure", []),
            "largest_positions":       snapshot.get("largest_positions", [])[:5],
            "concentration_warnings":  snapshot.get("concentration_warnings", [])[:3],
            "brokers":                 snapshot.get("brokers", {}),
            "real_trade": False,
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc), "real_trade": False}


# ── Trader Audit ───────────────────────────────────────────────────────

@app.get("/api/trader/audit")
def trader_audit(current_user: dict = Depends(get_optional_user)):
    """
    Trader agent reliability score — audits signal quality, risk logic,
    data quality, portfolio awareness, and explanation quality.
    """
    try:
        import yfinance as yf
        from core.trader_alpha_engine import TraderAlphaEngine
        engine = TraderAlphaEngine()

        test_symbols  = ["AAPL", "MSFT", "NVDA", "META", "TSLA", "AMD", "XOM", "PLTR"]
        results       = []
        buy_count     = 0
        watch_count   = 0
        avoid_count   = 0
        data_errors   = 0
        score_variance = []
        explanations_present = 0

        for sym in test_symbols:
            try:
                r = engine._analyze_impl(sym)
                if "error" in r:
                    data_errors += 1
                    continue
                action = r.get("action", "NEUTRAL")
                score  = r.get("setup_score", 50)
                sigs   = r.get("signals", [])
                buy_count   += (action == "BUY")
                watch_count += (action == "WATCH")
                avoid_count += (action in ("AVOID", "NEUTRAL"))
                score_variance.append(score)
                if sigs and len(sigs) >= 2:
                    explanations_present += 1
                results.append({"symbol": sym, "action": action, "score": score, "signals": len(sigs)})
            except Exception:
                data_errors += 1

        n = len(results)
        if n == 0:
            return {"status": "error", "message": "No analysis results available", "real_trade": False}

        buy_rate          = buy_count / n
        always_buy_flag   = buy_rate > 0.85
        signal_diversity  = 1 - (max(buy_count, watch_count, avoid_count) / n)
        expl_quality      = explanations_present / n
        import statistics
        score_std         = statistics.stdev(score_variance) if len(score_variance) > 1 else 0
        score_diversity   = min(score_std / 20, 1.0)  # 20pt std = good

        data_quality_score         = max(0, round((1 - data_errors / len(test_symbols)) * 100))
        signal_consistency_score   = round(min(signal_diversity * 100 + score_diversity * 50, 100))
        risk_quality_score         = round((1 - buy_rate) * 50 + 50) if not always_buy_flag else 30
        # Portfolio awareness — dynamic when brokers are connected
        if _PORTFOLIO_AVAILABLE:
            try:
                snap = _build_unified_snapshot()
                n_pos = snap.get("position_count", 0)
                has_warnings = len(snap.get("concentration_warnings", [])) > 0
                # Score: having connected portfolio data = +20, no warnings = +20
                portfolio_awareness_score = 40
                if n_pos > 0:
                    portfolio_awareness_score += 30
                if not has_warnings and n_pos > 0:
                    portfolio_awareness_score += 15
                if snap.get("total_market_value", 0) > 0:
                    portfolio_awareness_score += 15
            except Exception:
                portfolio_awareness_score = 55
        else:
            portfolio_awareness_score = 40

        # Learning engine bonus — if outcomes tracked, elevate quality score
        learning_bonus = 0
        if _PORTFOLIO_AVAILABLE and _trader_learning:
            try:
                lm = _trader_learning.get_metrics()
                total_outcomes = lm.get("total_outcomes", 0)
                win_rate = lm.get("overall_win_rate", 0)
                if total_outcomes >= 20:
                    learning_bonus = min(10, int(total_outcomes / 10))
                if win_rate >= 55:
                    learning_bonus += 5
            except Exception:
                pass

        explanation_quality_score  = round(expl_quality * 100)
        overall_score = round(min(100,
            data_quality_score * 0.25 +
            signal_consistency_score * 0.25 +
            risk_quality_score * 0.20 +
            portfolio_awareness_score * 0.15 +
            explanation_quality_score * 0.15 +
            learning_bonus
        ))

        known_limitations = [
            "Solo usa datos técnicos (OHLCV) — sin análisis fundamental",
            "No tiene acceso al portafolio real sin conexión de broker",
            "Datos de yfinance pueden tener retraso de 15-20 min",
            "No detecta eventos intraday ni noticias en tiempo real",
        ]
        if always_buy_flag:
            known_limitations.append("ALERTA: tasa de compra > 85% — posible sesgo alcista")

        recs = []
        if data_quality_score < 80:
            recs.append("Mejorar manejo de datos faltantes y símbolos inválidos")
        if signal_consistency_score < 70:
            recs.append("Aumentar variedad de señales: añadir análisis fundamental básico")
        if risk_quality_score < 70:
            recs.append("Mejorar evaluación de riesgo: incluir VIX y contexto macro")
        if explanation_quality_score < 80:
            recs.append("Mejorar calidad de explicaciones: añadir contexto de catalizador")

        return {
            "status":                        "ok",
            "data_quality_score":            data_quality_score,
            "signal_consistency_score":      signal_consistency_score,
            "risk_quality_score":            risk_quality_score,
            "portfolio_awareness_score":     portfolio_awareness_score,
            "explanation_quality_score":     explanation_quality_score,
            "overall_reliability_score":     overall_score,
            "symbols_tested":                len(test_symbols),
            "data_errors":                   data_errors,
            "buy_rate_pct":                  round(buy_rate * 100, 1),
            "always_buy_flag":               always_buy_flag,
            "results_summary":               results,
            "known_limitations":             known_limitations,
            "recommendations_to_improve":    recs,
            "real_trade":                    False,
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc), "real_trade": False}


# ── Trader Learning Engine ──────────────────────────────────────────────

@app.get("/api/trader/learning")
def trader_learning_metrics(current_user: dict = Depends(get_optional_user)):
    """Adaptive learning metrics — win rate, calibration, signal performance."""
    if not _PORTFOLIO_AVAILABLE or not _trader_learning:
        return {
            "status":          "unavailable",
            "message":         "Learning engine not loaded",
            "total_outcomes":  0,
            "real_trade":      False,
        }
    try:
        metrics = _trader_learning.get_metrics()
        signal_perf = _trader_learning.get_signal_performance()
        return {
            "status":      "ok",
            "metrics":     metrics,
            "by_signal":   signal_perf.get("by_signal", {}),
            "real_trade":  False,
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc), "real_trade": False}


@app.get("/api/trader/learning/calibration")
def trader_calibration(current_user: dict = Depends(get_optional_user)):
    """Confidence calibration curve — expected vs actual accuracy by bucket."""
    if not _PORTFOLIO_AVAILABLE or not _trader_learning:
        return {"status": "unavailable", "real_trade": False}
    try:
        return _trader_learning.get_confidence_calibration()
    except Exception as exc:
        return {"status": "error", "error": str(exc), "real_trade": False}


@app.get("/api/trader/learning/accuracy")
def trader_recommendation_accuracy(current_user: dict = Depends(get_optional_user)):
    """Per-symbol recommendation accuracy history."""
    if not _PORTFOLIO_AVAILABLE or not _trader_learning:
        return {"status": "unavailable", "real_trade": False}
    try:
        return _trader_learning.get_recommendation_accuracy()
    except Exception as exc:
        return {"status": "error", "error": str(exc), "real_trade": False}


class _OutcomeRecordReq(BaseModel):
    symbol:              str
    signal_type:         str = "BUY"
    confidence:          float = 0.6
    predicted_direction: str = "up"
    actual_return_pct:   float = 0.0
    holding_days:        int = 1
    source:              str = "paper"
    notes:               str = ""


@app.post("/api/trader/learning/record-outcome")
def trader_record_outcome(
    body: _OutcomeRecordReq,
    current_user: dict = Depends(get_optional_user),
):
    """
    Record a trading outcome for adaptive learning.
    Call when a paper trade is closed or a recommendation is evaluated.
    """
    if not _PORTFOLIO_AVAILABLE or not _trader_learning:
        return {"status": "unavailable", "real_trade": False}
    try:
        return _trader_learning.record_outcome(
            symbol=body.symbol.upper(),
            signal_type=body.signal_type.upper(),
            confidence=body.confidence,
            predicted_direction=body.predicted_direction,
            actual_return_pct=body.actual_return_pct,
            holding_days=body.holding_days,
            source=body.source,
            context={"notes": body.notes},
        )
    except Exception as exc:
        return {"status": "error", "error": str(exc), "real_trade": False}


@app.get("/api/trader/learning/score-adjustment/{symbol}")
def trader_score_adjustment(
    symbol: str,
    base_score: float = 50.0,
    current_user: dict = Depends(get_optional_user),
):
    """Get learning-adjusted score for a symbol based on historical outcomes."""
    if not _PORTFOLIO_AVAILABLE or not _trader_learning:
        return {"adjusted_score": base_score, "adjustment": 0, "real_trade": False}
    try:
        return {
            **_trader_learning.get_adapted_score_adjustment(symbol.upper(), base_score),
            "real_trade": False,
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc), "real_trade": False}


# ══════════════════════════════════════════════════════════════════════
# CALENDAR EVENT REMINDER BACKGROUND TASK
# ══════════════════════════════════════════════════════════════════════

async def _calendar_reminder_scheduler() -> None:
    """
    Runs every 60 seconds. Checks calendar events for upcoming reminders.
    Creates a notification at (start_time - reminder_minutes).
    Sets notified=True to prevent duplicates.
    """
    from datetime import timedelta as _td
    _log = logging.getLogger("jarvis.calendar_scheduler")
    _log.info("Calendar reminder scheduler started")
    while True:
        try:
            users_to_check = list({"owner"} | set(_cal_cache.keys()))
            for user_id in users_to_check:
                try:
                    cal   = _cal(user_id)
                    notif = _notif(user_id)
                    now   = datetime.utcnow()
                    for ev in cal.get_events(upcoming_days=1):
                        if ev.get("notified"):
                            continue
                        try:
                            start_dt = datetime.fromisoformat(
                                ev["start"].replace("Z", "").split("+")[0]
                            )
                        except Exception:
                            continue
                        reminder_mins = int(ev.get("reminder_minutes", 30))
                        remind_at = start_dt - _td(minutes=reminder_mins)
                        if now >= remind_at and now < start_dt:
                            mins_left = max(0, int((start_dt - now).total_seconds() / 60))
                            notif.create(
                                title      = f"📅 {ev.get('title', 'Event')}",
                                message    = f"Starts in {mins_left} min",
                                notif_type = "meeting_alert",
                                priority   = "high",
                                action_url = "calendar",
                            )
                            cal.update_event(ev["id"], {"notified": True})
                            _log.info("Reminder fired: %s for user=%s", ev.get("title"), user_id)
                except Exception as _eu:
                    _log.debug("Cal scheduler error for user=%s: %s", user_id, _eu)
        except Exception as _e:
            _log.debug("Cal scheduler outer error: %s", _e)
        await asyncio.sleep(60)
# ===== OUTLOOK WEBHOOK =====

from fastapi import Request
from fastapi.responses import Response

@app.api_route("/api/outlook/webhook", methods=["GET", "POST"])
async def outlook_webhook_canonical(request: Request, validationToken: str = ""):
    """
    Canonical Microsoft Graph webhook endpoint.

    GET or POST with ?validationToken=... → return token as text/plain (Graph handshake).
    POST JSON body                         → enqueue email events, return 202 immediately.

    NOTE: Must respond to the validation request within 10 seconds or Graph rejects the sub.
    """
    from fastapi.responses import PlainTextResponse

    # ── Validation handshake (always unauthenticated) ──────────────────
    vtoken = validationToken or request.query_params.get("validationToken", "")
    if vtoken:
        print(f"[WEBHOOK] Validation handshake received token={vtoken[:20]}...")
        return PlainTextResponse(content=vtoken, status_code=200)

    # ── Lifecycle notifications (keep-alive pings from Graph) ──────────
    # These arrive as POST with no value array — just ack them.
    body_bytes = await request.body()
    print(f"[WEBHOOK] HIT: method={request.method} body={body_bytes[:400]}")

    if not body_bytes:
        return JSONResponse({"queued": 0}, status_code=202)

    try:
        body = await request.json()
    except Exception:
        # Return 202 regardless — never let Graph think the endpoint is down
        return JSONResponse({"queued": 0}, status_code=202)

    # Lifecycle ping (lifecycleEvent field present, no value)
    if "lifecycleEvent" in body:
        print(f"[WEBHOOK] Lifecycle event: {body.get('lifecycleEvent')}")
        return JSONResponse({"status": "lifecycle_ack"}, status_code=202)

    notifications = body.get("value", [])
    queued = 0
    _wlog  = logging.getLogger("jarvis.webhook")

    if not _OUTLOOK_AVAILABLE:
        _wlog.warning("Webhook received but Outlook module not available — dropping %d events", len(notifications))
        return JSONResponse({"queued": 0}, status_code=202)

    for note in notifications:
        received_state = note.get("clientState", "")
        if not _ms_validate_state(received_state):
            _wlog.warning("Webhook: invalid clientState=%r — skipping", received_state)
            continue

        resource   = note.get("resourceData", {})
        msg_id     = resource.get("id")
        change     = note.get("changeType", "")
        sub_id     = note.get("subscriptionId", "")

        print(f"[WEBHOOK] changeType={change} messageId={msg_id} sub={sub_id}")
        _wlog.info("Webhook event: changeType=%s messageId=%s sub=%s", change, msg_id, sub_id)

        if change == "created" and msg_id:
            # Resolve subscription → user_id
            user_id = "owner"
            for uid in _ms_sub_store.all_users():
                s = _ms_sub_store.get(uid)
                if s and s.get("id") == sub_id:
                    user_id = uid
                    break

            ok = await _ms_event_queue.enqueue("new_email", {
                "message_id": msg_id,
                "user_id":    user_id,
                "sub_id":     sub_id,
            })
            if ok:
                queued += 1
                _wlog.info("Enqueued new_email message_id=%s user=%s", msg_id, user_id)

    return JSONResponse({"queued": queued}, status_code=202)