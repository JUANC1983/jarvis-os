from fastapi import FastAPI
from core.jarvis_os import JarvisOS

app = FastAPI()

jarvis = None

@app.on_event("startup")
def startup_event():
    global jarvis
    try:
        jarvis = JarvisOS()
        print("? Jarvis initialized")
    except Exception as e:
        print(f"? Jarvis failed to init: {e}")
        jarvis = None


@app.get("/health")
def health():
    return {
        "status": "ok",
        "jarvis_loaded": jarvis is not None
    }


@app.get("/")
def root():
    return {"message": "Jarvis OS running"}
