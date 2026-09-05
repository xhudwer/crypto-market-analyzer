import os
import time
import threading
import requests
from fastapi import FastAPI

app = FastAPI()

BYBIT_URL = "https://api.bybit.com"

TOP_COINS = 30
CANDLE_LIMIT = 100
MONITOR_INTERVAL = 60


# ============================================================
# BYBIT
# ============================================================

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

    return result[:TOP_COINS]


def get_klines(symbol, interval, limit=CANDLE_LIMIT):
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

    candles.reverse()

    return candles


# ============================================================
# ЗАГРУЗКА РЫНКА
# ============================================================

def load_market_data(coins):
    market_data = []

    for number, coin in enumerate(coins, 1):
        symbol = coin["symbol"]

        try:
            candles_15m = get_klines(symbol, "15")
            candles_1h = get_klines(symbol, "60")
            candles_4h = get_klines(symbol, "240")

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
                f"[{number:02}/{TOP_COINS}] "
                f"{symbol} | "
                f"15m={len(candles_15m)} | "
                f"1h={len(candles_1h)} | "
                f"4h={len(candles_4h)}",
                flush=True
            )

        except Exception as error:
            print(
                f"[{number:02}/{TOP_COINS}] "
                f"{symbol} ERROR: {error}",
                flush=True
            )

    return market_data


# ============================================================
# SWING POINTS
# ============================================================

def find_swing_points(candles, window=3):
    highs = []
    lows = []

    for i in range(window, len(candles) - window):
        current_high = candles[i]["high"]
        current_low = candles[i]["low"]

        left_highs = [
            candles[j]["high"]
            for j in range(i - window, i)
        ]

        right_highs = [
            candles[j]["high"]
            for j in range(i + 1, i + window + 1)
        ]

        left_lows = [
            candles[j]["low"]
            for j in range(i - window, i)
        ]

        right_lows = [
            candles[j]["low"]
            for j in range(i + 1, i + window + 1)
        ]

        if current_high > max(left_highs + right_highs):
            highs.append({
                "index": i,
                "price": current_high
            })

        if current_low < min(left_lows + right_lows):
            lows.append({
                "index": i,
                "price": current_low
            })

    return highs, lows


# ============================================================
# STRUKTURA HH / HL / LH / LL
# ============================================================

def classify_structure(highs, lows):
    high_structure = []
    low_structure = []

    for i in range(1, len(highs)):
        previous = highs[i - 1]["price"]
        current = highs[i]["price"]

        high_structure.append(
            "HH" if current > previous else "LH"
        )

    for i in range(1, len(lows)):
        previous = lows[i - 1]["price"]
        current = lows[i]["price"]

        low_structure.append(
            "HL" if current > previous else "LL"
        )

    return high_structure, low_structure


# ============================================================
# TREND
# ============================================================

def determine_trend(high_structure, low_structure):
    recent_highs = high_structure[-5:]
    recent_lows = low_structure[-5:]

    bullish = (
        recent_highs.count("HH") +
        recent_lows.count("HL")
    )

    bearish = (
        recent_highs.count("LH") +
        recent_lows.count("LL")
    )

    total = bullish + bearish

    if total == 0:
        return "UNKNOWN", 0

    difference = bullish - bearish

    strength = round(
        abs(difference) / total * 100,
        1
    )

    if difference >= 2:
        return "UP", strength

    if difference <= -2:
        return "DOWN", strength

    return "RANGE", strength


# ============================================================
# MOMENTUM
# ============================================================

def calculate_momentum(candles, lookback=10):
    if len(candles) <= lookback:
        return {
            "direction": "UNKNOWN",
            "change_pct": 0
        }

    current = candles[-1]["close"]
    previous = candles[-1 - lookback]["close"]

    if previous == 0:
        return {
            "direction": "UNKNOWN",
            "change_pct": 0
        }

    change_pct = (
        (current - previous) /
        previous
        * 100
    )

    if change_pct > 1:
        direction = "POSITIVE"
    elif change_pct < -1:
        direction = "NEGATIVE"
    else:
        direction = "NEUTRAL"

    return {
        "direction": direction,
        "change_pct": round(change_pct, 2)
    }


# ============================================================
# ATR / VOLATILITY
# ============================================================

def calculate_atr(candles, period=14):
    if len(candles) < period + 1:
        return 0

    true_ranges = []

    for i in range(1, len(candles)):
        high = candles[i]["high"]
        low = candles[i]["low"]
        previous_close = candles[i - 1]["close"]

        true_range = max(
            high - low,
            abs(high - previous_close),
            abs(low - previous_close)
        )

        true_ranges.append(true_range)

    recent = true_ranges[-period:]

    return sum(recent) / len(recent)


def calculate_volatility(candles):
    atr = calculate_atr(candles)

    price = candles[-1]["close"]

    if price == 0:
        return {
            "atr": 0,
            "atr_pct": 0
        }

    atr_pct = atr / price * 100

    return {
        "atr": round(atr, 8),
        "atr_pct": round(atr_pct, 3)
    }


