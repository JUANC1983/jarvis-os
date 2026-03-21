from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Core system
from core.jarvis_os import JarvisOS

# Routers (SAFE LOAD)
def safe_import_router(path, name):
    try:
        module = __import__(path, fromlist=[name])
        return getattr(module, name)
    except Exception as e:
        print(f"[WARNING] Failed to load {path}: {e}")
        return None


app = FastAPI(
    title="JARVIS OS",
    version="1.0",
    description="Autonomous Intelligence System"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# INIT CORE
jarvis = JarvisOS()


# =========================
# HEALTH CHECK
# =========================
@app.get("/")
def root():
    return {
        "status": "JARVIS ONLINE",
        "version": "1.0"
    }


@app.get("/health")
def health():
    return {"status": "ok"}


# =========================
# CORE CHAT ENDPOINT
# =========================
@app.post("/chat")
async def chat_endpoint(payload: dict):
    try:
        message = payload.get("message", "")
        response = jarvis.process(message)
        return {"response": response}
    except Exception as e:
        return {"error": str(e)}


# =========================
# OPTIONAL ROUTES (SAFE LOAD)
# =========================

routes_to_load = [
    ("api.voice_routes", "router"),
    ("api.whatsapp_routes", "router"),
    ("api.dashboard_routes", "router"),
    ("api.trader_alpha_routes", "router"),
    ("api.golf_routes", "router"),
]

for module_path, router_name in routes_to_load:
    router = safe_import_router(module_path, router_name)
    if router:
        app.include_router(router)
