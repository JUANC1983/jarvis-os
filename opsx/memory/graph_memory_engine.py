"""
GraphMemoryEngine — main API layer over MemoryStore.
All external callers use this, not the store directly.
"""
from __future__ import annotations

import hashlib
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from .memory_models import MemoryEdge, MemoryNode, NodeType
from .memory_store import MemoryStore

log = logging.getLogger("jarvis.memory.engine")


class GraphMemoryEngine:

    def __init__(self, store_path: str = "data/memory_graph.json") -> None:
        self._store = MemoryStore(store_path)

    # ── Node management ────────────────────────────────────────────────────

    def add_node(
        self,
        node_id: str,
        node_type: str,
        label: str,
        module: str,
        content: str,
        importance: float = 0.5,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MemoryNode:
        node = MemoryNode(
            id=node_id,
            type=node_type,
            label=label,
            module=module,
            content=content,
            importance=max(0.0, min(1.0, importance)),
            tags=tags or [],
            metadata=metadata or {},
        )
        return self._store.upsert_node(node)

    def get_node(self, node_id: str) -> Optional[MemoryNode]:
        return self._store.get_node(node_id)

    def delete_node(self, node_id: str) -> bool:
        return self._store.delete_node(node_id)

    def list_nodes(
        self,
        module: Optional[str] = None,
        node_type: Optional[str] = None,
        tag: Optional[str] = None,
        limit: int = 50,
    ) -> List[MemoryNode]:
        return self._store.list_nodes(module=module, node_type=node_type, tag=tag, limit=limit)

    # ── Edge management ────────────────────────────────────────────────────

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        relation: str,
        weight: float = 0.5,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[MemoryEdge]:
        if source_id not in self._store._nodes:
            log.warning("add_edge: source node %s not found", source_id)
            return None
        if target_id not in self._store._nodes:
            log.warning("add_edge: target node %s not found", target_id)
            return None
        edge_id = _edge_id(source_id, target_id, relation)
        edge = MemoryEdge(
            id=edge_id,
            source_id=source_id,
            target_id=target_id,
            relation=relation,
            weight=max(0.0, min(1.0, weight)),
            metadata=metadata or {},
        )
        return self._store.upsert_edge(edge)

    def delete_edge(self, edge_id: str) -> bool:
        return self._store.delete_edge(edge_id)

    # ── Search and retrieval ───────────────────────────────────────────────

    def search_nodes(
        self,
        query: str,
        module: Optional[str] = None,
        limit: int = 10,
    ) -> List[MemoryNode]:
        return self._store.search_nodes(query, module=module, limit=limit)

    def get_related_nodes(
        self,
        node_id: str,
        depth: int = 1,
        relation: Optional[str] = None,
        limit: int = 10,
    ) -> List[Tuple[MemoryNode, MemoryEdge]]:
        """
        Return (node, edge) pairs reachable from node_id within `depth` hops.
        depth=1 returns direct neighbours only.
        """
        visited: set[str] = {node_id}
        results: List[Tuple[MemoryNode, MemoryEdge]] = []

        frontier = [node_id]
        for _ in range(depth):
            next_frontier = []
            for nid in frontier:
                edges = self._store.get_edges_for_node(nid, direction="out", relation=relation)
                for edge in edges:
                    tid = edge.target_id
                    if tid in visited:
                        continue
                    neighbour = self._store.get_node(tid)
                    if neighbour:
                        results.append((neighbour, edge))
                        visited.add(tid)
                        next_frontier.append(tid)
            frontier = next_frontier
            if not frontier:
                break

        results.sort(key=lambda x: x[1].weight * x[0].effective_importance(), reverse=True)
        return results[:limit]

    def get_context_for_query(
        self,
        query: str,
        module: Optional[str] = None,
        limit: int = 5,
        include_related: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Build a ranked context list for an AI call.
        Returns dicts with {node_id, type, label, content, importance, source}.
        """
        results: List[Tuple[float, Dict]] = []

        # Primary: direct keyword search
        direct = self._store.search_nodes(query, module=module, limit=limit * 2)
        for node in direct:
            results.append((node.effective_importance(), {
                "node_id":    node.id,
                "type":       node.type,
                "label":      node.label,
                "content":    node.content,
                "importance": node.effective_importance(),
                "module":     node.module,
                "source":     "search",
            }))

        # Secondary: related nodes from top result
        if include_related and direct:
            top = direct[0]
            related = self.get_related_nodes(top.id, depth=1, limit=3)
            for rnode, redge in related:
                score = rnode.effective_importance() * redge.weight * 0.8
                results.append((score, {
                    "node_id":    rnode.id,
                    "type":       rnode.type,
                    "label":      rnode.label,
                    "content":    rnode.content,
                    "importance": rnode.effective_importance(),
                    "module":     rnode.module,
                    "source":     f"related:{redge.relation}",
                    "relation":   redge.relation,
                    "via":        top.id,
                }))

        # Deduplicate and rank
        seen: set[str] = set()
        ranked = []
        for score, item in sorted(results, key=lambda x: x[0], reverse=True):
            if item["node_id"] not in seen:
                seen.add(item["node_id"])
                ranked.append(item)
            if len(ranked) >= limit:
                break

        return ranked

    def summarize_context(self, module: Optional[str] = None, limit: int = 10) -> str:
        """
        Build a concise text summary of high-importance memories for a module.
        Used for cold-start context injection.
        """
        nodes = self._store.list_nodes(module=module, limit=limit)
        if not nodes:
            return ""
        lines = []
        for n in nodes:
            lines.append(f"- [{n.type}] {n.label}: {n.content[:200]}")
        return "\n".join(lines)

    # ── Stats & health ─────────────────────────────────────────────────────

    def stats(self) -> Dict[str, Any]:
        return self._store.stats()

    def node_count(self) -> int:
        return self._store.node_count

    def edge_count(self) -> int:
        return self._store.edge_count

    def health(self) -> Dict[str, Any]:
        s = self._store.stats()
        s["status"] = "ok"
        s["store_writable"] = _check_writable(self._store._path)
        return s


# ── Helpers ────────────────────────────────────────────────────────────────────

def _edge_id(source: str, target: str, relation: str) -> str:
    key = f"{source}:{relation}:{target}"
    return "edge_" + hashlib.md5(key.encode()).hexdigest()[:10]


def _check_writable(path) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        test = path.parent / ".write_test"
        test.write_text("x")
        test.unlink()
        return True
    except Exception:
        return False
