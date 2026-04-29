"""
MemoryNode and MemoryEdge dataclasses.
Serialisable to/from plain dicts for JSON persistence.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


@dataclass
class MemoryNode:
    """
    A single memory entity — person, event, preference, fact, project, etc.

    Fields
    ------
    id          : unique node identifier (e.g. "person_juan", "pref_golf_driver")
    type        : semantic category — person / preference / event / fact / project / habit / goal
    label       : human-readable name
    module      : which JARVIS module owns this (golf, finance, productivity, health, system, general)
    content     : the actual remembered text
    importance  : 0.0-1.0 relevance score, used for context ranking
    tags        : free-form labels for cross-module search
    created_at  : unix timestamp
    updated_at  : unix timestamp
    access_count: number of times retrieved — boosts importance over time
    metadata    : arbitrary extra fields (e.g. handicap, email, ticker)
    """
    id:           str
    type:         str
    label:        str
    module:       str
    content:      str
    importance:   float                  = 0.5
    tags:         List[str]              = field(default_factory=list)
    created_at:   float                  = field(default_factory=time.time)
    updated_at:   float                  = field(default_factory=time.time)
    access_count: int                    = 0
    metadata:     Dict[str, Any]         = field(default_factory=dict)

    # ── Serialisation ──────────────────────────────────────────────────────

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict) -> "MemoryNode":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    # ── Helpers ────────────────────────────────────────────────────────────

    def touch(self) -> None:
        """Record access — increments counter and updates timestamp."""
        self.access_count += 1
        self.updated_at = time.time()

    def effective_importance(self) -> float:
        """Blends base importance with access frequency bonus (max 0.2 bonus)."""
        freq_bonus = min(self.access_count * 0.01, 0.2)
        return min(self.importance + freq_bonus, 1.0)

    def matches_tags(self, query_tags: List[str]) -> bool:
        return bool(set(self.tags) & set(query_tags))

    def __repr__(self) -> str:
        return f"MemoryNode(id={self.id!r}, type={self.type!r}, label={self.label!r})"


@dataclass
class MemoryEdge:
    """
    A directed relationship between two MemoryNodes.

    Fields
    ------
    id            : unique edge identifier
    source_id     : origin node id
    target_id     : destination node id
    relation      : semantic label (knows / has / uses / likes / dislikes / part_of / related_to)
    weight        : 0.0-1.0 relationship strength
    created_at    : unix timestamp
    metadata      : arbitrary extra context
    """
    id:         str
    source_id:  str
    target_id:  str
    relation:   str
    weight:     float                = 0.5
    created_at: float                = field(default_factory=time.time)
    metadata:   Dict[str, Any]       = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict) -> "MemoryEdge":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def __repr__(self) -> str:
        return f"MemoryEdge({self.source_id!r} --[{self.relation}]--> {self.target_id!r})"


# ── Node type constants ────────────────────────────────────────────────────────

class NodeType:
    PERSON     = "person"
    PREFERENCE = "preference"
    EVENT      = "event"
    FACT       = "fact"
    PROJECT    = "project"
    HABIT      = "habit"
    GOAL       = "goal"
    SKILL      = "skill"
    CONTACT    = "contact"

    ALL = {PERSON, PREFERENCE, EVENT, FACT, PROJECT, HABIT, GOAL, SKILL, CONTACT}


class EdgeRelation:
    KNOWS      = "knows"
    HAS        = "has"
    USES       = "uses"
    LIKES      = "likes"
    DISLIKES   = "dislikes"
    PART_OF    = "part_of"
    RELATED_TO = "related_to"
    CREATED    = "created"
    ASSIGNED   = "assigned"

    ALL = {KNOWS, HAS, USES, LIKES, DISLIKES, PART_OF, RELATED_TO, CREATED, ASSIGNED}


class Module:
    GOLF         = "golf"
    FINANCE      = "finance"
    PRODUCTIVITY = "productivity"
    HEALTH       = "health"
    SYSTEM       = "system"
    GENERAL      = "general"
    EMAIL        = "email"
    CALENDAR     = "calendar"

    ALL = {GOLF, FINANCE, PRODUCTIVITY, HEALTH, SYSTEM, GENERAL, EMAIL, CALENDAR}
