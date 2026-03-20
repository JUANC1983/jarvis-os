import requests

class ExternalDataEngine:

    def get_crypto_price(self,symbol="BTC"):

        url=f"https://api.coinbase.com/v2/prices/{symbol}-USD/spot"

        r=requests.get(url).json()

        return r


    def get_macro_indicator(self):

        url="https://api.stlouisfed.org/fred/series/observations"

        return{
        "note":"connect FRED API key later"
        }
