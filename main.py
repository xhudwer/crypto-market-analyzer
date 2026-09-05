import os
import time
import threading
import requests
from fastapi import FastAPI

app = FastAPI()

BYBIT_URL = "https://api.bybit.com"


# ============================================================
# BYBIT — TOP 30 COINS
# ============================================================

def get_top_30():
    response = requests.get(
        f"{BYBIT_URL}/v5/market/tickers",
        params={
            "category": "linear"
        },
        timeout=10
    )

    response.raise_for_status()

    data = response.json()

    if data["retCode"] != 0:
        raise Exception(data["retMsg"])

    result = []

    for ticker in data["result"]["list"]:

        symbol = ticker["symbol"]

        # Только USDT perpetual
        if not symbol.endswith("USDT"):
            continue

        # Исключаем потенциальные невалидные инструменты
        if ticker.get("lastPrice") in ("", None):
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

    # Сортировка по 24h обороту
    result.sort(
        key=lambda x: x["turnover"],
        reverse=True
    )

    return result[:30]


# ============================================================
# BYBIT — CANDLES
# ============================================================

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

    # Bybit отдаёт свечи от новых к старым.
    # Переворачиваем: старые → новые.
    candles.reverse()

    return candles


# ============================================================
# ЗАГРУЗКА ДАННЫХ ПО 30 МОНЕТАМ
# ============================================================

def load_market_data(coins):

    market_data = []

    for number, coin in enumerate(coins, 1):

        symbol = coin["symbol"]

        try:

            candles_15m = get_klines(
                symbol,
                "15",
                100
            )

            candles_1h = get_klines(
                symbol,
                "60",
                100
            )

            candles_4h = get_klines(
                symbol,
                "240",
                100
            )

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
                f"[{number:02}/30] "
                f"{symbol} | "
                f"15m={len(candles_15m)} | "
                f"1h={len(candles_1h)} | "
                f"4h={len(candles_4h)}",
                flush=True
            )

        except Exception as error:

            print(
                f"[{number:02}/30] "
                f"{symbol} ERROR: {error}",
                flush=True
            )

    return market_data


# ============================================================
# ПОИСК SWING HIGH / SWING LOW
# ============================================================

def find_swing_points(candles, window=3):

    highs = []
    lows = []

    for i in range(
        window,
        len(candles) - window
    ):

        current_high = candles[i]["high"]
        current_low = candles[i]["low"]

        left_highs = [
            candles[j]["high"]
            for j in range(
                i - window,
                i
            )
        ]

        right_highs = [
            candles[j]["high"]
            for j in range(
                i + 1,
                i + window + 1
            )
        ]

        left_lows = [
            candles[j]["low"]
            for j in range(
                i - window,
                i
            )
        ]

        right_lows = [
            candles[j]["low"]
            for j in range(
                i + 1,
                i + window + 1
            )
        ]

        # Swing High
        if current_high > max(
            left_highs + right_highs
        ):

            highs.append({
                "index": i,
                "price": current_high
            })

        # Swing Low
        if current_low < min(
            left_lows + right_lows
        ):

            lows.append({
                "index": i,
                "price": current_low
            })

    return highs, lows


# ============================================================
# АНАЛИЗ СТРУКТУРЫ
# ============================================================

def analyze_structure(candles):

    if len(candles) < 20:

        return {
            "trend": "UNKNOWN",
            "strength": 0,
            "structure": []
        }

    highs, lows = find_swing_points(
        candles,
        window=3
    )

    structure = []

    # --------------------------------------------------------
    # Анализ максимумов
    # --------------------------------------------------------

    if len(highs) >= 2:

        for i in range(1, len(highs)):

            previous = highs[i - 1]["price"]
            current = highs[i]["price"]

            if current > previous:

                structure.append("HH")

            else:

                structure.append("LH")

    # --------------------------------------------------------
    # Анализ минимумов
    # --------------------------------------------------------

    if len(lows) >= 2:

        for i in range(1, len(lows)):

            previous = lows[i - 1]["price"]
            current = lows[i]["price"]

            if current > previous:

                structure.append("HL")

            else:

                structure.append("LL")

    # --------------------------------------------------------
    # Если структура не определена
    # --------------------------------------------------------

    if not structure:

        return {
            "trend": "RANGE",
            "strength": 0,
            "structure": []
        }

    # Берём последние элементы структуры
    recent = structure[-8:]

    hh = recent.count("HH")
    hl = recent.count("HL")

    lh = recent.count("LH")
    ll = recent.count("LL")

    bullish_score = hh + hl
    bearish_score = lh + ll

    # --------------------------------------------------------
    # Определение направления
    # --------------------------------------------------------

    if bullish_score >= bearish_score + 2:

        trend = "UP"

    elif bearish_score >= bullish_score + 2:

        trend = "DOWN"

    else:

        trend = "RANGE"

    # --------------------------------------------------------
    # Сила структуры
    # --------------------------------------------------------

    total = max(
        len(recent),
        1
    )

    strength = round(
        abs(
            bullish_score -
            bearish_score
        )
        /
        total
        *
        100,
        1
    )

    return {
        "trend": trend,
        "strength": strength,
        "structure": recent
    }


