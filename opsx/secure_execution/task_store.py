import json
from pathlib import Path
from typing import List, Optional
from datetime import datetime
from opsx.secure_execution.schemas import StoredTask, TaskStatus

STORE_PATH = Path("data/secure_execution_tasks.json")

def _load_raw() -> list:
    if not STORE_PATH.exists():
        STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        STORE_PATH.write_text("[]", encoding="utf-8")
        return []
    text = STORE_PATH.read_text(encoding="utf-8").strip() or "[]"
    return json.loads(text)

def _save_raw(items: list):
    STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STORE_PATH.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

def all_tasks() -> List[StoredTask]:
    return [StoredTask(**x) for x in _load_raw()]

def save_task(task: StoredTask):
    items = _load_raw()
    items.append(task.model_dump())
    _save_raw(items)

def update_task(task_id: str, patch: dict) -> Optional[StoredTask]:
    items = _load_raw()
    updated = None
    for i, item in enumerate(items):
        if item.get("task_id") == task_id:
            item.update(patch)
            items[i] = item
            updated = StoredTask(**item)
            break
    _save_raw(items)
    return updated

def get_task(task_id: str) -> Optional[StoredTask]:
    for item in _load_raw():
        if item.get("task_id") == task_id:
            return StoredTask(**item)
    return None

def next_dispatchable() -> Optional[StoredTask]:
    now = datetime.utcnow().isoformat()
    items = _load_raw()
    for item in items:
        if item.get("status") == TaskStatus.approved.value and item.get("expires_at", "") > now:
            return StoredTask(**item)
    return None
