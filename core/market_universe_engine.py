from __future__ import annotations

import os
from typing import List


class MarketUniverseEngine:
    def __init__(self) -> None:
        self.base_dir = os.path.dirname(os.path.dirname(__file__))
        self.default_file = os.path.join(self.base_dir, "data", "market_universe.txt")

    def _normalize(self, symbols: List[str]) -> List[str]:
        clean = []
        seen = set()

        for raw in symbols:
            value = str(raw).strip().upper().replace(".", "-")
            if not value:
                continue
            if not value[0].isalnum():
                continue
            if value in seen:
                continue
            seen.add(value)
            clean.append(value)

        return clean

    def get_universe(self) -> List[str]:
        symbols: List[str] = []

        file_path = os.getenv("MARKET_UNIVERSE_FILE", self.default_file)

        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                symbols.extend([line.strip() for line in f.readlines() if line.strip()])

        extra = os.getenv("MARKET_EXTRA_SYMBOLS", "")
        if extra.strip():
            symbols.extend([x.strip() for x in extra.split(",") if x.strip()])

        symbols = self._normalize(symbols)

        max_symbols = int(os.getenv("MARKET_SCAN_MAX_SYMBOLS", "400"))
        if max_symbols > 0:
            symbols = symbols[:max_symbols]

        return symbols
