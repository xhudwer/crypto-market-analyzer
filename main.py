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


def get_klines(symbol, interval, limit=100):
    response = requests.get(
        f"{BYBIT_URL}/v5/market/kline",
        params={
            "category": "linear",
            "symbol": symbol,
            "interval": interval,
            "limit": limit
        },
        timeout=10
    )

    response.raise_for_status()
    data = response.json()

    if data["retCode"] != 0:
        raise Exception(data["retMsg"])

    candles = []

    for candle in data["result"]["list"]:
        candles.append({
            "timestamp": int(candle[0]),
            "open": float(candle[1]),
            "high": float(candle[2]),
            "low": float(candle[3]),
            "close": float(candle[4]),
            "volume": float(candle[5]),
            "turnover": float(candle[6])
        })

    # Bybit возвращает свечи от новых к старым.
    # Для анализа нам удобнее старые → новые.
    candles.reverse()

    return candles


def load_market_data(coins):
    market_data = []

    for number, coin in enumerate(coins, 1):
        symbol = coin["symbol"]

        try:
            candles_15m = get_klines(symbol, "15", 100)
            candles_1h = get_klines(symbol, "60", 100)
            candles_4h = get_klines(symbol, "240", 100)

            market_data.append({
                "symbol": symbol,
                "price": coin["price"],
                "change": coin["change"],
                "turnover": coin["turnover"],
                "candles": {
                    "15m": candles_15m,
                    "1h": candles_1h,
                    "4h": candles_4h
                }
            })

            print(
                f"[{number:02}/30] {symbol} | "
                f"15m={len(candles_15m)} | "
                f"1h={len(candles_1h)} | "
                f"4h={len(candles_4h)}",
                flush=True
            )

        except Exception as error:
            print(
                f"[{number:02}/30] {symbol} ERROR: {error}",
                flush=True
            )

    return market_data


def market_monitor():
    while True:
        try:
            print("\n" + "=" * 70, flush=True)
            print("BYBIT MARKET ANALYZER", flush=True)
            print("Загрузка 30 монет и свечей 15m / 1h / 4h", flush=True)
            print("=" * 70, flush=True)

            coins = get_top_30()

            market_data = load_market_data(coins)

            print("\n" + "-" * 70, flush=True)
            print(
                f"Получено данных: {len(market_data)}/30 монет",
                flush=True
            )
            print("-" * 70, flush=True)

            for coin in market_data:
                print(
                    f"{coin['symbol']:15} "
                    f"Price: {coin['price']} | "
                    f"24h: {coin['change']:+.2f}% | "
                    f"15m: {len(coin['candles']['15m'])} | "
                    f"1h: {len(coin['candles']['1h'])} | "
                    f"4h: {len(coin['candles']['4h'])}",
                    flush=True
                )

            print("=" * 70, flush=True)

        except Exception as error:
            print(f"MONITOR ERROR: {error}", flush=True)

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


@app.on_event("startup")
def startup_event():
    print(">>> STARTUP EVENT WORKS <<<", flush=True)

    thread = threading.Thread(
        target=market_monitor,
        daemon=True
    )

    thread.start()

    print(">>> MARKET MONITOR THREAD STARTED <<<", flush=True)