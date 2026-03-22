from __future__ import annotations

from typing import Dict, List

import yfinance as yf


class NewsCatalystEngine:
    POSITIVE = [
        "beat", "beats", "upgrade", "upgrades", "raise", "raises", "raised",
        "guidance", "partnership", "contract", "approval", "approved",
        "acquisition", "acquire", "launch", "breakthrough", "record",
        "surge", "growth", "expands", "expansion", "buyback", "strong"
    ]

    NEGATIVE = [
        "miss", "misses", "downgrade", "downgrades", "cut", "cuts", "cutting",
        "lawsuit", "probe", "investigation", "delay", "weak", "warning",
        "decline", "fall", "falls", "fraud", "recall", "soft", "guidance cut"
    ]

    def analyze(self, symbol: str) -> Dict:
        try:
            ticker = yf.Ticker(symbol)
            raw_news = getattr(ticker, "news", []) or []
        except Exception:
            raw_news = []

        if not raw_news:
            return {
                "catalyst_score": 0,
                "headlines": [],
                "catalyst_summary": "Sin catalizador fuerte detectado en noticias recientes."
            }

        headlines: List[str] = []
        score = 0

        for item in raw_news[:8]:
            title = str(item.get("title", "")).strip()
            if not title:
                continue

            headlines.append(title)
            low = title.lower()

            for word in self.POSITIVE:
                if word in low:
                    score += 2

            for word in self.NEGATIVE:
                if word in low:
                    score -= 2

        score = max(-12, min(12, score))

        if score >= 6:
            summary = "Catalizador positivo reciente en noticias."
        elif score >= 2:
            summary = "Noticias con sesgo ligeramente positivo."
        elif score <= -6:
            summary = "Catalizador negativo reciente en noticias."
        elif score <= -2:
            summary = "Noticias con sesgo ligeramente negativo."
        else:
            summary = "Noticias mixtas o sin impacto claro."

        return {
            "catalyst_score": score,
            "headlines": headlines[:3],
            "catalyst_summary": summary
        }
