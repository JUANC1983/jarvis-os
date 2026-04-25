from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import faiss
    import numpy as np
    from sentence_transformers import SentenceTransformer
    _VECTOR_AVAILABLE = True
except Exception:
    _VECTOR_AVAILABLE = False


_UNAVAILABLE_MSG = "Vector memory requires faiss-cpu + sentence-transformers. Running keyword-only fallback."


class VectorMemoryPro:
    """
    Semantic vector memory with FAISS + sentence-transformers.
    Gracefully degrades to stub when libraries are unavailable.
    """

    def __init__(self, base_path: str = "data/vector_memory_pro") -> None:
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.index_path = self.base_path / "memory.index"
        self.meta_path  = self.base_path / "memory.json"
        self._ready = False

        if _VECTOR_AVAILABLE:
            try:
                self._model = SentenceTransformer("all-MiniLM-L6-v2")
                self._dim   = 384

                if self.index_path.exists():
                    self._index = faiss.read_index(str(self.index_path))
                else:
                    self._index = faiss.IndexFlatL2(self._dim)

                self._memory: List[Dict[str, Any]] = (
                    json.loads(self.meta_path.read_text(encoding="utf-8"))
                    if self.meta_path.exists() else []
                )
                self._ready = True
            except Exception:
                self._memory = []
        else:
            self._memory = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def store(self, text: str, category: str = "general", metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not text.strip():
            return {"status": "error", "message": "text is required"}

        if not self._ready:
            entry = {"id": len(self._memory), "text": text, "category": category, "metadata": metadata or {}}
            self._memory.append(entry)
            try:
                self.meta_path.write_text(
                    json.dumps(self._memory, ensure_ascii=False, indent=2), encoding="utf-8"
                )
            except Exception:
                pass
            return {"status": "ok_fallback", "stored_id": entry["id"], "category": category, "note": _UNAVAILABLE_MSG}

        vector = self._model.encode([text])[0].astype("float32")
        self._index.add(np.array([vector], dtype="float32"))
        entry = {"id": len(self._memory), "text": text, "category": category, "metadata": metadata or {}}
        self._memory.append(entry)
        self._persist()
        return {"status": "ok", "stored_id": entry["id"], "category": category, "text": text}

    def search(self, query: str, k: int = 5) -> Dict[str, Any]:
        if not self._memory:
            return {"status": "ok", "query": query, "results": [], "summary": "No memories stored yet."}

        if not self._ready:
            keyword = query.lower()
            results = [m for m in self._memory if keyword in m.get("text", "").lower()][:k]
            return {
                "status": "ok_fallback",
                "query": query,
                "results": results,
                "summary": f"Keyword fallback: {len(results)} result(s). {_UNAVAILABLE_MSG}",
            }

        k = max(1, min(k, len(self._memory)))
        vector = self._model.encode([query])[0].astype("float32")
        distances, indices = self._index.search(np.array([vector], dtype="float32"), k)

        results = []
        for rank, idx in enumerate(indices[0].tolist()):
            if 0 <= idx < len(self._memory):
                item = self._memory[idx].copy()
                item["distance"] = float(distances[0][rank])
                results.append(item)

        return {"status": "ok", "query": query, "results": results, "summary": f"Retrieved {len(results)} items."}

    def categories(self) -> Dict[str, Any]:
        cats = sorted({m.get("category", "general") for m in self._memory})
        return {"count": len(self._memory), "categories": cats, "vector_ready": self._ready}

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _persist(self) -> None:
        faiss.write_index(self._index, str(self.index_path))
        self.meta_path.write_text(
            json.dumps(self._memory, ensure_ascii=False, indent=2), encoding="utf-8"
        )
