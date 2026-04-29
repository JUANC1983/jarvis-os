"""
Backfill graph memory from existing JARVIS data files.
Idempotent: uses stable node IDs so re-running just updates existing nodes.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .graph_memory_engine import GraphMemoryEngine
from .memory_models import Module, NodeType

log = logging.getLogger("jarvis.memory.backfill")

BASE = Path("data")


async def run_backfill(
    engine: GraphMemoryEngine,
    modules: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Seed graph memory from all known JARVIS data files.
    Returns a summary dict: {modules_run, nodes_added, errors}.
    """
    all_modules = modules or [
        Module.GOLF, Module.HEALTH, Module.PRODUCTIVITY,
        Module.CALENDAR, Module.GENERAL,
    ]

    total_nodes = 0
    errors: List[str] = []
    ran: List[str] = []

    runners = {
        Module.GOLF:         _backfill_golf,
        Module.HEALTH:       _backfill_health,
        Module.PRODUCTIVITY: _backfill_productivity,
        Module.CALENDAR:     _backfill_calendar,
        Module.GENERAL:      _backfill_general,
    }

    for mod in all_modules:
        fn = runners.get(mod)
        if fn is None:
            continue
        try:
            added = fn(engine)
            total_nodes += added
            ran.append(mod)
            log.info("Backfill %s: %d nodes", mod, added)
        except Exception as exc:
            err = f"{mod}: {exc}"
            errors.append(err)
            log.error("Backfill failed for module %s: %s", mod, exc)

    return {
        "modules_run":  ran,
        "nodes_upserted": total_nodes,
        "errors":       errors,
    }


# ── Module-specific loaders ────────────────────────────────────────────────────

def _backfill_golf(engine: GraphMemoryEngine) -> int:
    count = 0

    # Player stats
    stats_path = BASE / "golf" / "player_stats.json"
    if stats_path.exists():
        d = _load_json(stats_path)
        if d:
            handicap = d.get("handicap_index", "unknown")
            avg      = d.get("avg_score", "?")
            best     = d.get("best_score", "?")
            strengths = ", ".join(d.get("strengths", []))
            improve   = ", ".join(d.get("areas_to_improve", []))
            engine.add_node(
                node_id="golf_player_stats",
                node_type=NodeType.FACT,
                label="Golf Player Stats",
                module=Module.GOLF,
                content=f"Handicap: {handicap}. Avg score: {avg}. Best: {best}. "
                        f"Strengths: {strengths}. Areas to improve: {improve}.",
                importance=0.85,
                tags=["golf", "handicap", "stats"],
                metadata=d,
            )
            count += 1

    # Player bag
    bag_path = BASE / "golf" / "player_bag.json"
    if bag_path.exists():
        clubs = _load_json(bag_path)
        if isinstance(clubs, list) and clubs:
            summary = ", ".join(
                f"{c['club']} ({c.get('carry_yards', '?')}y)"
                for c in clubs[:8]
            )
            engine.add_node(
                node_id="golf_player_bag",
                node_type=NodeType.PREFERENCE,
                label="Golf Bag & Club Distances",
                module=Module.GOLF,
                content=f"Bag: {summary}. Total clubs: {len(clubs)}.",
                importance=0.75,
                tags=["golf", "clubs", "bag", "distances"],
                metadata={"clubs": clubs},
            )
            count += 1

            # Add edge: stats → bag
            engine.add_edge("golf_player_stats", "golf_player_bag", "has", weight=0.9)

    return count


def _backfill_health(engine: GraphMemoryEngine) -> int:
    count = 0
    fit_base = BASE / "fitness" / "owner"

    activity_files = {
        "golf":    fit_base / "owner_golf.json",
        "gym":     fit_base / "owner_gym.json",
        "running": fit_base / "owner_running.json",
        "cycling": fit_base / "owner_cycling.json",
        "tennis":  fit_base / "owner_tennis.json",
    }

    active_sports = []
    for sport, path in activity_files.items():
        if path.exists():
            d = _load_json(path)
            if d and isinstance(d, dict):
                sessions = d.get("sessions", [])
                if sessions:
                    active_sports.append(sport)
                    recent = sessions[-1] if sessions else {}
                    engine.add_node(
                        node_id=f"health_{sport}",
                        node_type=NodeType.HABIT,
                        label=f"{sport.title()} Activity",
                        module=Module.HEALTH,
                        content=f"Active in {sport}. {len(sessions)} sessions logged. "
                                f"Latest: {_fmt_session(recent)}",
                        importance=0.6,
                        tags=["fitness", "health", sport],
                        metadata={"sessions_count": len(sessions), "latest": recent},
                    )
                    count += 1

    if active_sports:
        engine.add_node(
            node_id="health_profile",
            node_type=NodeType.FACT,
            label="Fitness Profile",
            module=Module.HEALTH,
            content=f"Active sports: {', '.join(active_sports)}.",
            importance=0.7,
            tags=["fitness", "health", "profile"],
        )
        count += 1

    return count


