from __future__ import annotations

import hashlib
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional


class LiveNewsEngine:
    """
    Multi-source RSS news aggregator.
    Returns rich items: id, title, source, source_label, link, summary,
    published_at, category, tickers.
    """

    SOURCES: Dict[str, Dict[str, str]] = {
        "reuters_world": {
            "url":      "http://feeds.reuters.com/Reuters/worldNews",
            "label":    "Reuters",
            "category": "World",
        },
        "reuters_business": {
            "url":      "http://feeds.reuters.com/reuters/businessNews",
            "label":    "Reuters",
            "category": "Business",
        },
        "bbc_world": {
            "url":      "https://feeds.bbci.co.uk/news/world/rss.xml",
            "label":    "BBC News",
            "category": "World",
        },
        "bbc_business": {
            "url":      "https://feeds.bbci.co.uk/news/business/rss.xml",
            "label":    "BBC News",
            "category": "Business",
        },
        "cnbc_top": {
            "url":      "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114",
            "label":    "CNBC",
            "category": "Markets",
        },
        "cnbc_markets": {
            "url":      "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=15839135",
            "label":    "CNBC",
            "category": "Markets",
        },
        "marketwatch": {
            "url":      "https://feeds.marketwatch.com/marketwatch/topstories/",
            "label":    "MarketWatch",
            "category": "Markets",
        },
        "ap_finance": {
            "url":      "https://feeds.feedburner.com/APTopBusinessNews",
            "label":    "AP News",
            "category": "Business",
        },
    }

    _TICKER_PATTERN = re.compile(r"\b([A-Z]{2,5})\b")
    _KNOWN_TICKERS  = {
        "AAPL","MSFT","NVDA","AMZN","GOOGL","META","TSLA","NFLX","AMD","INTC",
        "PLTR","COIN","BTC","ETH","SPY","QQQ","GLD","SLV","XOM","CVX","JPM",
        "GS","BAC","WMT","COST","UNH","V","MA","PYPL","UBER","LYFT","SPOT",
    }

    def fetch(self, limit_per_source: int = 5) -> List[Dict[str, Any]]:
        try:
            import feedparser
        except ImportError:
            return self._fallback_items()

        items: List[Dict[str, Any]] = []
        seen:  set = set()

        for source_key, meta in self.SOURCES.items():
            try:
                feed  = feedparser.parse(meta["url"])
                count = 0
                for entry in feed.entries:
                    if count >= limit_per_source:
                        break
                    title = (entry.get("title") or "").strip()
                    link  = (entry.get("link")  or "").strip()
                    if not title:
                        continue

                    dedup_key = title.lower()[:80]
                    if dedup_key in seen:
                        continue
                    seen.add(dedup_key)

                    summary = self._extract_summary(entry)
                    pub_at  = self._extract_date(entry)
                    tickers = self._detect_tickers(title + " " + summary)
                    item_id = hashlib.md5(f"{source_key}{title}".encode()).hexdigest()[:12]

                    items.append({
                        "id":           item_id,
                        "title":        title,
                        "source":       source_key,
                        "source_label": meta["label"],
                        "publisher":    meta["label"],
                        "category":     meta["category"],
                        "link":         link,
                        "url":          link,
                        "summary":      summary,
                        "published_at": pub_at,
                        "tickers":      tickers,
                    })
                    count += 1
            except Exception:
                continue

        return items

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _extract_summary(self, entry: Any) -> str:
        for field in ("summary", "description", "content"):
            raw = entry.get(field)
            if isinstance(raw, list):
                raw = raw[0].get("value", "") if raw else ""
            if raw:
                clean = re.sub(r"<[^>]+>", " ", str(raw))
                clean = re.sub(r"\s+", " ", clean).strip()
                return clean[:400]
        return ""

    def _extract_date(self, entry: Any) -> str:
        for field in ("published", "updated", "created"):
            val = entry.get(field)
            if val:
                return str(val)[:32]
        t = entry.get("published_parsed") or entry.get("updated_parsed")
        if t:
            try:
                return datetime(*t[:6]).isoformat()
            except Exception:
                pass
        return datetime.utcnow().isoformat()

    def _detect_tickers(self, text: str) -> List[str]:
        candidates = self._TICKER_PATTERN.findall(text)
        return list({c for c in candidates if c in self._KNOWN_TICKERS})[:5]

    def _fallback_items(self) -> List[Dict[str, Any]]:
        return [{
            "id":           "fallback_001",
            "title":        "News feed temporarily unavailable — feedparser not installed",
            "source":       "system",
            "source_label": "JARVIS",
            "publisher":    "JARVIS",
            "category":     "System",
            "link":         "",
            "url":          "",
            "summary":      "Install feedparser to enable the news feed.",
            "published_at": datetime.utcnow().isoformat(),
            "tickers":      [],
        }]
