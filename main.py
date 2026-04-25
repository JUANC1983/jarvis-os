from datetime import datetime
from pathlib import Path
import json
import os
import shutil
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


# ============================================================
# LLM — OpenAI wrapper with optional json_mode
# ============================================================
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


# ============================================================
# CHAT MEMORY — last 5 exchanges (10 messages)
# ============================================================
_HISTORY_LIMIT = 5
_chat_history: list[dict] = []


def _push_history(role: str, content: str) -> None:
    _chat_history.append({"role": role, "content": content})
    while len(_chat_history) > _HISTORY_LIMIT * 2:
        _chat_history.pop(0)


# ============================================================
# CONTEXT — pipeline + news, cached 2 min, never blocks chat
# ============================================================
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


# ============================================================
# KEYWORD FALLBACK — intent + dispatch (demoted to fallback)
# ============================================================
_KNOWN_SYMBOLS = {
    "NVDA", "AAPL", "MSFT", "AMZN", "META", "TSLA", "PLTR", "COIN",
    "SMCI", "XOM", "CVX", "BTC", "ETH", "SPY", "QQQ", "GOOGL", "AMD",
    "NFLX", "GOOG", "UBER", "SBUX", "DIS", "BA", "GLD", "SLV",
}


def _detect_intent(message: str) -> str:
    low = message.lower()
    if any(w in low for w in ["analiz", "analyze", "trade", "setup", "entry", "chart", "signal"]):
        return "analyze"
    if any(w in low for w in ["recommend", "recomend", "best", "top pick", "scan", "oportunidad", "mejores"]):
        return "recommend"
    if any(w in low for w in ["news", "noticias", "headline", "latest", "que paso", "what happened"]):
        return "news"
    return "general"


def _extract_symbol(message: str) -> str | None:
    for word in message.upper().split():
        clean = word.strip(".,!?;:()")
        if clean in _KNOWN_SYMBOLS:
            return clean
    return None


def _dispatch_tool(intent: str, message: str) -> dict | None:
    if intent == "analyze":
        sym = _extract_symbol(message)
        if sym:
            try:
                return brain.trader(sym)
            except Exception:
                return None
    elif intent == "recommend":
        try:
            return brain_pro.auto_scan()
        except Exception:
            return None
    elif intent == "news":
        try:
            return {"items": news_engine.fetch_categorized(max_per_category=4)}
        except Exception:
            return None
    return None


# ============================================================
# PROMPTS
# ============================================================

# Pass 1 — LLM decides which tool (if any) to call.
# Must mention JSON so response_format=json_object is valid.
_DECISION_PROMPT = """\
You are the JARVIS decision engine for Juan Camilo Montenegro.
Your job: read the user message and decide whether a tool call is needed.

Available tools:
  analyze_asset(symbol)  — deep signal analysis for a specific stock or crypto
  market_scan()          — full market intelligence: top setups, macro regime, confidence
  get_news()             — latest categorised financial and market headlines

Rules:
- Use "analyze"  when the user asks about a specific ticker (NVDA, BTC, AAPL …)
- Use "scan"     when the user asks for top picks, market overview, recommendations, or opportunities
- Use "news"     when the user asks about recent events, headlines, or what is happening in markets
- Use "none"     for everything else — greetings, opinions, strategy questions, definitions
- Respond in the same language the user writes in

You MUST respond with valid JSON and nothing else:
{
  "action": "none | analyze | scan | news",
  "symbol": "UPPERCASE_TICKER or null",
  "reason": "one sentence explanation",
  "reply":  "user-facing answer (only populate when action is none, else leave empty)"
}\
"""

# Pass 2 — LLM synthesises a final reply using the tool result.
_SYNTHESIS_PROMPT = """\
You are JARVIS, an AI operating system and market intelligence assistant for Juan Camilo Montenegro.
You have just executed a real-time tool and the result is injected below.
Use it to give a sharp, specific, actionable answer.
Rules:
- Be concise: 2–4 sentences maximum unless more detail was explicitly requested
- Use exact numbers from the data (scores, prices, percentages)
- Never invent data beyond what is provided
- Respond in the same language the user writes in
- Sound confident and clear, not robotic\
"""

# Single-pass fallback prompt (used when decision pass is bypassed)
_FALLBACK_PROMPT = """\
You are JARVIS, an AI market intelligence assistant for Juan Camilo Montenegro.
You have access to real-time pipeline state and live news.
Be concise (2–4 sentences), direct, actionable.
Use exact numbers from your context. Respond in the user's language.\
"""


