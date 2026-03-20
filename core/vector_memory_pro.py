from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer


class VectorMemoryPro:
    def __init__(self, base_path: str = "data/vector_memory_pro") -> None:
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

        self.index_path = self.base_path / "memory.index"
        self.meta_path = self.base_path / "memory.json"

        self.model = SentenceTransformer("all-MiniLM-L6-v2")
        self.dimension = 384

        if self.index_path.exists():
            self.index = faiss.read_index(str(self.index_path))
        else:
            self.index = faiss.IndexFlatL2(self.dimension)

        if self.meta_path.exists():
            self.memory: List[Dict[str, Any]] = json.loads(self.meta_path.read_text(encoding="utf-8"))
        else:
            self.memory = []

    def _persist(self) -> None:
        faiss.write_index(self.index, str(self.index_path))
        self.meta_path.write_text(json.dumps(self.memory, ensure_ascii=False, indent=2), encoding="utf-8")

    def store(self, text: str, category: str = "general", metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not text.strip():
            return {"status": "error", "message": "text is required"}

        vector = self.model.encode([text])[0].astype("float32")
        self.index.add(np.array([vector], dtype="float32"))

        entry = {
            "id": len(self.memory),
            "text": text,
            "category": category,
            "metadata": metadata or {},
        }
        self.memory.append(entry)
        self._persist()

        return {
            "status": "ok",
            "stored_id": entry["id"],
            "category": category,
            "text": text,
        }

    def search(self, query: str, k: int = 5) -> Dict[str, Any]:
        if len(self.memory) == 0:
            return {
                "status": "ok",
                "query": query,
                "results": [],
                "summary": "No semantic memories stored yet.",
            }

        k = max(1, min(k, len(self.memory)))
        vector = self.model.encode([query])[0].astype("float32")
        distances, indices = self.index.search(np.array([vector], dtype="float32"), k)

        results = []
        for rank, idx in enumerate(indices[0].tolist()):
            if 0 <= idx < len(self.memory):
                item = self.memory[idx].copy()
                item["distance"] = float(distances[0][rank])
                results.append(item)

        return {
            "status": "ok",
            "query": query,
            "results": results,
            "summary": f"Retrieved {len(results)} semantic memory items.",
        }

    def categories(self) -> Dict[str, Any]:
        cats = sorted(list({m.get("category", "general") for m in self.memory}))
        return {"count": len(self.memory), "categories": cats}
