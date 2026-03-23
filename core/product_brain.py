from __future__ import annotations

from typing import Dict, Any, List, Optional
import re
import yfinance as yf
import numpy as np


class ProductBrain:

    def __init__(self):
        self.alias_map = {
            "apple": "AAPL",
            "tesla": "TSLA",
            "nvidia": "NVDA",
            "nvdia": "NVDA",
            "microsoft": "MSFT",
            "amd": "AMD",
            "google": "GOOGL",
            "amazon": "AMZN",
            "meta": "META",
            "coinbase": "COIN",
            "palantir": "PLTR",
            "exxon": "XOM",
            "chevron": "CVX",
            "oxy": "OXY",
            "uso": "USO",
            "tsm": "TSM",
            "crm": "CRM",
            "salesforce": "CRM",
            "asml": "ASML",
            "avgo": "AVGO",
            "broadcom": "AVGO"
        }

        self.last_symbols: List[str] = []

    def health(self) -> dict:
        return {
            "available": True,
            "boot_errors": [],
            "orchestrator_available": True,
        }

    def _extract_symbols_from_text(self, text: str):
        text_lower = text.lower()

        detected = set()

        # Detect via alias
        for word, symbol in self.alias_map.items():
            if word in text_lower:
                detected.add(symbol)

        # Detect direct symbols
        text_upper = text.upper()

        possible = [
            "AAPL","TSLA","NVDA","MSFT","AMD",
            "GOOGL","META","AMZN","COIN","PLTR",
            "XOM","CVX","OXY","XLE","USO","TSM",
            "CRM","ASML","AVGO"
        ]

        for sym in possible:
            if sym in text_upper:
                detected.add(sym)

        return list(detected)
