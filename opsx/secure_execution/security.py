import hashlib
import hmac
import json
import os
from datetime import datetime
from opsx.secure_execution.schemas import StoredTask

def get_api_token() -> str:
    return os.getenv("JARVIS_EXEC_API_TOKEN", "")

def get_shared_secret() -> str:
    return os.getenv("JARVIS_EXEC_SHARED_SECRET", "")

def sign_task(task: StoredTask, nonce: str, issued_at: str) -> str:
    secret = get_shared_secret().encode("utf-8")
    payload = {
        "task": task.model_dump(),
        "nonce": nonce,
        "issued_at": issued_at,
    }
    msg = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hmac.new(secret, msg, hashlib.sha256).hexdigest()

def verify_signature(task: StoredTask, nonce: str, issued_at: str, signature: str) -> bool:
    expected = sign_task(task, nonce, issued_at)
    return hmac.compare_digest(expected, signature)
