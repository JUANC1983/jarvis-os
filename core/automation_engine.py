from __future__ import annotations

"""
Automation Engine — Phase 5G OPS-X Layer

Model:
  Trigger  → Condition → Action

Trigger types : task_due | meeting_start | calendar_event | schedule | manual
Condition ops : eq | ne | gt | lt | gte | lte | contains | not_contains | always
Action types  : notify | save_memory | log | create_task | webhook

Anti-loop protection: per-automation cooldown_minutes (default 60).
If last_run is within cooldown the automation is skipped automatically.
"""

import json
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

_TRIGGER_TYPES = {
    "task_due", "meeting_start", "calendar_event",
    "schedule", "manual",
}
_CONDITION_OPS = {
    "eq", "ne", "gt", "lt", "gte", "lte",
    "contains", "not_contains", "always",
}
_ACTION_TYPES = {
    "notify", "save_memory", "log", "create_task", "webhook",
}
_DEFAULT_COOLDOWN = 60          # minutes — prevents re-fire within this window
_MAX_RUN_LOG      = 100         # entries kept in execution_log per file
_MAX_AUTOMATIONS  = 50          # hard cap per user

# ── condition evaluator ──────────────────────────────────────────────

def _evaluate_condition(condition: Dict[str, Any], context: Dict[str, Any]) -> bool:
    """
    Evaluate a single condition dict against context.
    condition = {"field": str, "operator": str, "value": Any}
    context   = flat dict of runtime values, e.g. {"task_priority": "critical"}
    """
    op = condition.get("operator", "always")
    if op == "always":
        return True

    field = condition.get("field", "")
    expected = condition.get("value")
    actual = context.get(field)

    if actual is None:
        return False

    try:
        if op == "eq":           return actual == expected
        if op == "ne":           return actual != expected
        if op == "gt":           return float(actual) > float(expected)
        if op == "lt":           return float(actual) < float(expected)
        if op == "gte":          return float(actual) >= float(expected)
        if op == "lte":          return float(actual) <= float(expected)
        if op == "contains":     return str(expected).lower() in str(actual).lower()
        if op == "not_contains": return str(expected).lower() not in str(actual).lower()
    except (TypeError, ValueError):
        pass
    return False


# ── automation storage schema ────────────────────────────────────────

def _empty_store() -> Dict[str, Any]:
    return {"automations": [], "execution_log": []}


