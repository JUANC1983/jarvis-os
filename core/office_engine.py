"""Office Engine — Colleagues, Work Tasks, Expenses per user.

Persisted as JSON under data/office/{user_id}/
Thread-safe; all public methods return dicts ready for JSON serialisation.
"""
from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


def _now() -> str:
    return datetime.utcnow().isoformat()

def _gen_id() -> str:
    return hashlib.sha256(datetime.utcnow().isoformat().encode()).hexdigest()[:10]


_TASK_STATUSES  = ("todo", "doing", "done")
_PRIORITIES     = ("low", "medium", "high", "critical")
_EXPENSE_CATS   = ("travel", "meals", "supplies", "software", "equipment", "other")
_EXPENSE_STATUS = ("pending", "approved", "rejected", "paid")


class OfficeEngine:
    MODULES = ("colleagues", "tasks", "expenses")

    def __init__(self, base_dir: str, user_id: str = "owner") -> None:
        self._base = Path(base_dir)
        self._user = user_id
        self._lock = threading.Lock()
        self._base.mkdir(parents=True, exist_ok=True)
        for module in self.MODULES:
            p = self._path(module)
            if not p.exists():
                self._write(module, {"items": []})

    # ── Colleagues ──────────────────────────────────────────────────────

    def add_colleague(self, name: str, role: str = "", department: str = "",
                      email: str = "", phone: str = "", notes: str = "") -> Dict:
        return self._append("colleagues", {
            "id": _gen_id(), "name": name, "role": role,
            "department": department, "email": email,
            "phone": phone, "notes": notes, "created_at": _now(),
        })

    def get_colleagues(self) -> List[Dict]:
        items = self._read("colleagues")["items"]
        return sorted(items, key=lambda x: x.get("name", ""))

    def update_colleague(self, colleague_id: str, **kwargs) -> Optional[Dict]:
        with self._lock:
            d = self._read("colleagues")
            for item in d["items"]:
                if item["id"] == colleague_id:
                    for k, v in kwargs.items():
                        if k in ("name", "role", "department", "email", "phone", "notes"):
                            item[k] = v
                    item["updated_at"] = _now()
                    self._write("colleagues", d)
                    return item
        return None

    def delete_colleague(self, colleague_id: str) -> bool:
        return self._delete("colleagues", colleague_id)

    # ── Work Tasks ──────────────────────────────────────────────────────

    def add_task(self, title: str, due: str = "", priority: str = "medium",
                 assigned_to: str = "", project: str = "", notes: str = "") -> Dict:
        return self._append("tasks", {
            "id": _gen_id(), "title": title, "due": due,
            "priority": priority, "status": "todo",
            "assigned_to": assigned_to, "project": project,
            "notes": notes, "created_at": _now(),
        })

    def get_tasks(self, status: Optional[str] = None,
                  include_done: bool = False) -> List[Dict]:
        items = self._read("tasks")["items"]
        if not include_done:
            items = [i for i in items if i.get("status") != "done"]
        if status:
            items = [i for i in items if i.get("status") == status]
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        return sorted(items, key=lambda x: (
            priority_order.get(x.get("priority", "medium"), 2),
            x.get("due", ""),
        ))

    def update_task_status(self, task_id: str, status: str) -> Optional[Dict]:
        with self._lock:
            d = self._read("tasks")
            for item in d["items"]:
                if item["id"] == task_id:
                    item["status"] = status
                    if status == "done":
                        item["completed_at"] = _now()
                    self._write("tasks", d)
                    return item
        return None

    def delete_task(self, task_id: str) -> bool:
        return self._delete("tasks", task_id)

    # ── Expenses ────────────────────────────────────────────────────────

    def add_expense(self, title: str, amount: float, category: str = "other",
                    currency: str = "COP", date: str = "", reimbursable: bool = True,
                    notes: str = "") -> Dict:
        return self._append("expenses", {
            "id": _gen_id(), "title": title, "amount": amount,
            "category": category, "currency": currency,
            "date": date or _now()[:10], "reimbursable": reimbursable,
            "status": "pending", "notes": notes, "created_at": _now(),
        })

    def get_expenses(self, include_closed: bool = False) -> List[Dict]:
        items = self._read("expenses")["items"]
        if not include_closed:
            items = [i for i in items if i.get("status") not in ("paid", "rejected")]
        return sorted(items, key=lambda x: x.get("date", ""), reverse=True)

    def update_expense_status(self, expense_id: str, status: str) -> Optional[Dict]:
        with self._lock:
            d = self._read("expenses")
            for item in d["items"]:
                if item["id"] == expense_id:
                    item["status"] = status
                    self._write("expenses", d)
                    return item
        return None

    def delete_expense(self, expense_id: str) -> bool:
        return self._delete("expenses", expense_id)

    def expense_totals(self) -> Dict[str, Any]:
        items = self.get_expenses(include_closed=True)
        pending  = sum(i["amount"] for i in items if i.get("status") == "pending")
        approved = sum(i["amount"] for i in items if i.get("status") == "approved")
        paid     = sum(i["amount"] for i in items if i.get("status") == "paid")
        currency = items[0]["currency"] if items else "COP"
        return {"pending": pending, "approved": approved, "paid": paid, "currency": currency}

    # ── Summary ─────────────────────────────────────────────────────────

    def summary(self) -> Dict[str, Any]:
        tasks    = self.get_tasks()
        expenses = self.get_expenses()
        totals   = self.expense_totals()
        todo_cnt = sum(1 for t in tasks if t.get("status") == "todo")
        doing_cnt= sum(1 for t in tasks if t.get("status") == "doing")
        critical = sum(1 for t in tasks if t.get("priority") == "critical")
        return {
            "colleague_count":    len(self.get_colleagues()),
            "tasks_todo":         todo_cnt,
            "tasks_doing":        doing_cnt,
            "tasks_critical":     critical,
            "expenses_pending":   len(expenses),
            "expense_pending_amt": totals["pending"],
            "currency":           totals["currency"],
        }

    # ── Storage ─────────────────────────────────────────────────────────

    def _path(self, module: str) -> Path:
        return self._base / f"{self._user}_{module}.json"

    def _read(self, module: str) -> Dict:
        try:
            return json.loads(self._path(module).read_text(encoding="utf-8"))
        except Exception:
            return {"items": []}

    def _write(self, module: str, data: Dict) -> None:
        self._path(module).write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _append(self, module: str, item: Dict) -> Dict:
        with self._lock:
            d = self._read(module)
            d["items"].append(item)
            if len(d["items"]) > 500:
                d["items"] = d["items"][-400:]
            self._write(module, d)
        return item

    def _delete(self, module: str, item_id: str) -> bool:
        with self._lock:
            d = self._read(module)
            before = len(d["items"])
            d["items"] = [i for i in d["items"] if i["id"] != item_id]
            if len(d["items"]) < before:
                self._write(module, d)
                return True
        return False
