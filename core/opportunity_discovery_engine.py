import yfinance as yf

class OpportunityDiscoveryEngine:

    def __init__(self):

        self.universe = [
            "NVDA","AAPL","MSFT","AMZN","META","TSLA",
            "GLD","XLE","XLF","XLK",
            "BTC-USD","ETH-USD"
        ]

    def scan(self):

        ideas = []

        for symbol in self.universe:

            try:

                ticker = yf.Ticker(symbol)
                hist = ticker.history(period="6mo")

                price = float(hist["Close"].iloc[-1])
                high = float(hist["Close"].max())

                drawdown=((price-high)/high)*100

                if drawdown < -20:

                    ideas.append({
                        "symbol":symbol,
                        "type":"deep_value",
                        "drawdown_pct":round(drawdown,2)
                    })

                if hist["Close"].iloc[-1] > hist["Close"].iloc[-20]:

                    ideas.append({
                        "symbol":symbol,
                        "type":"momentum"
                    })

            except:
                pass

        return ideas