# ============================================================
# АНАЛИЗ ОДНОЙ МОНЕТЫ
# ============================================================

def analyze_coin(coin):

    candles = coin["candles"]

    result = {}

    for timeframe in [
        "15m",
        "1h",
        "4h"
    ]:

        result[timeframe] = analyze_structure(
            candles[timeframe]
        )

    return result


# ============================================================
# МОНИТОР РЫНКА
# ============================================================

def market_monitor():

    while True:

        try:

            print(
                "\n" + "=" * 70,
                flush=True
            )

            print(
                "BYBIT MARKET ANALYZER",
                flush=True
            )

            print(
                "Загрузка 30 монет "
                "и свечей 15m / 1h / 4h",
                flush=True
            )

            print(
                "=" * 70,
                flush=True
            )

            # ------------------------------------------------
            # TOP 30
            # ------------------------------------------------

            coins = get_top_30()

            print(
                f"Найдено монет: {len(coins)}",
                flush=True
            )

            # ------------------------------------------------
            # СВЕЧИ
            # ------------------------------------------------

            market_data = load_market_data(
                coins
            )

            print(
                "\n" + "-" * 70,
                flush=True
            )

            print(
                f"Получено данных: "
                f"{len(market_data)}/30 монет",
                flush=True
            )

            print(
                "-" * 70,
                flush=True
            )

            # ------------------------------------------------
            # КРАТКИЙ СПИСОК ДАННЫХ
            # ------------------------------------------------

            for coin in market_data:

                print(
                    f"{coin['symbol']:15} "
                    f"Price: {coin['price']} | "
                    f"24h: "
                    f"{coin['change']:+.2f}% | "
                    f"15m: "
                    f"{len(coin['candles']['15m'])} | "
                    f"1h: "
                    f"{len(coin['candles']['1h'])} | "
                    f"4h: "
                    f"{len(coin['candles']['4h'])}",
                    flush=True
                )

            # =================================================
            # АНАЛИЗ СТРУКТУРЫ
            # =================================================

            print(
                "\n" + "=" * 70,
                flush=True
            )

            print(
                "MARKET STRUCTURE",
                flush=True
            )

            print(
                "=" * 70,
                flush=True
            )

            for coin in market_data:

                analysis = analyze_coin(
                    coin
                )

                print(
                    f"{coin['symbol']:15} | "
                    f"15m: "
                    f"{analysis['15m']['trend']:5} "
                    f"({analysis['15m']['strength']:4.1f}%) | "
                    f"1h: "
                    f"{analysis['1h']['trend']:5} "
                    f"({analysis['1h']['strength']:4.1f}%) | "
                    f"4h: "
                    f"{analysis['4h']['trend']:5} "
                    f"({analysis['4h']['strength']:4.1f}%)",
                    flush=True
                )

            print(
                "=" * 70,
                flush=True
            )

        except Exception as error:

            print(
                f"MONITOR ERROR: {error}",
                flush=True
            )

        # =====================================================
        # Следующий цикл через 60 секунд
        # =====================================================

        time.sleep(60)


# ============================================================
# FASTAPI
# ============================================================

@app.get("/")
def home():

    return {
        "status": "online",
        "service": "Crypto Market Analyzer",
        "exchange": "Bybit"
    }


@app.get("/health")
def health():

    return {
        "status": "ok"
    }


# ============================================================
# ЗАПУСК МОНИТОРА ПРИ СТАРТЕ FASTAPI
# ============================================================

@app.on_event("startup")
def startup_event():

    print(
        ">>> STARTUP EVENT WORKS <<<",
        flush=True
    )

    thread = threading.Thread(
        target=market_monitor,
        daemon=True
    )

    thread.start()

    print(
        ">>> MARKET MONITOR THREAD STARTED <<<",
        flush=True
    )