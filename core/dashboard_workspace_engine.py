from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict
from uuid import uuid4
from core.meetings_engine import MeetingsEngine


class DashboardWorkspaceEngine:
    def __init__(self, base_path: str = "data/dashboard_workspace.json", uploads_dir: str = "dashboard/uploads") -> None:
        self.base_path = Path(base_path)
        self.base_path.parent.mkdir(parents=True, exist_ok=True)
        self.uploads_dir = Path(uploads_dir)
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        self.meetings_engine = MeetingsEngine()

        if not self.base_path.exists():
            self.base_path.write_text(json.dumps({
                "tasks": [
                    {"id": "t1", "text": "Review macro markets", "priority": "high", "day": "today", "done": False},
                    {"id": "t2", "text": "Prepare strategy review", "priority": "medium", "day": "today", "done": False}
                ],
                "meetings": [],
                "assets": []
            }, ensure_ascii=False, indent=2), encoding="utf-8")

    def _read(self) -> Dict[str, Any]:
        return json.loads(self.base_path.read_text(encoding="utf-8"))

    def _write(self, data: Dict[str, Any]) -> None:
        self.base_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def home(self, owner_name: str) -> Dict[str, Any]:
        data = self._read()
        tasks = data.get("tasks", [])
        meetings = self.meetings_engine.get_meetings()
        assets = data.get("assets", [])
        meetings = sorted(meetings, key=lambda x: x.get('time') or x.get('datetime', '99:99'))
        next_meeting = meetings[0] if meetings else None

        return {
            "date": datetime.now().strftime("%A %d %B %Y"),
            "greeting": "JARVIS Command Center ready.",
            "owner_name": owner_name,
            "top_priority": "Protect capital and increase asymmetric upside",
            "tasks": tasks,
            "meetings": meetings,
            "tasks_open": len([t for t in tasks if not t.get("done")]),
            "assets_count": len(assets),
            "next_meeting": next_meeting,
        }

    def list_assets(self) -> Dict[str, Any]:
        return {"assets": self._read().get("assets", [])}

    def add_task(self, text: str, priority: str = "medium", day: str = "today") -> Dict[str, Any]:
        data = self._read()
        item = {
            "id": f"t_{uuid4().hex[:8]}",
            "text": text,
            "priority": priority,
            "day": day,
            "done": False
        }
        data["tasks"].append(item)
        self._write(data)
        return item

    def toggle_task(self, task_id: str) -> Dict[str, Any]:
        data = self._read()
        for item in data.get("tasks", []):
            if item["id"] == task_id:
                item["done"] = not item.get("done", False)
                self._write(data)
                return item
        raise ValueError("task not found")

    def add_meeting(self, title: str, time_value: str, notes: str = "") -> Dict[str, Any]:
        return self.meetings_engine.add_meeting(title, time_value, notes)

    def register_asset(self, filename: str, stored_path: str, mime_type: str | None = None, size_bytes: int | None = None) -> Dict[str, Any]:
        data = self._read()
        item = {
            "id": f"a_{uuid4().hex[:10]}",
            "filename": filename,
            "stored_path": stored_path.replace("\\\\", "/"),
            "mime_type": mime_type or "application/octet-stream",
            "kind": "file",
            "size_bytes": size_bytes,
            "created_at": datetime.utcnow().isoformat(),
        }
        data["assets"].insert(0, item)
        self._write(data)
        return item