# ============================================================
# VOLUME
# ============================================================

def analyze_volume(candles, period=20):
    if len(candles) < period + 1:
        return {
            "current": 0,
            "average": 0,
            "ratio": 0,
            "state": "UNKNOWN"
        }

    current = candles[-1]["volume"]

    previous = [
        candle["volume"]
        for candle in candles[-period - 1:-1]
    ]

    average = sum(previous) / len(previous)

    if average == 0:
        ratio = 0
    else:
        ratio = current / average

    if ratio >= 2:
        state = "EXTREME"
    elif ratio >= 1.3:
        state = "HIGH"
    elif ratio <= 0.7:
        state = "LOW"
    else:
        state = "NORMAL"

    return {
        "current": round(current, 4),
        "average": round(average, 4),
        "ratio": round(ratio, 2),
        "state": state
    }


# ============================================================
# SUPPORT / RESISTANCE
# ============================================================

def calculate_levels(candles, highs, lows):
    current_price = candles[-1]["close"]

    recent_highs = [
        item["price"]
        for item in highs
        if item["price"] > current_price
    ]

    recent_lows = [
        item["price"]
        for item in lows
        if item["price"] < current_price
    ]

    resistance = (
        min(recent_highs)
        if recent_highs
        else None
    )

    support = (
        max(recent_lows)
        if recent_lows
        else None
    )

    return {
        "support": support,
        "resistance": resistance
    }


# ============================================================
# RANGE POSITION
# ============================================================

def calculate_range_position(candles, lookback=50):
    recent = candles[-lookback:]

    highest = max(
        candle["high"]
        for candle in recent
    )

    lowest = min(
        candle["low"]
        for candle in recent
    )

    current = candles[-1]["close"]

    if highest == lowest:
        position = 50
    else:
        position = (
            (current - lowest) /
            (highest - lowest)
            * 100
        )

    return {
        "high": highest,
        "low": lowest,
        "position_pct": round(position, 1)
    }


# ============================================================
# BREAKOUT
# ============================================================

def detect_breakout(candles, highs, lows):
    current = candles[-1]
    previous = candles[-2]

    recent_high = (
        max(item["price"] for item in highs[-5:])
        if highs
        else None
    )

    recent_low = (
        min(item["price"] for item in lows[-5:])
        if lows
        else None
    )

    breakout = "NONE"

    if recent_high is not None:
        if (
            current["close"] > recent_high
            and previous["close"] <= recent_high
        ):
            breakout = "BREAKOUT_UP"

    if recent_low is not None:
        if (
            current["close"] < recent_low
            and previous["close"] >= recent_low
        ):
            breakout = "BREAKOUT_DOWN"

    return breakout


# ============================================================
# MARKET STATE
# ============================================================

def analyze_market_state(candles):
    if len(candles) < 30:
        return {
            "regime": "UNKNOWN",
            "trend": "UNKNOWN",
            "strength": 0
        }

    highs, lows = find_swing_points(
        candles,
        window=3
    )

    high_structure, low_structure = classify_structure(
        highs,
        lows
    )

    trend, strength = determine_trend(
        high_structure,
        low_structure
    )

    momentum = calculate_momentum(
        candles
    )

    volatility = calculate_volatility(
        candles
    )

    volume = analyze_volume(
        candles
    )

    levels = calculate_levels(
        candles,
        highs,
        lows
    )

    range_data = calculate_range_position(
        candles
    )

    breakout = detect_breakout(
        candles,
        highs,
        lows
    )

    # --------------------------------------------------------
    # Определяем режим рынка
    # --------------------------------------------------------

    if breakout != "NONE":
        regime = breakout

    elif trend == "UP" and momentum["direction"] == "POSITIVE":
        regime = "TREND_UP"

    elif trend == "DOWN" and momentum["direction"] == "NEGATIVE":
        regime = "TREND_DOWN"

    elif trend == "UP" and momentum["direction"] == "NEGATIVE":
        regime = "CORRECTION"

    elif trend == "DOWN" and momentum["direction"] == "POSITIVE":
        regime = "CORRECTION"

    elif trend == "RANGE":
        regime = "RANGE"

    else:
        regime = "TRANSITION"

    return {
        "regime": regime,
        "trend": trend,
        "strength": strength,

        "high_structure": high_structure[-5:],
        "low_structure": low_structure[-5:],

        "momentum": momentum,

        "volatility": volatility,

        "volume": volume,

        "support": levels["support"],
        "resistance": levels["resistance"],

        "range": range_data,

        "breakout": breakout
    }


# ============================================================
# АНАЛИЗ МОНЕТЫ
# ============================================================

def analyze_coin(coin):
    candles = coin["candles"]

    result = {}

    for timeframe in ["15m", "1h", "4h"]:
        result[timeframe] = analyze_market_state(
            candles[timeframe]
        )

    return result


