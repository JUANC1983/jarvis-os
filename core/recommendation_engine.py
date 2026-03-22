from core.product_brain import ProductBrain

brain = ProductBrain()

def get_recommendations():

    symbols = ["NVDA", "AAPL", "MSFT", "ASML"]

    results = []

    for s in symbols:
        data = brain._fetch_market_snapshot(s)

        if not data["ok"]:
            continue

        if data["setup_score"] >= 60:
            results.append(data)

    return results
