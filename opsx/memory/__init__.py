"""
Graph Memory System for JARVIS.
Provides structured node/edge memory with context injection for AI calls.

Controlled by GRAPH_MEMORY_MODE env var:
  OFF    — disabled entirely (default, safe)
  SHADOW — builds memory but never injects into AI context
  ACTIVE — builds and injects memory context

Import guard: if anything fails here, the rest of JARVIS continues normally.
"""
from __future__ import annotations

import logging
import os

log = logging.getLogger("jarvis.memory")

GRAPH_MEMORY_MODE = os.getenv("GRAPH_MEMORY_MODE", "OFF").upper()

_engine = None
_context_builder = None
_router = None

try:
    from .graph_memory_engine import GraphMemoryEngine
    from .context_builder import ContextBuilder
    from .memory_router import MemoryRouter

    _engine = GraphMemoryEngine()
    _context_builder = ContextBuilder(_engine)
    _router = MemoryRouter(_engine, _context_builder)

    log.info("Graph Memory System loaded (mode=%s, nodes=%d)", GRAPH_MEMORY_MODE, _engine.node_count())
except Exception as _exc:
    log.warning("Graph Memory System failed to load — disabled. Reason: %s", _exc)


def get_engine() -> "GraphMemoryEngine | None":
    return _engine


def get_router() -> "MemoryRouter | None":
    return _router


def is_active() -> bool:
    return GRAPH_MEMORY_MODE == "ACTIVE" and _engine is not None


def is_shadow() -> bool:
    return GRAPH_MEMORY_MODE == "SHADOW" and _engine is not None


def is_enabled() -> bool:
    return GRAPH_MEMORY_MODE in ("ACTIVE", "SHADOW") and _engine is not None


def get_context(module: str, query: str, limit: int = 5) -> list:
    """
    Safe wrapper — returns [] if memory is off, in shadow mode, or fails.
    Called from ai_orchestrator context builders.
    """
    if not is_active():
        return []
    try:
        return _router.get_context(module, query, limit=limit)
    except Exception as exc:
        log.error("Graph memory get_context failed (module=%s): %s", module, exc)
        return []
