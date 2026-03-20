import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


class CognitiveMemoryEngine:
    """
    Memoria persistente simple y robusta.
    No reemplaza tu SuperMemorySystem: lo complementa.
    """

    def __init__(self, path: str = "memory/cognitive_memory.json") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

        if not self.path.exists():
            self._write({"items": []})

    def _read(self) -> Dict[str, Any]:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _write(self, data: Dict[str, Any]) -> None:
        self.path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def store(self, category: str, text: str, metadata: Dict[str, Any] | None = None) -> Dict[str, Any]:
        data = self._read()
        item = {
            "category": (category or "general").strip(),
            "text": (text or "").strip(),
            "metadata": metadata or {},
            "timestamp": datetime.utcnow().isoformat(),
        }
        data["items"].append(item)
        self._write(data)
        return item

    def search(self, keyword: str, limit: int = 10) -> List[str]:
        term = (keyword or "").strip().lower()
        if not term:
            return []

        items = self._read().get("items", [])
        results: List[str] = []

        for item in reversed(items):
            text = str(item.get("text", ""))
            if term in text.lower():
                results.append(text)
            if len(results) >= limit:
                break

        return results

    def recent(self, limit: int = 20) -> List[Dict[str, Any]]:
        items = self._read().get("items", [])
        return list(reversed(items[-limit:]))