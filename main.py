from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

jarvis = None
jarvis_error = None

def boot_jarvis():
    global jarvis, jarvis_error
    try:
        from core.jarvis_os import JarvisOS
        jarvis = JarvisOS()
        print("[OK] Jarvis booted")
    except Exception as e:
        jarvis_error = str(e)
        print("[ERROR] Jarvis failed:", e)

boot_jarvis()

@app.get("/")
def root():
    return {
        "status": "online",
        "jarvis_loaded": jarvis is not None,
        "error": jarvis_error
    }

@app.get("/health")
def health():
    return {
        "status": "ok",
        "jarvis_loaded": jarvis is not None,
        "error": jarvis_error
    }

@app.post("/chat")
def chat(payload: dict):
    if jarvis is None:
        return {"error": jarvis_error}
    return {"response": "ok"}

# SAFE ROUTER LOADING
def safe_router(path):
    try:
        module = __import__(path, fromlist=["router"])
        return module.router
    except Exception as e:
        print(f"[WARNING] router {path} failed:", e)
        return None

routes = [
    "api.secure_execution_routes",
]

for r in routes:
    router = safe_router(r)
    if router:
        app.include_router(router)