# ============================================================
# AGENT CHAT — two-pass: LLM decides → tool → LLM synthesises
# ============================================================
def _agent_chat(message: str) -> dict | None:
    context = _get_context()

    # ── PASS 1: decision ─────────────────────────────────────
    decision_system = _DECISION_PROMPT
    if context:
        decision_system += f"\n\n[Live System Context]\n{context}"

    decision_messages = [
        {"role": "system", "content": decision_system},
        *list(_chat_history),
        {"role": "user", "content": message},
    ]

    raw = generate_response(decision_messages, json_mode=True)
    if not raw:
        return None

    try:
        decision = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return None

    action = (decision.get("action") or "none").lower().strip()
    symbol = (decision.get("symbol") or "").upper().strip() or None
    direct_reply = (decision.get("reply") or "").strip()

    # No tool needed — return the LLM's direct answer
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

    if action == "analyze":
        sym = symbol or _extract_symbol(message)
        if sym:
            try:
                tool_result = brain.trader(sym)
            except Exception:
                pass
    elif action == "scan":
        try:
            tool_result = brain_pro.auto_scan()
        except Exception:
            pass
    elif action == "news":
        try:
            tool_result = {"items": news_engine.fetch_categorized(max_per_category=4)}
        except Exception:
            pass

    # ── PASS 2: synthesis ────────────────────────────────────
    synthesis_system = _SYNTHESIS_PROMPT
    if context:
        synthesis_system += f"\n\n[Live System Context]\n{context}"
    if tool_result:
        snippet = json.dumps(tool_result, default=str)[:1400]
        synthesis_system += f"\n\n[Tool: {action} result]\n{snippet}"

    synthesis_messages = [
        {"role": "system", "content": synthesis_system},
        *list(_chat_history),
        {"role": "user", "content": message},
    ]

    final_reply = generate_response(synthesis_messages, json_mode=False)

    # If synthesis fails but tool ran, surface what we know
    if not final_reply:
        if tool_result and action == "scan":
            summary = tool_result.get("summary", "")
            actions = tool_result.get("actions", [])
            final_reply = summary + (" — " + actions[0] if actions else "")
        elif not final_reply:
            return None

    _push_history("user", message)
    _push_history("assistant", final_reply)

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


# ============================================================
# KEYWORD CHAT — single-pass fallback (keyword → tool → LLM)
# ============================================================
def _llm_chat(message: str) -> dict | None:
    intent      = _detect_intent(message)
    tool_result = _dispatch_tool(intent, message)
    context     = _get_context()

    system_content = _FALLBACK_PROMPT
    if context:
        system_content += f"\n\n[Live System Context]\n{context}"
    if tool_result:
        snippet = json.dumps(tool_result, default=str)[:1400]
        system_content += f"\n\n[Tool Result — {intent}]\n{snippet}"

    messages = [{"role": "system", "content": system_content}]
    messages.extend(list(_chat_history))
    messages.append({"role": "user", "content": message})

    reply = generate_response(messages)
    if not reply:
        return None

    _push_history("user", message)
    _push_history("assistant", reply)

    sym    = _extract_symbol(message)
    action = (f"analyze:{sym}" if sym and intent == "analyze"
              else "auto_scan" if intent == "recommend"
              else "news_fetch" if intent == "news"
              else "")

    return {
        "type":       "llm_chat",
        "reply":      reply,
        "summary":    reply[:120] + ("..." if len(reply) > 120 else ""),
        "details":    tool_result or {},
        "action":     action,
        "confidence": 0.88 if tool_result else 0.70,
        "source":     "llm_fallback",
    }


# ============================================================
# PYDANTIC MODELS
# ============================================================
class ChatRequest(BaseModel):
    message: str
    domain: str | None = "general"


# ============================================================
# ROUTES
# ============================================================
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
# HOME — persistent tasks + meetings
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
# CHAT — agent (two-pass) → keyword fallback → ProductBrain
# =========================
@app.post("/chat")
def chat(req: ChatRequest):
    try:
        # Tier 1: LLM decides tool autonomously (two-pass agent)
        result = _agent_chat(req.message)

        # Tier 2: keyword intent → tool → LLM (single-pass)
        if result is None:
            result = _llm_chat(req.message)

        # Tier 3: rule-based ProductBrain (no LLM)
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
# AUTO JARVIS — full intelligence scan via ProductBrainPro
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
# TASKS — persistent
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
# MEETINGS — persistent
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
# SCHEDULE MEETING (from floating button)
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
# ASSETS — persistent
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
# PIPELINE — derived from real agent activity via AgentOrchestratorPro
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
# AGENTS — real orchestrator state
# =========================
@app.get("/dashboard/agents")
def agents():
    try:
        items = orchestrator.agent_status_snapshot()
        return {"items": items}
    except Exception as e:
        return {"items": [], "error": str(e)}


# =========================
# NEWS FEED — real categorised RSS via NewsIntelligenceEngine
# =========================
@app.get("/dashboard/news")
def news():
    try:
        items = news_engine.fetch_categorized(max_per_category=5)
        return {"items": items}
    except Exception as e:
        return {"items": [], "error": str(e)}


# =========================
# GOLF — wires GolfCourseDatabase + Open-Meteo weather
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
