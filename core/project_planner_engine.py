from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

DATA_FILE = Path("data/projects.json")

_URGENCY_COLOR = {
    "critical": "red",
    "high":     "orange",
    "medium":   "yellow",
    "low":      "green",
}


class ProjectPlannerEngine:
    def __init__(self, data_file: str | Path = DATA_FILE) -> None:
        self.path = Path(data_file)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write({"projects": [], "tasks": []})

    # ── persistence ─────────────────────────────────────────────────

    def _read(self) -> Dict[str, Any]:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _write(self, data: Dict[str, Any]) -> None:
        self.path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # ── projects ────────────────────────────────────────────────────

    def list_projects(self) -> List[Dict]:
        data = self._read()
        projects = data.get("projects", [])
        tasks = data.get("tasks", [])
        for p in projects:
            pid = p["id"]
            p["task_count"]  = sum(1 for t in tasks if t.get("project_id") == pid)
            p["done_count"]  = sum(1 for t in tasks if t.get("project_id") == pid and t.get("status") == "done")
            p["todo_count"]  = sum(1 for t in tasks if t.get("project_id") == pid and t.get("status") == "todo")
            p["doing_count"] = sum(1 for t in tasks if t.get("project_id") == pid and t.get("status") == "doing")
        return projects

    def create_project(self, name: str, description: str = "", color: str = "cyan") -> Dict:
        data = self._read()
        item: Dict[str, Any] = {
            "id":          f"p_{uuid4().hex[:10]}",
            "name":        name.strip(),
            "description": description.strip(),
            "color":       color,
            "status":      "active",
            "created_at":  datetime.utcnow().isoformat(),
        }
        data["projects"].append(item)
        self._write(data)
        return {**item, "task_count": 0, "done_count": 0, "todo_count": 0, "doing_count": 0}

    def get_project(self, project_id: str) -> Optional[Dict]:
        projects = self.list_projects()
        return next((p for p in projects if p["id"] == project_id), None)

    def delete_project(self, project_id: str) -> bool:
        data = self._read()
        before = len(data["projects"])
        data["projects"] = [p for p in data["projects"] if p["id"] != project_id]
        if len(data["projects"]) == before:
            return False
        data["tasks"] = [t for t in data["tasks"] if t.get("project_id") != project_id]
        self._write(data)
        return True

    # ── tasks ────────────────────────────────────────────────────────

    def get_tasks(self, project_id: str) -> List[Dict]:
        data = self._read()
        tasks = [t for t in data.get("tasks", []) if t.get("project_id") == project_id]
        tasks.sort(key=lambda t: (t.get("status", ""), t.get("created_at", "")))
        return tasks

    def create_task(
        self,
        project_id: str,
        title: str,
        description: str = "",
        status: str = "todo",
        urgency: str = "medium",
        due_date: str = "",
    ) -> Dict:
        data = self._read()
        if not any(p["id"] == project_id for p in data.get("projects", [])):
            raise ValueError(f"project '{project_id}' not found")
        urgency = urgency if urgency in _URGENCY_COLOR else "medium"
        item: Dict[str, Any] = {
            "id":             f"tk_{uuid4().hex[:10]}",
            "project_id":     project_id,
            "title":          title.strip(),
            "description":    description.strip(),
            "status":         status if status in ("todo", "doing", "done") else "todo",
            "urgency":        urgency,
            "priority_color": _URGENCY_COLOR[urgency],
            "due_date":       due_date.strip(),
            "created_at":     datetime.utcnow().isoformat(),
            "completed_at":   None,
        }
        data["tasks"].append(item)
        self._write(data)
        return item

    def update_task(self, task_id: str, updates: Dict[str, Any]) -> Dict:
        data = self._read()
        allowed = {"title", "description", "status", "urgency", "due_date"}
        for task in data.get("tasks", []):
            if task["id"] == task_id:
                for k, v in updates.items():
                    if k in allowed:
                        task[k] = v
                if "urgency" in updates:
                    urg = updates["urgency"]
                    if urg in _URGENCY_COLOR:
                        task["priority_color"] = _URGENCY_COLOR[urg]
                if "status" in updates:
                    if updates["status"] == "done" and not task.get("completed_at"):
                        task["completed_at"] = datetime.utcnow().isoformat()
                    elif updates["status"] != "done":
                        task["completed_at"] = None
                self._write(data)
                return task
        raise ValueError(f"task '{task_id}' not found")

    def delete_task(self, task_id: str) -> bool:
        data = self._read()
        before = len(data["tasks"])
        data["tasks"] = [t for t in data["tasks"] if t["id"] != task_id]
        if len(data["tasks"]) == before:
            return False
        self._write(data)
        return True

    def create_tasks_bulk(self, project_id: str, task_defs: List[Dict]) -> List[Dict]:
        created = []
        for td in task_defs:
            t = self.create_task(
                project_id=project_id,
                title=td.get("title", "New Task"),
                description=td.get("description", ""),
                status=td.get("status", "todo"),
                urgency=td.get("urgency", "medium"),
                due_date=td.get("due_date", ""),
            )
            created.append(t)
        return created
