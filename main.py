import importlib
import os
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="JARVIS OS",
    version="1.0.0",
    description="Safe boot runtime for Jarvis",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

jarvis = None
jarvis_error: Optional[str] = None
loaded_routers = []
failed_routers = []


def safe_boot_jarvis() -> None:
    global jarvis, jarvis_error

    try:
        from core.jarvis_os import JarvisOS
        jarvis = JarvisOS()
        jarvis_error = None
        print("[OK] JarvisOS loaded")
    except Exception as e:
        jarvis = None
        jarvis_error = str(e)
        print(f"[WARNING] JarvisOS failed to load: {jarvis_error}")


def safe_include_router(module_path: str) -> None:
    global loaded_routers, failed_routers

    try:
        module = importlib.import_module(module_path)
        router = getattr(module, "router", None)

        if router is None:
            failed_routers.append({"module": module_path, "error": "router not found"})
            print(f"[WARNING] Router missing in {module_path}")
            return

        app.include_router(router)
        loaded_routers.append(module_path)
        print(f"[OK] Router loaded: {module_path}")

    except Exception as e:
        failed_routers.append({"module": module_path, "error": str(e)})
        print(f"[WARNING] Router failed: {module_path} -> {e}")


safe_boot_jarvis()

ROUTERS = [
    "api.secure_execution_routes",
    "api.voice_routes",
    "api.whatsapp_routes",
    "api.dashboard_routes",
    "api.trader_alpha_routes",
    "api.golf_routes",
    "api.golf_vision_routes",
    "api.operator_routes",
    "api.opportunity_routes",
    "api.command_center_routes",
    "api.communication_routes",
    "api.executive_intelligence_routes",
    "api.global_market_routes",
    "api.global_opportunity_radar_pro_routes",
    "api.strategic_council_routes",
    "api.strategic_foresight_pro_routes",
    "api.apple_watch_routes",
    "api.autonomous_routes",
    "api.computer_agent_routes",
    "api.agent_orchestrator_routes",
    "api.agent_optimization_routes",
    "api.ops_routes",
    "api.health_performance_routes",
    "api.silicon_valley_routes",
    "api.computer_control_routes",
]

for module_path in ROUTERS:
    safe_include_router(module_path)


@app.get("/")
def root():
    return {
        "status": "ok",
        "service": "jarvis",
        "jarvis_loaded": jarvis is not None,
        "error": jarvis_error,
        "loaded_routers": loaded_routers,
        "failed_router_count": len(failed_routers),
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "jarvis_loaded": jarvis is not None,
        "error": jarvis_error,
        "openai_key_present": bool(os.getenv("OPENAI_API_KEY", "").strip()),
        "loaded_routers": loaded_routers,
        "failed_routers": failed_routers,
        "jarvis_health": jarvis.health() if jarvis else None,
    }


@app.get("/debug/env")
def debug_env():
    api_key = os.getenv("OPENAI_API_KEY", "")
    return {
        "openai_key_present": bool(api_key.strip()),
        "openai_key_prefix": api_key[:12] if api_key else None,
        "env_keys": sorted(list(os.environ.keys())),
    }


@app.post("/chat")
def chat(payload: dict):
    if jarvis is None:
        return {
            "ok": False,
            "error": jarvis_error or "Jarvis not available",
        }

    message = str(payload.get("message", "")).strip()
    if not message:
        return {
            "ok": False,
            "error": "message is required",
        }

    try:
        return {
            "ok": True,
            "response": jarvis.process(message),
        }
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
        }
