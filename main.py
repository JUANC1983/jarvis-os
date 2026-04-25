from datetime import datetime
from pathlib import Path
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

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from core.product_brain import ProductBrain
from core.product_brain_pro import ProductBrainPro
from core.dashboard_workspace_engine import DashboardWorkspaceEngine
from core.meetings_engine import MeetingsEngine
from core.agent_orchestrator_pro import AgentOrchestratorPro
from core.news_intelligence_engine import NewsIntelligenceEngine
from core.golf_dashboard_engine import GolfDashboardEngine

app = FastAPI(title="JARVIS OS")
brain           = ProductBrain()
brain_pro       = ProductBrainPro()
workspace       = DashboardWorkspaceEngine()
meetings_engine = MeetingsEngine()
orchestrator    = AgentOrchestratorPro()
news_engine     = NewsIntelligenceEngine()
golf_engine     = GolfDashboardEngine()

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

    # Finance / market
    if any(w in low for w in [
        "analiz", "analyze", "trade", "setup", "entry", "chart",
        "signal", "precio de", "price of",
        "buy", "sell", "comprar", "vender",
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
You are JARVIS — the AI operating system for Juan Camilo Montenegro.
A real-time tool just ran. The result is injected below as [Tool result].
Your job: turn that data into a sharp, human, actionable answer.

Style guide:
- Maximum 3 sentences unless the user explicitly asked for more detail
- Use specific numbers, scores, and percentages from the data
- Short sentences. Natural rhythm. Easy to read aloud.
- Sound like a sharp, confident advisor — not a robot, not a disclaimer machine
- Respond in the exact same language the user wrote in
- Medical/legal outputs: include the disclaimer in one short sentence at the end
- If data is sparse, say what you know and stop — never fabricate
- If [Memory] is provided, use it to personalize tone — reference past context
  naturally, never quote it verbatim\
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
        elif action == "medical":
            tool_result = orchestrator.execute(message, "medical")
        elif action == "legal":
            tool_result = orchestrator.execute(message, "legal")
        elif action == "fitness":
            tool_result = orchestrator.execute(message, "fitness")
        elif action == "coach":
            tool_result = orchestrator.execute(message, "coach")
    except Exception:
        pass

    # ── PASS 2: synthesis ─────────────────────────────────────
    synthesis_system = _SYNTHESIS_PROMPT
    if context:
        synthesis_system += f"\n\n[Live System Context]\n{context}"
    if mem_ctx:
        synthesis_system += f"\n\n[Memory]\n{mem_ctx}"
    if tool_result:
        snippet = json.dumps(tool_result, default=str)[:1400]
        synthesis_system += f"\n\n[Tool: {action}]\n{snippet}"

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
def dashboard_home():
    try:
        return workspace.home("Juan Camilo")
    except Exception:
        return {
            "greeting":     "JARVIS ready",
            "date":         datetime.now().strftime("%A %d %B %Y"),
            "owner_name":   "Juan Camilo",
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
def add_task(data: dict):
    try:
        text     = (data.get("text") or "").strip()
        priority = (data.get("priority") or "medium").strip().lower()
        day      = (data.get("day") or "today").strip().lower()

        if not text:
            raise HTTPException(status_code=400, detail="text is required")
        if priority not in ["high", "medium", "low"]:
            priority = "medium"

        return workspace.add_task(text, priority, day)
    except HTTPException:
        raise
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@app.post("/dashboard/tasks/{task_id}/toggle")
def toggle_task(task_id: str):
    try:
        return workspace.toggle_task(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# =========================
# MEETINGS
# =========================
@app.post("/dashboard/meetings")
def add_meeting(data: dict):
    try:
        title      = (data.get("title") or "").strip()
        time_value = (data.get("time") or "").strip()
        notes      = (data.get("notes") or "").strip()

        if not title or not time_value:
            raise HTTPException(status_code=400, detail="title and time are required")

        return workspace.add_meeting(title, time_value, notes)
    except HTTPException:
        raise
    except Exception as e:
        return {"status": "error", "detail": str(e)}


# =========================
# SCHEDULE MEETING
# =========================
@app.post("/dashboard/schedule-meeting")
def schedule_meeting(data: dict):
    try:
        objective      = (data.get("objective") or "").strip()
        datetime_value = (data.get("datetime") or "").strip()

        if not objective or not datetime_value:
            raise HTTPException(status_code=400, detail="objective and datetime are required")

        meeting = meetings_engine.add_meeting_datetime(
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
    return {
        "signals":  3,
        "accuracy": "72%",
        "risk":     "medium",
        "exposure": "45%",
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
# AGENT PERFORMANCE STATS
# =========================
@app.get("/jarvis/agents/performance")
def agent_performance():
    try:
        return {"items": orchestrator.agent_performance_stats()}
    except Exception as e:
        return {"items": [], "error": str(e)}


# =========================
# MEMORY STATS
# =========================
@app.get("/jarvis/memory/stats")
def memory_stats():
    try:
        return _mem().stats()
    except Exception as e:
        return {"total_entries": 0, "vector_ready": False, "error": str(e)}