# ============================================================
# MULTI-TIMEFRAME ANALYSIS
# ============================================================

def analyze_multi_timeframe(analysis):
    tf_15m = analysis["15m"]
    tf_1h = analysis["1h"]
    tf_4h = analysis["4h"]

    trends = [
        tf_15m["trend"],
        tf_1h["trend"],
        tf_4h["trend"]
    ]

    up_count = trends.count("UP")
    down_count = trends.count("DOWN")

    # Полное совпадение
    if up_count == 3:
        alignment = "STRONG_LONG_BIAS"

    elif down_count == 3:
        alignment = "STRONG_SHORT_BIAS"

    # Старшие ТФ вверх, младший вниз
    elif (
        tf_4h["trend"] == "UP"
        and tf_1h["trend"] == "UP"
        and tf_15m["trend"] == "DOWN"
    ):
        alignment = "LONG_CORRECTION"

    # Старшие ТФ вниз, младший вверх
    elif (
        tf_4h["trend"] == "DOWN"
        and tf_1h["trend"] == "DOWN"
        and tf_15m["trend"] == "UP"
    ):
        alignment = "SHORT_CORRECTION"

    # Возможный переход
    elif (
        tf_4h["trend"] == "UP"
        and tf_1h["trend"] == "DOWN"
        and tf_15m["trend"] == "DOWN"
    ):
        alignment = "REVERSAL_WATCH_DOWN"

    elif (
        tf_4h["trend"] == "DOWN"
        and tf_1h["trend"] == "UP"
        and tf_15m["trend"] == "UP"
    ):
        alignment = "REVERSAL_WATCH_UP"

    else:
        alignment = "MIXED"

    return alignment


# ============================================================
# ВЫВОД АНАЛИЗА
# ============================================================

def print_detailed_analysis(coin, analysis):
    symbol = coin["symbol"]

    print(
        "\n" + "-" * 80,
        flush=True
    )

    print(
        f"{symbol} | MARKET STATE",
        flush=True
    )

    print(
        "-" * 80,
        flush=True
    )

    for timeframe in ["4h", "1h", "15m"]:
        state = analysis[timeframe]

        momentum = state["momentum"]
        volatility = state["volatility"]
        volume = state["volume"]

        print(
            f"{timeframe:>3} | "
            f"REGIME={state['regime']:18} | "
            f"TREND={state['trend']:5} | "
            f"STRENGTH={state['strength']:5.1f}% | "
            f"MOM={momentum['direction']:8} "
            f"{momentum['change_pct']:+.2f}% | "
            f"VOL={volume['state']:8} "
            f"x{volume['ratio']:.2f}",
            flush=True
        )

        print(
            f"     Structure: "
            f"HH/LH={state['high_structure']} "
            f"HL/LL={state['low_structure']}",
            flush=True
        )

        print(
            f"     Support={state['support']} | "
            f"Resistance={state['resistance']} | "
            f"ATR={volatility['atr_pct']:.3f}% | "
            f"Range position="
            f"{state['range']['position_pct']:.1f}%",
            flush=True
        )

    alignment = analyze_multi_timeframe(
        analysis
    )

    print(
        f"MULTI-TF ALIGNMENT: {alignment}",
        flush=True
    )


# ============================================================
# MARKET MONITOR
# ============================================================

def market_monitor():

    while True:

        try:

            print(
                "\n" + "=" * 80,
                flush=True
            )

            print(
                "BYBIT CRYPTO MARKET ANALYZER",
                flush=True
            )

            print(
                "PRICE + STRUCTURE + MOMENTUM + "
                "VOLUME + VOLATILITY",
                flush=True
            )

            print(
                "=" * 80,
                flush=True
            )

            coins = get_top_30()

            print(
                f"Найдено монет: {len(coins)}",
                flush=True
            )

            market_data = load_market_data(
                coins
            )

            print(
                "\n" + "=" * 80,
                flush=True
            )

            print(
                "DEEP MARKET ANALYSIS",
                flush=True
            )

            print(
                "=" * 80,
                flush=True
            )

            for coin in market_data:

                analysis = analyze_coin(
                    coin
                )

                print_detailed_analysis(
                    coin,
                    analysis
                )

            print(
                "\n" + "=" * 80,
                flush=True
            )

            print(
                "ANALYSIS CYCLE COMPLETE",
                flush=True
            )

            print(
                "=" * 80,
                flush=True
            )

        except Exception as error:

            print(
                f"MONITOR ERROR: {error}",
                flush=True
            )

        time.sleep(
            MONITOR_INTERVAL
        )


# ============================================================
# FASTAPI
# ============================================================

@app.get("/")
def home():
    return {
        "status": "online",
        "service": "Crypto Market Analyzer",
        "exchange": "Bybit",
        "coins": TOP_COINS,
        "timeframes": ["15m", "1h", "4h"]
    }


@app.get("/health")
def health():
    return {
        "status": "ok"
    }


# ============================================================
# STARTUP
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