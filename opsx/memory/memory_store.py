"""
Thread-safe JSON-backed storage for MemoryNode and MemoryEdge objects.
Designed for swap to a real graph DB later — only this file needs changing.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .memory_models import MemoryEdge, MemoryNode

log = logging.getLogger("jarvis.memory.store")

_DEFAULT_PATH = "data/memory_graph.json"


class MemoryStore:
    """
    Persistence layer for graph memory.

    Schema on disk:
    {
      "nodes": { "<id>": { ...MemoryNode.to_dict() } },
      "edges": { "<id>": { ...MemoryEdge.to_dict() } },
      "meta":  { "version": 1, "written_at": <ts> }
    }
    """

    VERSION = 1

    def __init__(self, path: str = _DEFAULT_PATH) -> None:
        self._lock = threading.Lock()
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._nodes: Dict[str, MemoryNode] = {}
        self._edges: Dict[str, MemoryEdge] = {}
        self._load()

    # ── Persistence ────────────────────────────────────────────────────────

    def _load(self) -> None:
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            for nid, nd in raw.get("nodes", {}).items():
                try:
                    self._nodes[nid] = MemoryNode.from_dict(nd)
                except Exception as e:
                    log.warning("Skipping bad node %s: %s", nid, e)
            for eid, ed in raw.get("edges", {}).items():
                try:
                    self._edges[eid] = MemoryEdge.from_dict(ed)
                except Exception as e:
                    log.warning("Skipping bad edge %s: %s", eid, e)
            log.info("Memory store loaded: %d nodes, %d edges", len(self._nodes), len(self._edges))
        except FileNotFoundError:
            log.info("No memory graph file found — starting fresh at %s", self._path)
        except Exception as e:
            log.error("Memory store load failed: %s — starting fresh", e)

    def _persist(self) -> None:
        try:
            data = {
                "nodes": {nid: n.to_dict() for nid, n in self._nodes.items()},
                "edges": {eid: e.to_dict() for eid, e in self._edges.items()},
                "meta":  {"version": self.VERSION, "written_at": time.time()},
            }
            self._path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            log.error("Memory store persist failed: %s", e)

    # ── Node CRUD ──────────────────────────────────────────────────────────

    def upsert_node(self, node: MemoryNode) -> MemoryNode:
        with self._lock:
            existing = self._nodes.get(node.id)
            if existing:
                existing.content     = node.content
                existing.importance  = node.importance
                existing.tags        = node.tags
                existing.metadata    = node.metadata
                existing.updated_at  = time.time()
                self._nodes[node.id] = existing
                log.debug("Node updated: %s", node.id)
            else:
                self._nodes[node.id] = node
                log.debug("Node created: %s", node.id)
            self._persist()
            return self._nodes[node.id]

    def get_node(self, node_id: str) -> Optional[MemoryNode]:
        node = self._nodes.get(node_id)
        if node:
            node.touch()
            with self._lock:
                self._persist()
        return node

    def delete_node(self, node_id: str) -> bool:
        with self._lock:
            if node_id not in self._nodes:
                return False
            del self._nodes[node_id]
            # Remove orphaned edges
            orphans = [eid for eid, e in self._edges.items()
                       if e.source_id == node_id or e.target_id == node_id]
            for eid in orphans:
                del self._edges[eid]
            self._persist()
            log.info("Node deleted: %s (removed %d edges)", node_id, len(orphans))
            return True

    def list_nodes(
        self,
        module: Optional[str] = None,
        node_type: Optional[str] = None,
        tag: Optional[str] = None,
        limit: int = 100,
    ) -> List[MemoryNode]:
        nodes = list(self._nodes.values())
        if module:
            nodes = [n for n in nodes if n.module == module]
        if node_type:
            nodes = [n for n in nodes if n.type == node_type]
        if tag:
            nodes = [n for n in nodes if tag in n.tags]
        nodes.sort(key=lambda n: n.effective_importance(), reverse=True)
        return nodes[:limit]

    def search_nodes(self, query: str, module: Optional[str] = None, limit: int = 10) -> List[MemoryNode]:
        """
        Multi-word keyword search across label + content + tags.
        Scores per-word hits — no need for exact phrase match.
        """
        words = [w for w in query.lower().split() if len(w) > 1]
        if not words:
            return self.list_nodes(module=module, limit=limit)

        results = []
        for node in self._nodes.values():
            if module and node.module != module:
                continue
            label_l   = node.label.lower()
            content_l = node.content.lower()
            tag_l     = [t.lower() for t in node.tags]

            score = 0.0
            for word in words:
                if word in label_l:
                    score += 0.6
                if word in content_l:
                    score += 0.3
                if any(word in t for t in tag_l):
                    score += 0.25
            if score > 0:
                results.append((score * node.effective_importance(), node))

        results.sort(key=lambda x: x[0], reverse=True)
        return [n for _, n in results[:limit]]

    # ── Edge CRUD ──────────────────────────────────────────────────────────

    def upsert_edge(self, edge: MemoryEdge) -> MemoryEdge:
        with self._lock:
            existing = self._edges.get(edge.id)
            if existing:
                existing.weight   = edge.weight
                existing.metadata = edge.metadata
                self._edges[edge.id] = existing
            else:
                self._edges[edge.id] = edge
            self._persist()
            return self._edges[edge.id]

    def get_edge(self, edge_id: str) -> Optional[MemoryEdge]:
        return self._edges.get(edge_id)

    def delete_edge(self, edge_id: str) -> bool:
        with self._lock:
            if edge_id not in self._edges:
                return False
            del self._edges[edge_id]
            self._persist()
            return True

    def get_edges_for_node(
        self,
        node_id: str,
        direction: str = "both",  # "out" | "in" | "both"
        relation: Optional[str] = None,
    ) -> List[MemoryEdge]:
        result = []
        for e in self._edges.values():
            if direction in ("out", "both") and e.source_id == node_id:
                result.append(e)
            elif direction in ("in", "both") and e.target_id == node_id:
                result.append(e)
        if relation:
            result = [e for e in result if e.relation == relation]
        result.sort(key=lambda e: e.weight, reverse=True)
        return result

    # ── Stats ──────────────────────────────────────────────────────────────

    def stats(self) -> Dict[str, Any]:
        from collections import Counter
        node_types   = Counter(n.type   for n in self._nodes.values())
        node_modules = Counter(n.module for n in self._nodes.values())
        edge_rels    = Counter(e.relation for e in self._edges.values())
        return {
            "node_count":    len(self._nodes),
            "edge_count":    len(self._edges),
            "node_types":    dict(node_types),
            "node_modules":  dict(node_modules),
            "edge_relations": dict(edge_rels),
            "store_path":    str(self._path),
        }

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    @property
    def edge_count(self) -> int:
        return len(self._edges)
