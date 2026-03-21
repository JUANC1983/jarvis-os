from fastapi import APIRouter, Header, HTTPException
from datetime import datetime
import secrets

from opsx.secure_execution.schemas import TaskRequest, StoredTask, ApprovalRequest, TaskResult, SignedDispatch, TaskStatus
from opsx.secure_execution.policy_engine import validate_task, classify_risk, requires_approval
from opsx.secure_execution.task_store import save_task, get_task, update_task, next_dispatchable, all_tasks
from opsx.secure_execution.audit_log import log_event
from opsx.secure_execution.security import get_api_token, sign_task

router = APIRouter(prefix="/secure-exec", tags=["secure-exec"])

def _auth(x_jarvis_exec_token: str | None):
    expected = get_api_token()
    if not expected:
        raise HTTPException(status_code=500, detail="JARVIS_EXEC_API_TOKEN not configured")
    if x_jarvis_exec_token != expected:
        raise HTTPException(status_code=401, detail="unauthorized")

@router.get("/health")
def secure_exec_health():
    return {"status": "ok", "service": "secure-exec"}

@router.post("/submit")
def submit_task(task: TaskRequest, x_jarvis_exec_token: str | None = Header(default=None)):
    _auth(x_jarvis_exec_token)

    allowed, reason = validate_task(task)
    if not allowed:
        log_event("task_blocked_policy", {"task": task.model_dump(), "reason": reason})
        return {"status": "blocked", "reason": reason}

    risk = classify_risk(task)
    approval_needed = requires_approval(task)
    stored = StoredTask.build(task=task, risk=risk, requires_approval=approval_needed)
    save_task(stored)
    log_event("task_submitted", {"task_id": stored.task_id, "risk": stored.risk, "requires_approval": stored.requires_approval})

    return {
        "status": stored.status,
        "task_id": stored.task_id,
        "risk": stored.risk,
        "requires_approval": stored.requires_approval,
    }

@router.get("/tasks")
def list_tasks(x_jarvis_exec_token: str | None = Header(default=None)):
    _auth(x_jarvis_exec_token)
    return {"items": [t.model_dump() for t in all_tasks()]}

@router.get("/tasks/{task_id}")
def get_task_route(task_id: str, x_jarvis_exec_token: str | None = Header(default=None)):
    _auth(x_jarvis_exec_token)
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="task not found")
    return task

@router.post("/tasks/{task_id}/approve")
def approve_task(task_id: str, approval: ApprovalRequest, x_jarvis_exec_token: str | None = Header(default=None)):
    _auth(x_jarvis_exec_token)
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="task not found")
    if task.status not in {TaskStatus.pending_approval, TaskStatus.approved}:
        return {"status": "ignored", "reason": f"cannot approve task in status {task.status}"}

    updated = update_task(task_id, {
        "status": TaskStatus.approved.value,
        "approved_by": approval.approver,
        "approved_at": datetime.utcnow().isoformat(),
    })
    log_event("task_approved", {"task_id": task_id, "approver": approval.approver, "note": approval.note})
    return updated

@router.post("/tasks/{task_id}/reject")
def reject_task(task_id: str, approval: ApprovalRequest, x_jarvis_exec_token: str | None = Header(default=None)):
    _auth(x_jarvis_exec_token)
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="task not found")

    updated = update_task(task_id, {
        "status": TaskStatus.rejected.value,
        "approved_by": approval.approver,
        "approved_at": datetime.utcnow().isoformat(),
    })
    log_event("task_rejected", {"task_id": task_id, "approver": approval.approver, "note": approval.note})
    return updated

@router.get("/next-approved")
def next_approved(agent_id: str, x_jarvis_exec_token: str | None = Header(default=None)):
    _auth(x_jarvis_exec_token)
    task = next_dispatchable()
    if not task:
        return {}

    nonce = secrets.token_hex(16)
    issued_at = datetime.utcnow().isoformat()
    signature = sign_task(task, nonce, issued_at)

    update_task(task.task_id, {
        "status": TaskStatus.dispatched.value,
        "dispatched_at": issued_at,
    })
    log_event("task_dispatched", {"task_id": task.task_id, "agent_id": agent_id})

    return SignedDispatch(task=task, signature=signature, nonce=nonce, issued_at=issued_at)

@router.post("/tasks/{task_id}/result")
def task_result(task_id: str, result: TaskResult, x_jarvis_exec_token: str | None = Header(default=None)):
    _auth(x_jarvis_exec_token)
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="task not found")

    status_map = {
        "succeeded": TaskStatus.succeeded.value,
        "failed": TaskStatus.failed.value,
        "blocked": TaskStatus.blocked.value,
        "rejected": TaskStatus.rejected.value,
    }

    updated = update_task(task_id, {
        "status": status_map[result.status],
        "completed_at": datetime.utcnow().isoformat(),
        "result": result.result,
    })
    log_event("task_result", {"task_id": task_id, "agent_id": result.agent_id, "status": result.status, "result": result.result})
    return updated