def _backfill_productivity(engine: GraphMemoryEngine) -> int:
    count = 0

    proj_path = BASE / "projects.json"
    if proj_path.exists():
        d = _load_json(proj_path)
        if d and isinstance(d, dict):
            projects = d.get("projects", [])
            tasks    = d.get("tasks", [])

            if projects:
                active = [p for p in projects if p.get("status") not in ("done", "archived")]
                summary = "; ".join(p.get("name", "?") for p in active[:5])
                engine.add_node(
                    node_id="productivity_projects",
                    node_type=NodeType.PROJECT,
                    label="Active Projects",
                    module=Module.PRODUCTIVITY,
                    content=f"{len(active)} active projects: {summary}.",
                    importance=0.8,
                    tags=["projects", "productivity", "work"],
                    metadata={"count": len(active)},
                )
                count += 1

            if tasks:
                pending = [t for t in tasks if t.get("status") not in ("done", "cancelled")]
                if pending:
                    engine.add_node(
                        node_id="productivity_tasks",
                        node_type=NodeType.FACT,
                        label="Pending Tasks",
                        module=Module.PRODUCTIVITY,
                        content=f"{len(pending)} tasks pending.",
                        importance=0.7,
                        tags=["tasks", "productivity", "todo"],
                        metadata={"count": len(pending)},
                    )
                    count += 1

            if count >= 2:
                engine.add_edge("productivity_projects", "productivity_tasks", "has", weight=0.7)

    return count


def _backfill_calendar(engine: GraphMemoryEngine) -> int:
    count = 0

    cal_path = BASE / "calendar_owner.json"
    if cal_path.exists():
        events = _load_json(cal_path)
        if isinstance(events, list) and events:
            upcoming = [e for e in events if not e.get("notified")][:5]
            titles   = ", ".join(e.get("title", "?") for e in upcoming)
            engine.add_node(
                node_id="calendar_upcoming",
                node_type=NodeType.EVENT,
                label="Upcoming Calendar Events",
                module=Module.CALENDAR,
                content=f"{len(upcoming)} upcoming events: {titles}.",
                importance=0.75,
                tags=["calendar", "events", "schedule"],
                metadata={"count": len(upcoming)},
            )
            count += 1

    return count


def _backfill_general(engine: GraphMemoryEngine) -> int:
    count = 0

    # Super memory — high-value condensed memories
    sm_path = BASE / "super_memory.json"
    if sm_path.exists():
        entries = _load_json(sm_path)
        if isinstance(entries, list):
            for i, entry in enumerate(entries[:10]):
                text     = entry.get("text", "")
                category = entry.get("category", "general")
                if not text:
                    continue
                nid = f"super_mem_{i}"
                engine.add_node(
                    node_id=nid,
                    node_type=NodeType.FACT,
                    label=f"Memory: {text[:40]}",
                    module=Module.GENERAL,
                    content=text[:500],
                    importance=0.6,
                    tags=["memory", category],
                )
                count += 1

    # Owner identity node (always add)
    engine.add_node(
        node_id="owner_identity",
        node_type=NodeType.PERSON,
        label="JARVIS Owner",
        module=Module.GENERAL,
        content="Primary JARVIS user. Passionate about golf, software engineering, and personal productivity.",
        importance=0.95,
        tags=["owner", "user", "identity"],
        metadata={"user_id": "owner"},
    )
    count += 1

    return count


# ── Helpers ────────────────────────────────────────────────────────────────────

def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        log.warning("Could not load %s: %s", path, e)
        return None


def _fmt_session(s: Dict) -> str:
    if not s:
        return "no data"
    parts = []
    for k in ("date", "duration_min", "distance_km", "notes"):
        if k in s:
            parts.append(f"{k}={s[k]}")
    return ", ".join(parts) or "session logged"
