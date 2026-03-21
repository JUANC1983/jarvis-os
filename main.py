from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

app = FastAPI(
    title="JARVIS OS",
    version="1.0",
    description="Autonomous Intelligence System"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

jarvis = None
jarvis_boot_error = None

def safe_import_router(path, name):
    try:
        module = __import__(path, fromlist=[name])
        return getattr(module, name)
    except Exception as e:
        print(f"[WARNING] Failed to load {path}: {e}")
        return None

try:
    from core.jarvis_os import JarvisOS
    jarvis = JarvisOS()
    print("[OK] JarvisOS booted")
except Exception as e:
    jarvis_boot_error = str(e)
    print(f"[WARNING] JarvisOS boot failed: {e}")

@app.get("/")
def root():
    return {
        "status": "JARVIS ONLINE",
        "jarvis_loaded": jarvis is not None,
        "boot_error": jarvis_boot_error
    }

@app.get("/health")
def health():
    return {
        "status": "ok",
        "jarvis_loaded": jarvis is not None,
        "boot_error": jarvis_boot_error
    }

@app.post("/chat")
async def chat_endpoint(payload: dict):
    if jarvis is None:
        return {
            "error": "JarvisOS not available",
            "boot_error": jarvis_boot_error
        }

    try:
        message = payload.get("message", "")
        response = jarvis.process(message)
        return {"response": response}
    except Exception as e:
        return {"error": str(e)}

routes_to_load = [
    ("api.voice_routes", "router"),
    ("api.whatsapp_routes", "router"),
    ("api.dashboard_routes", "router"),
    ("api.trader_alpha_routes", "router"),
    ("api.golf_routes", "router"),
    ("api.secure_execution_routes", "router"),
]

for module_path, router_name in routes_to_load:
    router = safe_import_router(module_path, router_name)
    if router:
        app.include_router(router)
