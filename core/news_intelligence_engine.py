from __future__ import annotations

import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeout
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import feedparser

from core.news_catalyst_engine import NewsCatalystEngine


class NewsIntelligenceEngine:
    # ------------------------------------------------------------------ #
    # Original sources — preserved for backward compatibility              #
    # ------------------------------------------------------------------ #
    SOURCES = {
        "reuters_world": "http://feeds.reuters.com/Reuters/worldNews",
        "reuters_business": "http://feeds.reuters.com/reuters/businessNews",
    }

    # ------------------------------------------------------------------ #
    # Categorised sources for the dashboard feed                           #
    # Each entry: (display_name, rss_url)                                 #
    # ------------------------------------------------------------------ #
    CATEGORIZED_SOURCES: Dict[str, List[Tuple[str, str]]] = {
        "markets": [
            ("Yahoo Finance", "https://feeds.finance.yahoo.com/rss/2.0/headline?s=%5EGSPC&region=US&lang=en-US"),
            ("CNBC Markets",  "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114"),
            ("Reuters Business", "https://feeds.reuters.com/reuters/businessNews"),
            ("Seeking Alpha", "https://seekingalpha.com/market_currents.xml"),
        ],
        "tech": [
            ("TechCrunch",  "https://techcrunch.com/feed/"),
            ("Ars Technica", "https://feeds.arstechnica.com/arstechnica/index"),
            ("The Verge",   "https://www.theverge.com/rss/index.xml"),
        ],
        "ai": [
            ("VentureBeat AI",  "https://venturebeat.com/category/ai/feed/"),
            ("MIT Tech Review", "https://www.technologyreview.com/feed/"),
            ("Wired AI",        "https://www.wired.com/feed/category/artificial-intelligence/latest/rss"),
        ],
        "golf": [
            ("Golf.com",      "https://golf.com/feed/"),
            ("Golf Digest",   "https://www.golfdigest.com/rss/all"),
            ("PGA Tour News", "https://www.pgatour.com/news/rss.xml"),
        ],
    }

    # Reuse keyword sets from NewsCatalystEngine — no duplication
    _POSITIVE: frozenset = frozenset(NewsCatalystEngine.POSITIVE)
    _NEGATIVE: frozenset = frozenset(NewsCatalystEngine.NEGATIVE)

    # Extra positive/negative words relevant to general news (non-stock)
    _EXTRA_POSITIVE: frozenset = frozenset({
        "wins", "win", "record", "rise", "rises", "gains", "profit",
        "deal", "growth", "expands", "innovation", "leader", "top",
    })
    _EXTRA_NEGATIVE: frozenset = frozenset({
        "crash", "plunge", "layoff", "layoffs", "fraud", "ban", "banned",
        "recall", "loss", "losses", "fine", "fined", "crisis",
    })

    FETCH_TIMEOUT_S: int = 4   # per-source HTTP timeout
    POOL_TIMEOUT_S: int = 5    # total wall-clock budget for all fetches
    CACHE_TTL_S: int = 60      # seconds to cache results before re-fetching

    def __init__(self) -> None:
        self._cache: Optional[List[Dict[str, Any]]] = None
        self._cache_ts: float = 0.0
        self._cache_lock = threading.Lock()

    # ------------------------------------------------------------------ #
    # Original method — untouched                                          #
    # ------------------------------------------------------------------ #
    def fetch_news(self) -> List[Dict[str, Any]]:
        news = []
        for name, url in self.SOURCES.items():
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:5]:
                    news.append({
                        "source": name,
                        "title": entry.get("title", ""),
                        "link": entry.get("link", ""),
                    })
            except Exception:
                continue
        return news

    # ------------------------------------------------------------------ #
    # Private helpers                                                      #
    # ------------------------------------------------------------------ #
    def _infer_sentiment(self, title: str) -> str:
        low = title.lower()
        pos = sum(1 for w in self._POSITIVE | self._EXTRA_POSITIVE if w in low)
        neg = sum(1 for w in self._NEGATIVE | self._EXTRA_NEGATIVE if w in low)
        if pos > neg:
            return "bullish"
        if neg > pos:
            return "bearish"
        return "neutral"

    def _parse_timestamp(self, entry: Any) -> str:
        try:
            t = entry.get("published_parsed") or entry.get("updated_parsed")
            if t:
                return datetime(*t[:6]).isoformat()
        except Exception:
            pass
        return datetime.utcnow().isoformat()

    def _fetch_source(
        self,
        category: str,
        source_name: str,
        url: str,
        limit: int,
    ) -> List[Dict[str, Any]]:
        """Fetch one RSS source. Uses urllib with explicit timeout (thread-safe)."""
        items: List[Dict[str, Any]] = []
        local_seen: set = set()

        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "JARVIS-Dashboard/1.0 (news feed reader)"},
            )
            with urllib.request.urlopen(req, timeout=self.FETCH_TIMEOUT_S) as resp:
                content = resp.read()

            feed = feedparser.parse(content)

            for entry in feed.entries:
                if len(items) >= limit:
                    break

                title = (entry.get("title") or "").strip()
                if not title:
                    continue

                # local per-source dedup
                key = title.lower()[:80]
                if key in local_seen:
                    continue
                local_seen.add(key)

                items.append({
                    "category": category,
                    "title": title,
                    "source": source_name,
                    "timestamp": self._parse_timestamp(entry),
                    "sentiment": self._infer_sentiment(title),
                })

        except Exception:
            # any network/parse error → return empty, never crash
            pass

        return items

    # ------------------------------------------------------------------ #
    # Public dashboard method                                              #
    # ------------------------------------------------------------------ #
    def fetch_categorized(self, max_per_category: int = 5) -> List[Dict[str, Any]]:
        """
        Fetch news from all categorised sources in parallel.
        Returns at most max_per_category items per category, deduplicated globally.
        Total wall-clock time is capped at POOL_TIMEOUT_S seconds.
        Results are cached for CACHE_TTL_S seconds — subsequent calls are <1ms.
        """
        with self._cache_lock:
            if self._cache is not None and (time.monotonic() - self._cache_ts) < self.CACHE_TTL_S:
                return list(self._cache)
        # Per-category item buckets
        buckets: Dict[str, List[Dict[str, Any]]] = {
            cat: [] for cat in self.CATEGORIZED_SOURCES
        }
        # Global title dedup across all categories
        global_seen: set = set()

        # Build all tasks
        tasks: List[Tuple[str, str, str]] = [
            (cat, name, url)
            for cat, sources in self.CATEGORIZED_SOURCES.items()
            for name, url in sources
        ]

        with ThreadPoolExecutor(max_workers=min(len(tasks), 12)) as pool:
            future_map = {
                pool.submit(self._fetch_source, cat, name, url, max_per_category): cat
                for cat, name, url in tasks
            }

            try:
                for future in as_completed(future_map, timeout=self.POOL_TIMEOUT_S):
                    cat = future_map[future]
                    try:
                        items = future.result()
                    except Exception:
                        continue

                    bucket = buckets[cat]
                    for item in items:
                        if len(bucket) >= max_per_category:
                            break
                        key = item["title"].lower()[:80]
                        if key in global_seen:
                            continue
                        global_seen.add(key)
                        bucket.append(item)

            except FuturesTimeout:
                # Time budget exhausted — return whatever arrived in time
                pass

        # Flatten in category order
        result: List[Dict[str, Any]] = []
        for cat in self.CATEGORIZED_SOURCES:
            result.extend(buckets[cat])

        with self._cache_lock:
            self._cache = result
            self._cache_ts = time.monotonic()

        return result
