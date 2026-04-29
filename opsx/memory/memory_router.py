"""
MemoryRouter — dispatches context requests to the right module + query strategy.
Each JARVIS module gets a tailored retrieval profile.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .context_builder import BuiltContext, ContextBuilder
from .graph_memory_engine import GraphMemoryEngine
from .memory_models import Module

log = logging.getLogger("jarvis.memory.router")


# ── Module profiles ────────────────────────────────────────────────────────────

_PROFILES: Dict[str, Dict] = {
    Module.GOLF: {
        "limit":      6,
        "max_tokens": 600,
        "extra_modules": [],
        "fmt":        "bullet",
    },
    Module.FINANCE: {
        "limit":      5,
        "max_tokens": 500,
        "extra_modules": [],
        "fmt":        "bullet",
    },
    Module.PRODUCTIVITY: {
        "limit":      6,
        "max_tokens": 700,
        "extra_modules": [Module.CALENDAR, Module.EMAIL],
        "fmt":        "bullet",
    },
    Module.HEALTH: {
        "limit":      5,
        "max_tokens": 500,
        "extra_modules": [],
        "fmt":        "bullet",
    },
    Module.CALENDAR: {
        "limit":      4,
        "max_tokens": 400,
        "extra_modules": [Module.PRODUCTIVITY],
        "fmt":        "bullet",
    },
    Module.EMAIL: {
        "limit":      4,
        "max_tokens": 400,
        "extra_modules": [],
        "fmt":        "bullet",
    },
    Module.SYSTEM: {
        "limit":      4,
        "max_tokens": 400,
        "extra_modules": [],
        "fmt":        "prose",
    },
    Module.GENERAL: {
        "limit":      5,
        "max_tokens": 500,
        "extra_modules": [],
        "fmt":        "bullet",
    },
}

_DEFAULT_PROFILE = {
    "limit":      5,
    "max_tokens": 500,
    "extra_modules": [],
    "fmt":        "bullet",
}


class MemoryRouter:

    def __init__(self, engine: GraphMemoryEngine, builder: ContextBuilder) -> None:
        self._engine  = engine
        self._builder = builder

    def get_context(
        self,
        module: str,
        query: str,
        limit: Optional[int] = None,
        max_tokens: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Return a list of memory context items for AI injection.
        Used by opsx.memory.get_context() — always returns [] on failure.
        """
        try:
            ctx = self.build_context(module, query, limit=limit, max_tokens=max_tokens)
            return ctx.items
        except Exception as exc:
            log.error("MemoryRouter.get_context failed: %s", exc)
            return []

    def build_context(
        self,
        module: str,
        query: str,
        limit: Optional[int] = None,
        max_tokens: Optional[int] = None,
    ) -> BuiltContext:
        """
        Build a BuiltContext for the given module + query.
        Merges results from extra_modules if configured.
        """
        profile = _PROFILES.get(module, _DEFAULT_PROFILE)
        _limit      = limit      or profile["limit"]
        _max_tokens = max_tokens or profile["max_tokens"]
        _fmt        = profile["fmt"]
        _extra      = profile["extra_modules"]

        # Primary module context
        ctx = self._builder.build(
            query=query,
            module=module,
            limit=_limit,
            max_tokens=_max_tokens,
            fmt=_fmt,
        )

        # Merge extra module context (cross-module enrichment)
        if _extra:
            remaining = _max_tokens - ctx.tokens
            if remaining > 100:
                per_extra = remaining // len(_extra)
                for extra_mod in _extra:
                    extra_ctx = self._builder.build(
                        query=query,
                        module=extra_mod,
                        limit=max(2, _limit // 2),
                        max_tokens=per_extra,
                        fmt=_fmt,
                    )
                    if extra_ctx:
                        ctx = _merge_contexts(ctx, extra_ctx, _max_tokens)

        return ctx

    def build_summary_context(self, module: str) -> BuiltContext:
        """Module-wide cold-start summary (no query)."""
        profile = _PROFILES.get(module, _DEFAULT_PROFILE)
        return self._builder.build_module_summary(
            module=module,
            limit=profile["limit"],
            max_tokens=profile["max_tokens"],
        )

    def route_text(self, text: str) -> str:
        """
        Infer module from free-text input for routing decisions.
        Returns a Module constant or Module.GENERAL.
        """
        t = text.lower()
        if any(w in t for w in ["golf", "swing", "handicap", "putt", "iron", "driver", "birdie"]):
            return Module.GOLF
        if any(w in t for w in ["stock", "market", "invest", "finance", "portfolio", "trade", "crypto"]):
            return Module.FINANCE
        if any(w in t for w in ["workout", "fitness", "exercise", "health", "weight", "run", "gym"]):
            return Module.HEALTH
        if any(w in t for w in ["email", "outlook", "inbox", "message", "reply"]):
            return Module.EMAIL
        if any(w in t for w in ["calendar", "meeting", "appointment", "schedule", "event"]):
            return Module.CALENDAR
        if any(w in t for w in ["task", "project", "todo", "plan", "productivity", "work"]):
            return Module.PRODUCTIVITY
        return Module.GENERAL


# ── Merge helpers ──────────────────────────────────────────────────────────────

def _merge_contexts(primary: BuiltContext, secondary: BuiltContext, max_tokens: int) -> BuiltContext:
    from .context_builder import BuiltContext, _estimate_tokens
    if not secondary:
        return primary
    combined_text   = primary.text + "\n" + secondary.text
    combined_tokens = primary.tokens + secondary.tokens
    combined_items  = primary.items + secondary.items
    if combined_tokens > max_tokens:
        combined_text = combined_text[:int(max_tokens / 0.25)]
        combined_tokens = max_tokens
    return BuiltContext(combined_text, combined_tokens, combined_items)
