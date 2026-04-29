"""
ContextBuilder — converts graph memory nodes into compact AI-ready context strings.
Tracks estimated token cost so callers can budget context window usage.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .graph_memory_engine import GraphMemoryEngine

log = logging.getLogger("jarvis.memory.context_builder")

_TOKENS_PER_CHAR = 0.25   # ~4 chars per token


def _estimate_tokens(text: str) -> int:
    return max(1, int(len(text) * _TOKENS_PER_CHAR))


class ContextBuilder:

    def __init__(self, engine: GraphMemoryEngine) -> None:
        self._engine = engine

    def build(
        self,
        query: str,
        module: Optional[str] = None,
        limit: int = 5,
        max_tokens: int = 800,
        fmt: str = "bullet",   # "bullet" | "json" | "prose"
    ) -> "BuiltContext":
        """
        Build a context block for injection into an AI system prompt.

        Returns a BuiltContext with .text and .tokens attributes.
        Returns empty context if nothing relevant found or engine fails.
        """
        try:
            items = self._engine.get_context_for_query(query, module=module, limit=limit)
        except Exception as exc:
            log.error("ContextBuilder.build failed: %s", exc)
            return BuiltContext("", 0, [])

        if not items:
            return BuiltContext("", 0, [])

        lines = []
        total_tokens = 0

        for item in items:
            line = _format_item(item, fmt)
            toks = _estimate_tokens(line)
            if total_tokens + toks > max_tokens:
                log.debug("Context budget reached at %d tokens", total_tokens)
                break
            lines.append(line)
            total_tokens += toks

        if not lines:
            return BuiltContext("", 0, [])

        header = "### Relevant Memory Context\n"
        body   = "\n".join(lines)
        text   = header + body
        total_tokens += _estimate_tokens(header)

        return BuiltContext(text, total_tokens, items[:len(lines)])

    def build_module_summary(
        self,
        module: str,
        limit: int = 8,
        max_tokens: int = 600,
    ) -> "BuiltContext":
        """
        Build a module-wide summary (for cold-start context, not query-specific).
        """
        try:
            raw = self._engine.summarize_context(module=module, limit=limit)
        except Exception as exc:
            log.error("ContextBuilder.build_module_summary failed: %s", exc)
            return BuiltContext("", 0, [])

        if not raw:
            return BuiltContext("", 0, [])

        text = f"### {module.title()} Memory Summary\n{raw}"
        tokens = _estimate_tokens(text)

        if tokens > max_tokens:
            truncated = raw[: int(max_tokens / _TOKENS_PER_CHAR)]
            text = f"### {module.title()} Memory Summary\n{truncated}…"
            tokens = max_tokens

        return BuiltContext(text, tokens, [])


class BuiltContext:
    """Returned by ContextBuilder — holds rendered text and cost estimate."""

    __slots__ = ("text", "tokens", "items")

    def __init__(self, text: str, tokens: int, items: List[Dict]) -> None:
        self.text   = text
        self.tokens = tokens
        self.items  = items   # raw item dicts from engine

    def __bool__(self) -> bool:
        return bool(self.text)

    def as_messages_entry(self) -> Optional[Dict]:
        """Convenience: wrap as an OpenAI-style system message dict, or None if empty."""
        if not self.text:
            return None
        return {"role": "system", "content": self.text}

    def __repr__(self) -> str:
        return f"BuiltContext(tokens={self.tokens}, items={len(self.items)})"


# ── Formatting helpers ─────────────────────────────────────────────────────────

def _format_item(item: Dict[str, Any], fmt: str) -> str:
    label   = item.get("label", "?")
    content = item.get("content", "")
    node_type = item.get("type", "")
    relation = item.get("relation", "")
    via      = item.get("via", "")

    if fmt == "json":
        import json
        return json.dumps({k: item[k] for k in ("label", "content", "type", "source") if k in item})

    if fmt == "prose":
        rel_str = f" (via {relation} ← {via})" if relation else ""
        return f"{label}{rel_str}: {content}"

    # Default: bullet
    rel_str = f" [{relation}]" if relation else ""
    return f"- **{label}**{rel_str} ({node_type}): {content}"
