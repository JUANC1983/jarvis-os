import os
import time
import requests

from opsx.secure_execution.executor import SecureExecutor
from opsx.secure_execution.schemas import StoredTask
from opsx.secure_execution.security import verify_signature

SERVER = os.getenv("JARVIS_SERVER_URL", "https://jarvis-os-production.up.railway.app")
API_TOKEN = os.getenv("JARVIS_EXEC_API_TOKEN", "")
AGENT_ID = os.getenv("JARVIS_EXEC_AGENT_ID", "local-secure-agent")

executor = SecureExecutor()

def headers():
    return {"X-JARVIS-EXEC-TOKEN": API_TOKEN}

def execute_task(task: StoredTask):
    cap = task.capability.lower()
    args = task.args or {}
    dry_run = task.dry_run

    if cap == "desktop.open_app":
        return executor.open_app(args.get("app", ""), dry_run=dry_run)

    if cap == "browser.open_url":
        return executor.open_url(args.get("url", ""), dry_run=dry_run)

    if cap == "filesystem.write_text":
        return executor.write_text(args.get("path", ""), args.get("content", ""), dry_run=dry_run)

    if cap == "filesystem.read_text":
        return executor.read_text(args.get("path", ""), dry_run=dry_run)

    return {"status": "blocked", "reason": "unsupported capability"}

def listen():
    print("JARVIS SECURE EXECUTION AGENT RUNNING...")
    print(f"SERVER={SERVER}")
    print(f"AGENT_ID={AGENT_ID}")

    while True:
        try:
            res = requests.get(f"{SERVER}/secure-exec/next-approved", headers=headers(), params={"agent_id": AGENT_ID}, timeout=20)
            if res.status_code != 200:
                time.sleep(3)
                continue

            payload = res.json()
            if not payload:
                time.sleep(3)
                continue

            task = StoredTask(**payload["task"])
            nonce = payload["nonce"]
            issued_at = payload["issued_at"]
            signature = payload["signature"]

            if not verify_signature(task, nonce, issued_at, signature):
                requests.post(
                    f"{SERVER}/secure-exec/tasks/{task.task_id}/result",
                    headers=headers(),
                    json={
                        "task_id": task.task_id,
                        "agent_id": AGENT_ID,
                        "status": "blocked",
                        "result": {"reason": "signature verification failed"},
                    },
                    timeout=20,
                )
                time.sleep(3)
                continue

            result = execute_task(task)
            status = result.get("status", "failed")
            if status == "dry_run":
                status = "succeeded"
            if status not in {"succeeded", "failed", "blocked", "rejected"}:
                status = "failed"

            requests.post(
                f"{SERVER}/secure-exec/tasks/{task.task_id}/result",
                headers=headers(),
                json={
                    "task_id": task.task_id,
                    "agent_id": AGENT_ID,
                    "status": status,
                    "result": result,
                },
                timeout=20,
            )

        except Exception as e:
            print("ERROR:", e)

        time.sleep(3)

if __name__ == "__main__":
    listen()
