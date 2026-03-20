import feedparser


class LiveNewsEngine:
    SOURCES = {
        "reuters_world": "http://feeds.reuters.com/Reuters/worldNews",
        "reuters_business": "http://feeds.reuters.com/reuters/businessNews",
    }

    def fetch(self, limit_per_source: int = 5):
        items = []
        seen = set()

        for source, url in self.SOURCES.items():
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:limit_per_source]:
                    title = entry.get("title", "").strip()
                    link = entry.get("link", "").strip()
                    key = (title.lower(), link)

                    if not title or key in seen:
                        continue

                    seen.add(key)

                    items.append(
                        {
                            "source": source,
                            "title": title,
                            "link": link,
                        }
                    )
            except Exception:
                continue

        return items
