from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "jarvis_memory.json"
_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)

_MAX_ENTRIES = 500
_MAX_INJECT  = 4    # memories injected per LLM call
_MAX_CHARS   = 200  # max chars per memory in context string


class JarvisMemory:
    """
    Two-layer persistent memory:
      Layer 1 — FAISS vector index (semantic similarity, background init)
      Layer 2 — JSON keyword fallback (always available immediately)

    Thread-safe. Non-blocking disk writes. Background vector init.
    """

    def __init__(self) -> None:
        self._lock         = threading.Lock()
        self._entries:     List[Dict[str, Any]] = []
        self._vector_ready = False
        self._index        = None
        self._model        = None

        self._load_from_disk()
        threading.Thread(target=self._init_vector, daemon=True).start()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def store(
        self,
        user_input: str,
        output: str,
        agent: str = "",
        domain: str = "",
        tags: List[str] | None = None,
        metadata: Dict[str, Any] | None = None,
    ) -> None:
        entry: Dict[str, Any] = {
            "ts":       datetime.utcnow().isoformat(),
            "user":     (user_input or "")[:400],
            "output":   (output or "")[:400],
            "agent":    agent,
            "domain":   domain,
            "tags":     tags or [],
            "metadata": metadata or {},
        }
        with self._lock:
            self._entries.append(entry)
            if len(self._entries) > _MAX_ENTRIES:
                self._entries = self._entries[-_MAX_ENTRIES:]

            if self._vector_ready and self._index is not None:
                try:
                    import numpy as np
                    vec = self._model.encode([user_input])[0]
                    self._index.add(np.array([vec]).astype("float32"))
                except Exception:
                    pass

        threading.Thread(target=self._save_to_disk, daemon=True).start()

    def recall(self, context: str, k: int = 5) -> List[Dict[str, Any]]:
        """Semantic recall if vector ready, keyword fallback otherwise."""
        with self._lock:
            entries = list(self._entries)

        if not entries:
            return []

        if self._vector_ready and self._index is not None and self._index.ntotal > 0:
            return self._vector_recall(context, k, entries)
        return self._keyword_recall(context, k, entries)

    def as_context_string(self, context: str, k: int = _MAX_INJECT) -> str:
        """Compact memory block for LLM injection (≤ ~800 chars)."""
        mems = self.recall(context, k)
        if not mems:
            return ""
        lines = []
        for m in mems:
            u  = m["user"][:80]
            o  = m["output"][:_MAX_CHARS]
            ts = m["ts"][:10]
            lines.append(f"[{ts}] You: {u} → JARVIS: {o}")
        return "Past interactions:\n" + "\n".join(lines)

    def last_n(self, n: int = 8) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._entries[-n:])

    def domain_stats(self, domain: str) -> Dict[str, Any]:
        with self._lock:
            items = [e for e in self._entries if e.get("domain") == domain]
        return {
            "domain": domain,
            "count":  len(items),
            "agents": list({e.get("agent", "") for e in items} - {""}),
            "latest": items[-1]["ts"] if items else None,
        }

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            total   = len(self._entries)
            domains = list({e.get("domain", "") for e in self._entries} - {""})
        return {
            "total_entries": total,
            "vector_ready":  self._vector_ready,
            "domains":       domains,
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _vector_recall(
        self, query: str, k: int, entries: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        try:
            import numpy as np
            vec  = self._model.encode([query])[0]
            D, I = self._index.search(np.array([vec]).astype("float32"), k)
            return [entries[i] for i in I[0] if 0 <= i < len(entries)]
        except Exception:
            return self._keyword_recall(query, k, entries)

    def _keyword_recall(
        self, query: str, k: int, entries: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        words = set(query.lower().split())
        scored: List[tuple] = []
        for e in entries:
            text  = (e["user"] + " " + e["output"]).lower()
            score = sum(1 for w in words if w in text)
            if score > 0:
                scored.append((score, e))
        scored.sort(key=lambda x: -x[0])
        return [e for _, e in scored[:k]]

    def _init_vector(self) -> None:
        try:
            import faiss
            import numpy as np
            from sentence_transformers import SentenceTransformer

            model = SentenceTransformer("all-MiniLM-L6-v2")
            index = faiss.IndexFlatL2(384)

            with self._lock:
                if self._entries:
                    vecs = model.encode([e["user"] for e in self._entries])
                    index.add(np.array(vecs).astype("float32"))
                self._model        = model
                self._index        = index
                self._vector_ready = True
        except Exception:
            pass  # stay on keyword fallback — no crash

    def _load_from_disk(self) -> None:
        try:
            if _DATA_PATH.exists():
                data = json.loads(_DATA_PATH.read_text(encoding="utf-8"))
                with self._lock:
                    self._entries = data if isinstance(data, list) else []
        except Exception:
            pass

    def _save_to_disk(self) -> None:
        try:
            with self._lock:
                snapshot = list(self._entries)
            _DATA_PATH.write_text(
                json.dumps(snapshot, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
_instance: JarvisMemory | None = None
_instance_lock = threading.Lock()


def get_jarvis_memory() -> JarvisMemory:
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = JarvisMemory()
    return _instance
