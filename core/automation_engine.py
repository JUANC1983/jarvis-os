from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

# ── constants ────────────────────────────────────────────────────────
_TRIGGER_TYPES   = {"time", "event", "manual"}
_EVENT_TRIGGERS  = {
    "task_created", "task_completed", "project_created",
    "meeting_added", "calendar_event_created", "ai_insight",
}
_ACTION_TYPES    = {"create_task", "send_notification", "call_agent", "log_event"}
_CONDITION_OPS   = {"eq", "ne", "gt", "lt", "gte", "lte", "contains", "always"}
_DEFAULT_COOLDOWN_MIN = 5
_MAX_PER_USER    = 50
_MAX_EXEC_LOG    = 200


# ── condition evaluation ─────────────────────────────────────────────

def _eval_condition(cond: Dict[str, Any], ctx: Dict[str, Any]) -> bool:
    op = cond.get("operator", "always")
    if op == "always":
        return True
    field    = cond.get("field", "")
    expected = cond.get("value")
    actual   = ctx.get(field)
    if actual is None:
        return False
    try:
        if op == "eq":       return str(actual) == str(expected)
        if op == "ne":       return str(actual) != str(expected)
        if op == "gt":       return float(actual) > float(expected)
        if op == "lt":       return float(actual) < float(expected)
        if op == "gte":      return float(actual) >= float(expected)
        if op == "lte":      return float(actual) <= float(expected)
        if op == "contains": return str(expected).lower() in str(actual).lower()
    except (TypeError, ValueError):
        pass
    return False


def _eval_all_conditions(conditions: List[Dict], ctx: Dict[str, Any]) -> bool:
    """All conditions must pass (AND logic). Empty list = pass."""
    return all(_eval_condition(c, ctx) for c in conditions)


# ── storage helpers ───────────────────────────────────────────────────

def _blank() -> Dict[str, Any]:
    return {"automations": [], "execution_log": []}


