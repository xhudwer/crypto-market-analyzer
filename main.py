import os
import time
import threading
import requests
from fastapi import FastAPI

app = FastAPI()

BYBIT_URL = "https://api.bybit.com"


def get_top_30():
    response = requests.get(
        f"{BYBIT_URL}/v5/market/tickers",
        params={"category": "linear"},
        timeout=10
    )

    response.raise_for_status()
    data = response.json()

    if data["retCode"] != 0:
        raise Exception(data["retMsg"])

    result = []

    for ticker in data["result"]["list"]:
        symbol = ticker["symbol"]

        if not symbol.endswith("USDT"):
            continue

        try:
            turnover = float(ticker["turnover24h"])
            price = float(ticker["lastPrice"])
            change = float(ticker["price24hPcnt"]) * 100
        except (ValueError, TypeError):
            continue

        result.append({
            "symbol": symbol,
            "price": price,
            "turnover": turnover,
            "change": change
        })

    result.sort(
        key=lambda x: x["turnover"],
        reverse=True
    )

    return result[:30]


def market_monitor():
    while True:
        try:
            coins = get_top_30()

            print("\n" + "=" * 60)
            print("BYBIT MARKET ANALYZER")
            print("=" * 60)

            for number, coin in enumerate(coins, 1):
                print(
                    f"{number:2}. "
                    f"{coin['symbol']:15} "
                    f"Price: {coin['price']} "
                    f"24h: {coin['change']:+.2f}% "
                    f"Volume: ${coin['turnover']:,.0f}"
                )

            print("=" * 60)

        except Exception as error:
            print(f"ERROR: {error}")

        time.sleep(60)


@app.get("/")
def home():
    return {
        "status": "online",
        "service": "Crypto Market Analyzer",
        "exchange": "Bybit"
    }


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    thread = threading.Thread(
        target=market_monitor,
        daemon=True
    )
    thread.start()

    import uvicorn

    port = int(os.environ.get("PORT", 10000))

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port
    )