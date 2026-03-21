import importlib
import os
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(
    title="JARVIS OS",
    version="1.0.0",
    description="Jarvis backend + futuristic dashboard",
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

DASHBOARD_DIR = os.path.join(os.path.dirname(__file__), "dashboard")
DASHBOARD_HTML = os.path.join(DASHBOARD_DIR, "jarvis_futuristic.html")


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
    "api.operator_routes",
    "api.command_center_routes",
    "api.executive_intelligence_routes",
    "api.strategic_council_routes",
    "api.strategic_foresight_pro_routes",
    "api.autonomous_routes",
    "api.computer_agent_routes",
    "api.agent_orchestrator_routes",
    "api.agent_optimization_routes",
    "api.health_performance_routes",
]

for module_path in ROUTERS:
    safe_include_router(module_path)

if os.path.isdir(DASHBOARD_DIR):
    app.mount("/static-dashboard", StaticFiles(directory=DASHBOARD_DIR), name="static-dashboard")


@app.get("/")
def root():
    if os.path.isfile(DASHBOARD_HTML):
        return RedirectResponse(url="/dashboard")
    return {
        "status": "ok",
        "service": "jarvis",
        "jarvis_loaded": jarvis is not None,
        "error": jarvis_error,
        "loaded_routers": loaded_routers,
        "failed_router_count": len(failed_routers),
    }


@app.get("/dashboard")
def dashboard():
    if os.path.isfile(DASHBOARD_HTML):
        return FileResponse(DASHBOARD_HTML)
    return {
        "ok": False,
        "error": "dashboard/jarvis_futuristic.html not found"
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
