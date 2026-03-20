class TickerResolver:
    MAP = {
        "tesla": "TSLA",
        "google": "GOOGL",
        "alphabet": "GOOGL",
        "amazon": "AMZN",
        "apple": "AAPL",
        "nvidia": "NVDA",
        "microsoft": "MSFT",
        "meta": "META",
        "netflix": "NFLX",
        "palantir": "PLTR",
        "amd": "AMD",
        "uber": "UBER",
    }

    def resolve(self, text: str) -> str:
        value = (text or "").strip().lower()
        if value in self.MAP:
            return self.MAP[value]

        for name, ticker in self.MAP.items():
            if name in value:
                return ticker

        return (text or "").strip().upper()