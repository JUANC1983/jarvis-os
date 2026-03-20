import yfinance as yf


class MacroLiquidityEngine:

    """
    Institutional macro liquidity detector.

    Detects whether global liquidity conditions are:

    - expansion
    - neutral
    - tightening
    - stressed
    """

    def analyze(self):

        data = {}

        try:
            dxy = yf.Ticker("DX-Y.NYB").history(period="5d")["Close"].iloc[-1]
        except:
            dxy = None

        try:
            tlt = yf.Ticker("TLT").history(period="5d")["Close"].iloc[-1]
        except:
            tlt = None

        try:
            vix = yf.Ticker("^VIX").history(period="5d")["Close"].iloc[-1]
        except:
            vix = None

        try:
            oil = yf.Ticker("CL=F").history(period="5d")["Close"].iloc[-1]
        except:
            oil = None

        data["dollar_index"] = dxy
        data["bond_market"] = tlt
        data["volatility"] = vix
        data["oil_price"] = oil

        liquidity_state = "neutral"

        if vix and vix > 25:
            liquidity_state = "tightening"

        if vix and vix > 35:
            liquidity_state = "tightening_or_stressed"

        if dxy and dxy > 105:
            liquidity_state = "tightening"

        if tlt and tlt > 100 and (vix and vix < 18):
            liquidity_state = "supportive"

        return {
            "liquidity_state": liquidity_state,
            "metrics": data,
            "interpretation": self._interpret(liquidity_state),
        }

    def _interpret(self, state):

        if state == "supportive":
            return "Global liquidity conditions appear supportive for risk assets."

        if state == "tightening":
            return "Liquidity conditions tightening. Risk assets may face pressure."

        if state == "tightening_or_stressed":
            return "Liquidity stressed. Volatility regime elevated."

        return "Liquidity conditions neutral."
