import yfinance as yf

class GlobalOpportunityRadar:

    def __init__(self):

        self.assets = [
            "NVDA","AAPL","MSFT","AMZN","META",
            "TSLA","XLE","GLD","SLV","BTC-USD",
            "ETH-USD","SPY","QQQ"
        ]

    def scan(self):

        opportunities=[]

        for symbol in self.assets:

            try:

                ticker=yf.Ticker(symbol)

                hist=ticker.history(period="1y")

                if hist.empty:
                    continue

                price=float(hist["Close"].iloc[-1])
                high=float(hist["Close"].max())
                low=float(hist["Close"].min())

                drawdown=((price-high)/high)*100
                rebound=((price-low)/low)*100

                if drawdown<-25:

                    opportunities.append({
                        "symbol":symbol,
                        "type":"deep_value",
                        "drawdown_pct":round(drawdown,2)
                    })

                if rebound>80:

                    opportunities.append({
                        "symbol":symbol,
                        "type":"major_uptrend",
                        "move_pct":round(rebound,2)
                    })

            except:
                pass

        return opportunities
