import pandas as pd

class ChartAnalysisEngine:

    def analyze_dataframe(self,df):

        return{

        "trend":df["Close"].pct_change().mean(),

        "volatility":df["Close"].std()

        }