class AutomationEngine:
    def __init__(self, file_path: str | Path) -> None:
        self.path = Path(file_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write(_empty_store())
        self._lock = threading.Lock()

        # Pluggable action handlers — registered by main.py after engines are ready
        self._action_handlers: Dict[str, Callable] = {}

    # ── persistence ─────────────────────────────────────────────────

    def _read(self) -> Dict[str, Any]:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return _empty_store()

    def _write(self, data: Dict[str, Any]) -> None:
        self.path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # ── action handler registry ──────────────────────────────────────

    def register_action(self, action_type: str, handler: Callable) -> None:
        """Register a callable that handles a given action type.
        handler(action_config, context) → Any
        """
        self._action_handlers[action_type] = handler

    # ── CRUD ─────────────────────────────────────────────────────────

    def create(
        self,
        name:             str,
        trigger_type:     str,
        trigger_config:   Dict[str, Any] | None = None,
        condition:        Dict[str, Any] | None = None,
        action_type:      str = "notify",
        action_config:    Dict[str, Any] | None = None,
        cooldown_minutes: int = _DEFAULT_COOLDOWN,
        enabled:          bool = True,
    ) -> Dict[str, Any]:
        if not name.strip():
            raise ValueError("name is required")
        trigger_type = trigger_type if trigger_type in _TRIGGER_TYPES else "manual"
        action_type  = action_type  if action_type  in _ACTION_TYPES  else "notify"
        cooldown_minutes = max(1, int(cooldown_minutes))

        with self._lock:
            data = self._read()
            if len(data["automations"]) >= _MAX_AUTOMATIONS:
                raise ValueError(f"Max {_MAX_AUTOMATIONS} automations per user")

            now = datetime.utcnow().isoformat()
            item: Dict[str, Any] = {
                "id":               f"aut_{uuid4().hex[:10]}",
                "name":             name.strip(),
                "trigger": {
                    "type":   trigger_type,
                    "config": trigger_config or {},
                },
                "condition":        condition or {"operator": "always"},
                "action": {
                    "type":   action_type,
                    "config": action_config or {},
                },
                "cooldown_minutes": cooldown_minutes,
                "enabled":          enabled,
                "run_count":        0,
                "last_run":         None,
                "created_at":       now,
            }
            data["automations"].append(item)
            self._write(data)
            return item

    def list_automations(self, enabled_only: bool = False) -> List[Dict[str, Any]]:
        data = self._read()
        auts = data["automations"]
        if enabled_only:
            auts = [a for a in auts if a.get("enabled")]
        return sorted(auts, key=lambda a: a.get("created_at", ""), reverse=True)

    def get(self, automation_id: str) -> Optional[Dict[str, Any]]:
        data = self._read()
        for a in data["automations"]:
            if a["id"] == automation_id:
                return a
        return None

    def update(self, automation_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        allowed = {"name", "trigger", "condition", "action", "cooldown_minutes", "enabled"}
        with self._lock:
            data = self._read()
            for a in data["automations"]:
                if a["id"] == automation_id:
                    for k, v in updates.items():
                        if k in allowed:
                            a[k] = v
                    self._write(data)
                    return a
        raise ValueError(f"automation '{automation_id}' not found")

    def delete(self, automation_id: str) -> bool:
        with self._lock:
            data = self._read()
            before = len(data["automations"])
            data["automations"] = [a for a in data["automations"] if a["id"] != automation_id]
            if len(data["automations"]) == before:
                return False
            self._write(data)
            return True

    # ── execution ────────────────────────────────────────────────────

    def _within_cooldown(self, automation: Dict[str, Any]) -> bool:
        """Return True if automation ran within its cooldown window (skip it)."""
        last = automation.get("last_run")
        if not last:
            return False
        try:
            last_dt = datetime.fromisoformat(last)
            cooldown = timedelta(minutes=automation.get("cooldown_minutes", _DEFAULT_COOLDOWN))
            return (datetime.utcnow() - last_dt) < cooldown
        except Exception:
            return False

    def _execute_action(
        self,
        automation: Dict[str, Any],
        context:    Dict[str, Any],
    ) -> Dict[str, Any]:
        """Run the automation's action. Returns execution result dict."""
        action_type   = automation["action"]["type"]
        action_config = automation["action"].get("config", {})
        result: Dict[str, Any] = {"action": action_type, "outcome": "ok", "detail": ""}

        # Use registered handler if available
        handler = self._action_handlers.get(action_type)
        if handler:
            try:
                outcome = handler(action_config, context)
                result["detail"] = str(outcome)[:200]
            except Exception as e:
                result["outcome"] = "error"
                result["detail"]  = str(e)
            return result

        # Built-in fallback handlers
        if action_type == "log":
            msg = action_config.get("message", automation["name"])
            result["detail"] = f"Logged: {msg}"

        elif action_type == "notify":
            # Fallback: just record intent (real notify registered by main.py)
            result["detail"] = f"Notification queued: {action_config.get('title', automation['name'])}"

        elif action_type == "save_memory":
            result["detail"] = f"Memory save queued: {action_config.get('content', '')[:80]}"

        elif action_type == "webhook":
            url = action_config.get("url", "")
            if not url:
                result["outcome"] = "skip"
                result["detail"]  = "No URL configured"
            else:
                try:
                    import urllib.request
                    payload = json.dumps({
                        "automation_id": automation["id"],
                        "name":          automation["name"],
                        "context":       {k: str(v)[:100] for k, v in context.items()},
                    }).encode()
                    req = urllib.request.Request(
                        url, data=payload,
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    )
                    with urllib.request.urlopen(req, timeout=5) as resp:
                        result["detail"] = f"HTTP {resp.status}"
                except Exception as e:
                    result["outcome"] = "error"
                    result["detail"]  = str(e)
        else:
            result["outcome"] = "skip"
            result["detail"]  = f"No handler for action '{action_type}'"

        return result

    def run(
        self,
        automation_id: str,
        context:       Dict[str, Any] | None = None,
        force:         bool = False,
    ) -> Dict[str, Any]:
        """
        Execute a single automation by ID.
        force=True skips cooldown check (useful for manual triggers).
        """
        context = context or {}
        with self._lock:
            data = self._read()
            aut = next((a for a in data["automations"] if a["id"] == automation_id), None)
            if aut is None:
                raise ValueError(f"automation '{automation_id}' not found")
            if not aut.get("enabled"):
                return {"id": automation_id, "skipped": "disabled"}
            if not force and self._within_cooldown(aut):
                remaining = aut.get("cooldown_minutes", _DEFAULT_COOLDOWN)
                return {"id": automation_id, "skipped": f"cooldown ({remaining}m)"}

            # Evaluate condition
            if not _evaluate_condition(aut.get("condition", {}), context):
                return {"id": automation_id, "skipped": "condition_not_met"}

            # Execute action
            action_result = self._execute_action(aut, context)

            # Update automation state
            now = datetime.utcnow().isoformat()
            aut["last_run"]  = now
            aut["run_count"] = aut.get("run_count", 0) + 1

            # Append execution log entry
            log_entry = {
                "ts":            now,
                "automation_id": automation_id,
                "name":          aut["name"],
                "trigger":       aut["trigger"]["type"],
                "action":        action_result["action"],
                "outcome":       action_result["outcome"],
                "detail":        action_result["detail"],
            }
            data["execution_log"].append(log_entry)
            data["execution_log"] = data["execution_log"][-_MAX_RUN_LOG:]

            self._write(data)
            return {"id": automation_id, "executed": True, **action_result}

    def check_and_fire(
        self,
        trigger_type: str,
        context:      Dict[str, Any] | None = None,
    ) -> List[Dict[str, Any]]:
        """
        Evaluate all enabled automations whose trigger matches trigger_type.
        Fires each that passes condition + cooldown check.
        Returns list of run results.
        """
        context = context or {}
        results = []
        data    = self._read()

        for aut in data["automations"]:
            if not aut.get("enabled"):
                continue
            if aut["trigger"]["type"] != trigger_type:
                continue
            try:
                result = self.run(aut["id"], context=context)
                results.append(result)
            except Exception as e:
                results.append({"id": aut["id"], "error": str(e)})

        return results

    # ── execution log ────────────────────────────────────────────────

    def execution_log(self, limit: int = 20) -> List[Dict[str, Any]]:
        data = self._read()
        log  = data.get("execution_log", [])
        return list(reversed(log))[:limit]

    def stats(self) -> Dict[str, Any]:
        data  = self._read()
        auts  = data["automations"]
        enabled = sum(1 for a in auts if a.get("enabled"))
        by_trigger: Dict[str, int] = {}
        by_action:  Dict[str, int] = {}
        total_runs = 0
        for a in auts:
            t = a["trigger"]["type"]
            by_trigger[t] = by_trigger.get(t, 0) + 1
            ac = a["action"]["type"]
            by_action[ac] = by_action.get(ac, 0) + 1
            total_runs += a.get("run_count", 0)
        return {
            "total":       len(auts),
            "enabled":     enabled,
            "disabled":    len(auts) - enabled,
            "total_runs":  total_runs,
            "by_trigger":  by_trigger,
            "by_action":   by_action,
        }