class AutomationEngine:
    """
    Rule-based automation engine.

    Trigger types:
      time   — fire when called after a scheduled time (checked by caller)
      event  — fire when a named JARVIS event is emitted
      manual — fire only via explicit API call

    Actions:
      create_task        — add a task to the workspace
      send_notification  — create a notification
      call_agent         — route message via AI orchestrator
      log_event          — write a structured log entry
    """

    def __init__(self, file_path: str | Path, user_id: str = "owner") -> None:
        self.path    = Path(file_path)
        self.user_id = user_id
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write(_blank())
        self._lock = threading.Lock()
        # Injected by main.py after all engines initialise
        self._ext: Dict[str, Any] = {}

    def inject(self, **engines: Any) -> None:
        """Inject live engine references: notify, memory, orchestrator, planner, workspace."""
        self._ext.update(engines)

    # ── persistence ──────────────────────────────────────────────────

    def _read(self) -> Dict[str, Any]:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return _blank()

    def _write(self, data: Dict[str, Any]) -> None:
        self.path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # ── CRUD ─────────────────────────────────────────────────────────

    def create(
        self,
        name:           str,
        trigger_type:   str       = "manual",
        trigger_value:  str       = "",
        conditions:     List[Dict] | None = None,
        actions:        List[Dict] | None = None,
        cooldown_min:   int       = _DEFAULT_COOLDOWN_MIN,
        enabled:        bool      = True,
    ) -> Dict[str, Any]:
        """
        Create a new automation rule.

        actions: list of {type, config} dicts. Examples:
          {"type": "send_notification", "config": {"title": "...", "priority": "high"}}
          {"type": "create_task",       "config": {"text": "...", "priority": "medium"}}
          {"type": "call_agent",        "config": {"message": "..."}}
          {"type": "log_event",         "config": {"message": "..."}}
        """
        if not name.strip():
            raise ValueError("name required")
        trigger_type = trigger_type if trigger_type in _TRIGGER_TYPES else "manual"
        cooldown_min = max(1, int(cooldown_min))

        actions    = actions    or [{"type": "log_event", "config": {"message": name}}]
        conditions = conditions or []

        # Validate action types
        for act in actions:
            if act.get("type") not in _ACTION_TYPES:
                raise ValueError(f"unknown action type: {act.get('type')}")

        with self._lock:
            data = self._read()
            if len(data["automations"]) >= _MAX_PER_USER:
                raise ValueError(f"limit of {_MAX_PER_USER} automations reached")

            now  = datetime.utcnow().isoformat()
            item: Dict[str, Any] = {
                "id":            f"aut_{uuid4().hex[:10]}",
                "user_id":       self.user_id,
                "name":          name.strip(),
                "trigger_type":  trigger_type,
                "trigger_value": trigger_value.strip(),
                "conditions":    conditions,
                "actions":       actions,
                "cooldown_min":  cooldown_min,
                "enabled":       enabled,
                "run_count":     0,
                "last_run":      None,
                "created_at":    now,
            }
            data["automations"].append(item)
            self._write(data)
            return item

    def list_automations(
        self,
        enabled_only: bool = False,
        trigger_type: str  = "",
    ) -> List[Dict[str, Any]]:
        data = self._read()
        auts = data["automations"]
        if enabled_only:
            auts = [a for a in auts if a.get("enabled")]
        if trigger_type:
            auts = [a for a in auts if a.get("trigger_type") == trigger_type]
        return sorted(auts, key=lambda a: a.get("created_at", ""), reverse=True)

    def get(self, automation_id: str) -> Optional[Dict[str, Any]]:
        for a in self._read()["automations"]:
            if a["id"] == automation_id:
                return a
        return None

    def update(self, automation_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        allowed = {"name", "trigger_type", "trigger_value", "conditions",
                   "actions", "cooldown_min", "enabled"}
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
            data   = self._read()
            before = len(data["automations"])
            data["automations"] = [a for a in data["automations"]
                                   if a["id"] != automation_id]
            if len(data["automations"]) == before:
                return False
            self._write(data)
            return True

    # ── execution core ───────────────────────────────────────────────

    def _in_cooldown(self, aut: Dict[str, Any]) -> bool:
        last = aut.get("last_run")
        if not last:
            return False
        try:
            elapsed = datetime.utcnow() - datetime.fromisoformat(last)
            return elapsed < timedelta(minutes=aut.get("cooldown_min", _DEFAULT_COOLDOWN_MIN))
        except Exception:
            return False

    def _run_action(self, action: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
        atype  = action["type"]
        config = action.get("config", {})
        result = {"type": atype, "outcome": "ok", "detail": ""}

        try:
            if atype == "log_event":
                msg = config.get("message", "automation triggered")
                result["detail"] = f"logged: {msg[:200]}"
                # also persist to memory if available
                mem = self._ext.get("memory")
                if mem:
                    mem.save(
                        content=f"Automation log: {msg[:180]}",
                        entry_type="event",
                        importance=3,
                        tags=["automation"],
                    )

            elif atype == "send_notification":
                notify = self._ext.get("notify")
                if notify:
                    n = notify.create(
                        title=config.get("title", "Automation Alert"),
                        message=config.get("message", ""),
                        notif_type=config.get("notif_type", "general"),
                        priority=config.get("priority", "medium"),
                        source_id=ctx.get("automation_id", ""),
                        deduplicate=False,
                    )
                    result["detail"] = f"notification {n['id']}"
                else:
                    result["outcome"] = "skip"
                    result["detail"]  = "notify engine not injected"

            elif atype == "create_task":
                ws = self._ext.get("workspace")
                if ws:
                    t = ws.add_task(
                        text=config.get("text", "Automated task"),
                        priority=config.get("priority", "medium"),
                        day=config.get("day", "today"),
                        category=config.get("category", "automation"),
                    )
                    result["detail"] = f"task {t.get('id', '?')}"
                else:
                    result["outcome"] = "skip"
                    result["detail"]  = "workspace engine not injected"

            elif atype == "call_agent":
                orch = self._ext.get("orchestrator")
                if orch:
                    mem_ctx = {}
                    mem = self._ext.get("memory")
                    if mem:
                        mem_ctx["memory_context"] = mem.get_context(limit=5).get("context", [])
                    resp = orch.route(config.get("message", "status check"), mem_ctx)
                    result["detail"] = resp.get("response", "")[:200]
                    # save the agent response to memory
                    if mem:
                        mem.auto_save_interaction(
                            config.get("message", ""),
                            result["detail"],
                            importance=4,
                        )
                else:
                    result["outcome"] = "skip"
                    result["detail"]  = "orchestrator not injected"

        except Exception as e:
            result["outcome"] = "error"
            result["detail"]  = str(e)[:200]

        return result

    def run(
        self,
        automation_id: str,
        context:       Dict[str, Any] | None = None,
        force:         bool = False,
    ) -> Dict[str, Any]:
        """
        Execute one automation.
        force=True bypasses cooldown (used for manual triggers).
        """
        ctx = dict(context or {})
        ctx["automation_id"] = automation_id

        with self._lock:
            data = self._read()
            aut  = next((a for a in data["automations"] if a["id"] == automation_id), None)
            if aut is None:
                raise ValueError(f"automation '{automation_id}' not found")
            if not aut.get("enabled"):
                return {"id": automation_id, "status": "skipped", "reason": "disabled"}
            if not force and self._in_cooldown(aut):
                return {"id": automation_id, "status": "skipped",
                        "reason": f"cooldown ({aut.get('cooldown_min')}m)"}

            # Evaluate conditions
            if not _eval_all_conditions(aut.get("conditions", []), ctx):
                return {"id": automation_id, "status": "skipped",
                        "reason": "conditions not met"}

            # Execute all actions
            action_results = []
            for act in aut.get("actions", []):
                res = self._run_action(act, ctx)
                action_results.append(res)

            # Update state
            now = datetime.utcnow().isoformat()
            aut["last_run"]  = now
            aut["run_count"] = aut.get("run_count", 0) + 1

            log_entry = {
                "ts":            now,
                "automation_id": automation_id,
                "name":          aut["name"],
                "trigger_type":  aut["trigger_type"],
                "status":        "executed",
                "actions":       action_results,
                "context_keys":  list(ctx.keys()),
            }
            data["execution_log"].append(log_entry)
            data["execution_log"] = data["execution_log"][-_MAX_EXEC_LOG:]
            self._write(data)

            return {
                "id":             automation_id,
                "name":           aut["name"],
                "status":         "executed",
                "action_results": action_results,
                "run_count":      aut["run_count"],
            }

    def fire_event(
        self,
        event_name: str,
        context:    Dict[str, Any] | None = None,
    ) -> List[Dict[str, Any]]:
        """
        Fire all enabled event-triggered automations that match event_name.
        Called by other engines when an event occurs.
        """
        ctx = dict(context or {})
        ctx["event"] = event_name
        results = []
        for aut in self._read()["automations"]:
            if not aut.get("enabled"):
                continue
            if aut.get("trigger_type") != "event":
                continue
            if aut.get("trigger_value") and aut["trigger_value"] != event_name:
                continue
            try:
                r = self.run(aut["id"], context=ctx)
                results.append(r)
            except Exception as e:
                results.append({"id": aut["id"], "status": "error", "reason": str(e)})
        return results

    def check_time_triggers(self) -> List[Dict[str, Any]]:
        """
        Evaluate all time-based automations.
        trigger_value format: "HH:MM" (daily) or "daily|HH:MM" or "hourly".
        Called by a scheduler or on-demand.
        """
        now   = datetime.now()
        results = []
        for aut in self._read()["automations"]:
            if not aut.get("enabled"):
                continue
            if aut.get("trigger_type") != "time":
                continue
            tv = aut.get("trigger_value", "")
            fired = False
            try:
                if tv == "hourly":
                    # fire once per hour (cooldown handles dedup)
                    fired = True
                elif tv.startswith("daily|"):
                    hm = tv.split("|", 1)[1]
                    h, m = map(int, hm.split(":"))
                    # fire if current time is within 5 min of target
                    target = now.replace(hour=h, minute=m, second=0, microsecond=0)
                    if abs((now - target).total_seconds()) <= 300:
                        fired = True
                elif ":" in tv:
                    h, m = map(int, tv.split(":", 1))
                    target = now.replace(hour=h, minute=m, second=0, microsecond=0)
                    if abs((now - target).total_seconds()) <= 300:
                        fired = True
            except Exception:
                pass
            if fired:
                try:
                    r = self.run(aut["id"], context={"trigger": "time", "time": now.isoformat()})
                    results.append(r)
                except Exception as e:
                    results.append({"id": aut["id"], "status": "error", "reason": str(e)})
        return results

    # ── log & stats ──────────────────────────────────────────────────

    def execution_log(self, limit: int = 20) -> List[Dict[str, Any]]:
        log = self._read().get("execution_log", [])
        return list(reversed(log))[:limit]

    def stats(self) -> Dict[str, Any]:
        data  = self._read()
        auts  = data["automations"]
        log   = data.get("execution_log", [])
        by_trigger: Dict[str, int] = {}
        by_action:  Dict[str, int] = {}
        total_runs = 0
        for a in auts:
            t = a.get("trigger_type", "manual")
            by_trigger[t] = by_trigger.get(t, 0) + 1
            for act in a.get("actions", []):
                at = act.get("type", "?")
                by_action[at] = by_action.get(at, 0) + 1
            total_runs += a.get("run_count", 0)
        return {
            "total":      len(auts),
            "enabled":    sum(1 for a in auts if a.get("enabled")),
            "disabled":   sum(1 for a in auts if not a.get("enabled")),
            "total_runs": total_runs,
            "log_entries": len(log),
            "by_trigger": by_trigger,
            "by_action":  by_action,
        }
