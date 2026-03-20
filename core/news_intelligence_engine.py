import feedparser


class NewsIntelligenceEngine:
    SOURCES = {
        "reuters_world": "http://feeds.reuters.com/Reuters/worldNews",
        "reuters_business": "http://feeds.reuters.com/reuters/businessNews",
    }

    def fetch_news(self):
        news = []

        for name, url in self.SOURCES.items():
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:5]:
                    news.append(
                        {
                            "source": name,
                            "title": entry.get("title", ""),
                            "link": entry.get("link", ""),
                        }
                    )
            except Exception:
                continue

        return news
