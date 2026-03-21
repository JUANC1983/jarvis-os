from enum import Enum
from typing import Any, Dict, Optional, Literal
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
import uuid


class TaskStatus(str, Enum):
    pending_approval = "pending_approval"
    approved = "approved"
    rejected = "rejected"
    dispatched = "dispatched"
    succeeded = "succeeded"
    failed = "failed"
    blocked = "blocked"
    expired = "expired"


class RiskLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class TaskRequest(BaseModel):
    capability: str
    action: str
    args: Dict[str, Any] = Field(default_factory=dict)
    summary: str = ""
    dry_run: bool = True
    origin: str = "jarvis-cloud"


class StoredTask(BaseModel):
    task_id: str
    capability: str
    action: str
    args: Dict[str, Any]
    summary: str
    risk: RiskLevel
    status: TaskStatus
    dry_run: bool
    origin: str
    requires_approval: bool
    created_at: str
    expires_at: str
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    dispatched_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Optional[Dict[str, Any]] = None

    @staticmethod
    def build(task: TaskRequest, risk: RiskLevel, requires_approval: bool, ttl_minutes: int = 10) -> "StoredTask":
        now = datetime.utcnow()
        return StoredTask(
            task_id=str(uuid.uuid4()),
            capability=task.capability,
            action=task.action,
            args=task.args,
            summary=task.summary,
            risk=risk,
            status=TaskStatus.pending_approval if requires_approval else TaskStatus.approved,
            dry_run=task.dry_run,
            origin=task.origin,
            requires_approval=requires_approval,
            created_at=now.isoformat(),
            expires_at=(now + timedelta(minutes=ttl_minutes)).isoformat(),
        )


class ApprovalRequest(BaseModel):
    approver: str
    note: str = ""


class SignedDispatch(BaseModel):
    task: StoredTask
    signature: str
    nonce: str
    issued_at: str


class TaskResult(BaseModel):
    task_id: str
    agent_id: str
    status: Literal["succeeded", "failed", "blocked", "rejected"]
    result: Dict[str, Any] = Field(default_factory=dict)
