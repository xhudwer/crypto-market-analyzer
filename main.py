import os
import time
import threading
import requests
from fastapi import FastAPI


# ============================================================
# CONFIG
# ============================================================

BYBIT_URL = "https://api.bybit.com"

TOP_COINS = 30

# Берём больше истории для нормального анализа структуры
CANDLE_LIMIT = 200

# Интервал мониторинга
MONITOR_INTERVAL = 60

# Минимум закрытых свечей для анализа
MIN_CANDLES = 50

# Параметры поиска swing points
SWING_WINDOW = 3

# Таймфреймы
TIMEFRAMES = {
    "15m": "15",
    "1h": "60",
    "4h": "240",
}


# ============================================================
# FASTAPI
# ============================================================

app = FastAPI(
    title="Crypto Market Analyzer",
    version="0.2"
)


# ============================================================
# HTTP SESSION
# ============================================================

session = requests.Session()

session.headers.update({
    "User-Agent": "CryptoMarketAnalyzer/0.2"
})


# ============================================================
# BYBIT API
# ============================================================

def bybit_get(endpoint, params=None):
    """
    Универсальный GET запрос к Bybit.
    """

    url = BYBIT_URL + endpoint

    try:
        response = session.get(
            url,
            params=params,
            timeout=10
        )

        response.raise_for_status()

        data = response.json()

        if data.get("retCode") != 0:
            raise Exception(
                f"Bybit error: {data.get('retCode')} "
                f"{data.get('retMsg')}"
            )

        return data

    except Exception as e:
        print(
            f"BYBIT REQUEST ERROR: {endpoint} | {e}",
            flush=True
        )

        return None


# ============================================================
# TOP COINS
# ============================================================

def get_top_30():

    data = bybit_get(
        "/v5/market/tickers",
        {
            "category": "linear"
        }
    )

    if not data:
        return []

    try:

        tickers = data["result"]["list"]

        coins = []

        for ticker in tickers:

            symbol = ticker.get("symbol", "")

            # Только USDT perpetual
            if not symbol.endswith("USDT"):
                continue

            try:
                turnover = float(
                    ticker.get("turnover24h", 0)
                )
            except:
                turnover = 0

            coins.append({
                "symbol": symbol,
                "turnover": turnover
            })

        coins.sort(
            key=lambda x: x["turnover"],
            reverse=True
        )

        result = [
            x["symbol"]
            for x in coins[:TOP_COINS]
        ]

        return result

    except Exception as e:

        print(
            f"TOP COINS ERROR: {e}",
            flush=True
        )

        return []


# ============================================================
# KLINES
# ============================================================

def get_klines(symbol, interval, limit=CANDLE_LIMIT):

    data = bybit_get(
        "/v5/market/kline",
        {
            "category": "linear",
            "symbol": symbol,
            "interval": interval,
            "limit": limit
        }
    )

    if not data:
        return []

    try:

        rows = data["result"]["list"]

        candles = []

        for row in rows:

            candles.append({
                "timestamp": int(row[0]),
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
                "volume": float(row[5]),
                "turnover": float(row[6])
            })

        # Bybit возвращает от новых к старым.
        # Переворачиваем.
        candles.reverse()

        return candles

    except Exception as e:

        print(
            f"KLINE PARSE ERROR {symbol} {interval}: {e}",
            flush=True
        )

        return []


# ============================================================
# CLOSED CANDLES
# ============================================================

def get_closed_candles(candles):

    """
    Последняя свеча Bybit может быть ещё формирующейся.

    Для анализа и будущего backtest используем только
    полностью закрытые свечи.

    Здесь просто исключаем последнюю свечу.
    """

    if len(candles) <= 1:
        return []

    return candles[:-1]


# ============================================================
# MARKET DATA
# ============================================================

def load_market_data(coins):

    market_data = {}

    for symbol in coins:

        market_data[symbol] = {}

        for tf_name, tf_value in TIMEFRAMES.items():

            candles = get_klines(
                symbol,
                tf_value,
                CANDLE_LIMIT
            )

            closed = get_closed_candles(candles)

            market_data[symbol][tf_name] = closed

            print(
                f"{symbol} {tf_name}: "
                f"{len(closed)} closed candles",
                flush=True
            )

    return market_data


# ============================================================
# BASIC HELPERS
# ============================================================

def safe_div(a, b):

    if b == 0:
        return 0

    return a / b


def percentage_change(old, new):

    if old == 0:
        return 0

    return ((new - old) / old) * 100


# ============================================================
# SWING POINTS
# ============================================================

def find_swing_points(candles, window=SWING_WINDOW):

    highs = []
    lows = []

    if len(candles) < window * 2 + 1:
        return highs, lows

    # Последние window свечей не анализируем как подтверждённые
    # swing points — они ещё могут измениться.
    for i in range(
        window,
        len(candles) - window
    ):

        current = candles[i]

        is_high = True
        is_low = True

        for j in range(
            i - window,
            i + window + 1
        ):

            if j == i:
                continue

            if candles[j]["high"] >= current["high"]:
                is_high = False

            if candles[j]["low"] <= current["low"]:
                is_low = False

        if is_high:

            highs.append({
                "index": i,
                "price": current["high"]
            })

        if is_low:

            lows.append({
                "index": i,
                "price": current["low"]
            })

    return highs, lows


# ============================================================
# ATR
# ============================================================

def calculate_atr(candles, period=14):

    if len(candles) < period + 1:
        return None

    true_ranges = []

    for i in range(1, len(candles)):

        high = candles[i]["high"]
        low = candles[i]["low"]

        previous_close = candles[i - 1]["close"]

        tr = max(
            high - low,
            abs(high - previous_close),
            abs(low - previous_close)
        )

        true_ranges.append(tr)

    if len(true_ranges) < period:
        return None

    return sum(
        true_ranges[-period:]
    ) / period


# ============================================================
# VOLATILITY
# ============================================================

def calculate_volatility(candles):

    atr = calculate_atr(candles)

    if atr is None or not candles:
        return {
            "atr": None,
            "atr_percent": None,
            "state": "UNKNOWN"
        }

    price = candles[-1]["close"]

    atr_percent = safe_div(
        atr,
        price
    ) * 100

    if atr_percent >= 3:
        state = "HIGH"

    elif atr_percent >= 1.5:
        state = "MEDIUM"

    else:
        state = "LOW"

    return {
        "atr": atr,
        "atr_percent": atr_percent,
        "state": state
    }


# ============================================================
# MOMENTUM
# ============================================================

def calculate_momentum(candles, lookback=10):

    if len(candles) < lookback + 1:

        return {
            "percent": 0,
            "normalized": 0,
            "state": "UNKNOWN"
        }

    current = candles[-1]["close"]
    previous = candles[-lookback - 1]["close"]

    change = percentage_change(
        previous,
        current
    )

    atr = calculate_atr(candles)

    if atr is not None:

        movement = abs(
            current - previous
        )

        normalized = safe_div(
            movement,
            atr
        )

        if change < 0:
            normalized *= -1

    else:
        normalized = 0

    if normalized >= 2:
        state = "STRONG_POSITIVE"

    elif normalized >= 0.75:
        state = "POSITIVE"

    elif normalized <= -2:
        state = "STRONG_NEGATIVE"

    elif normalized <= -0.75:
        state = "NEGATIVE"

    else:
        state = "NEUTRAL"

    return {
        "percent": change,
        "normalized": normalized,
        "state": state
    }


# ============================================================
# VOLUME
# ============================================================

def analyze_volume(candles, period=20):

    if len(candles) < period + 1:

        return {
            "ratio": 0,
            "state": "UNKNOWN"
        }

    current_volume = candles[-1]["volume"]

    previous_volumes = [
        c["volume"]
        for c in candles[-period - 1:-1]
    ]

    average_volume = sum(
        previous_volumes
    ) / len(previous_volumes)

    ratio = safe_div(
        current_volume,
        average_volume
    )

    if ratio >= 2:
        state = "VERY_HIGH"

    elif ratio >= 1.3:
        state = "HIGH"

    elif ratio <= 0.7:
        state = "LOW"

    else:
        state = "NORMAL"

    return {
        "ratio": ratio,
        "state": state
    }


# ============================================================
# STRUCTURE
# ============================================================

def analyze_structure(candles):

    highs, lows = find_swing_points(
        candles
    )

    if len(highs) < 2 or len(lows) < 2:

        return {
            "trend": "UNKNOWN",
            "strength": 0,
            "high_structure": [],
            "low_structure": [],
            "swing_highs": highs,
            "swing_lows": lows
        }

    previous_high = highs[-2]["price"]
    current_high = highs[-1]["price"]

    previous_low = lows[-2]["price"]
    current_low = lows[-1]["price"]

    # -----------------------------------------
    # HIGH STRUCTURE
    # -----------------------------------------

    if current_high > previous_high:

        high_state = "HH"

    elif current_high < previous_high:

        high_state = "LH"

    else:

        high_state = "EQ"

    # -----------------------------------------
    # LOW STRUCTURE
    # -----------------------------------------

    if current_low > previous_low:

        low_state = "HL"

    elif current_low < previous_low:

        low_state = "LL"

    else:

        low_state = "EQ"

    # -----------------------------------------
    # STRUCTURE CLASSIFICATION
    # -----------------------------------------

    if high_state == "HH" and low_state == "HL":

        trend = "UP"

    elif high_state == "LH" and low_state == "LL":

        trend = "DOWN"

    else:

        trend = "TRANSITION"

    # -----------------------------------------
    # STRENGTH
    # -----------------------------------------

    atr = calculate_atr(candles)

    if atr:

        high_move = abs(
            current_high - previous_high
        )

        low_move = abs(
            current_low - previous_low
        )

        structural_move = (
            high_move + low_move
        ) / 2

        normalized_strength = safe_div(
            structural_move,
            atr
        )

    else:

        normalized_strength = 0

    if normalized_strength >= 3:
        strength = 100

    elif normalized_strength >= 2:
        strength = 75

    elif normalized_strength >= 1:
        strength = 50

    elif normalized_strength >= 0.5:
        strength = 25

    else:
        strength = 10

    return {
        "trend": trend,
        "strength": strength,

        "high_structure": [
            high_state
        ],

        "low_structure": [
            low_state
        ],

        "swing_highs": highs,
        "swing_lows": lows
    }


# ============================================================
# RANGE
# ============================================================

def calculate_range_position(
    candles,
    period=50
):

    if len(candles) < period:

        return {
            "position": 0,
            "state": "UNKNOWN"
        }

    recent = candles[-period:]

    highest = max(
        c["high"]
        for c in recent
    )

    lowest = min(
        c["low"]
        for c in recent
    )

    current = candles[-1]["close"]

    if highest == lowest:

        return {
            "position": 50,
            "state": "FLAT"
        }

    position = (
        (current - lowest)
        /
        (highest - lowest)
    ) * 100

    if position >= 80:

        state = "RANGE_HIGH"

    elif position <= 20:

        state = "RANGE_LOW"

    else:

        state = "RANGE_MIDDLE"

    return {
        "position": position,
        "state": state
    }


# ============================================================
# SUPPORT / RESISTANCE
# ============================================================

def calculate_levels(candles):

    highs, lows = find_swing_points(
        candles
    )

    current_price = candles[-1]["close"]

    resistance_candidates = [
        x["price"]
        for x in highs
        if x["price"] > current_price
    ]

    support_candidates = [
        x["price"]
        for x in lows
        if x["price"] < current_price
    ]

    resistance = (
        min(resistance_candidates)
        if resistance_candidates
        else None
    )

    support = (
        max(support_candidates)
        if support_candidates
        else None
    )

    return {
        "support": support,
        "resistance": resistance
    }


# ============================================================
# BREAKOUT
# ============================================================

def detect_breakout(candles):

    if len(candles) < 30:

        return {
            "state": "UNKNOWN"
        }

    highs, lows = find_swing_points(
        candles
    )

    if not highs or not lows:

        return {
            "state": "NONE"
        }

    current_close = candles[-1]["close"]

    previous_close = candles[-2]["close"]

    recent_high = highs[-1]["price"]
    recent_low = lows[-1]["price"]

    # Пробой вверх
    if (
        previous_close <= recent_high
        and current_close > recent_high
    ):

        return {
            "state": "BREAKOUT_UP",
            "level": recent_high
        }

    # Пробой вниз
    if (
        previous_close >= recent_low
        and current_close < recent_low
    ):

        return {
            "state": "BREAKOUT_DOWN",
            "level": recent_low
        }

    return {
        "state": "NONE"
    }


# ============================================================
# REGIME
# ============================================================

def determine_regime(
    structure,
    momentum,
    volatility,
    volume,
    breakout
):

    trend = structure["trend"]
    momentum_state = momentum["state"]
    breakout_state = breakout["state"]

    # -----------------------------------------
    # BREAKOUT
    # -----------------------------------------

    if breakout_state == "BREAKOUT_UP":

        return "BREAKOUT_UP"

    if breakout_state == "BREAKOUT_DOWN":

        return "BREAKOUT_DOWN"

    # -----------------------------------------
    # TREND
    # -----------------------------------------

    if trend == "UP":

        if momentum_state in [
            "POSITIVE",
            "STRONG_POSITIVE"
        ]:

            return "TREND_UP"

        if momentum_state in [
            "NEGATIVE",
            "STRONG_NEGATIVE"
        ]:

            return "BULLISH_CORRECTION"

        return "BULLISH_PAUSE"

    if trend == "DOWN":

        if momentum_state in [
            "NEGATIVE",
            "STRONG_NEGATIVE"
        ]:

            return "TREND_DOWN"

        if momentum_state in [
            "POSITIVE",
            "STRONG_POSITIVE"
        ]:

            return "BEARISH_CORRECTION"

        return "BEARISH_PAUSE"

    # -----------------------------------------
    # TRANSITION
    # -----------------------------------------

    if trend == "TRANSITION":

        return "TRANSITION"

    return "UNKNOWN"


# ============================================================
# MARKET STATE
# ============================================================

def analyze_market_state(candles):

    # -----------------------------------------
    # SAFE UNKNOWN STATE
    # -----------------------------------------

    if len(candles) < MIN_CANDLES:

        return {
            "data_quality": {
                "sufficient": False,
                "candles": len(candles),
                "required": MIN_CANDLES
            },

            "price": (
                candles[-1]["close"]
                if candles
                else None
            ),

            "regime": "UNKNOWN",

            "trend": "UNKNOWN",

            "strength": 0,

            "high_structure": [],

            "low_structure": [],

            "momentum": {
                "percent": 0,
                "normalized": 0,
                "state": "UNKNOWN"
            },

            "volatility": {
                "atr": None,
                "atr_percent": None,
                "state": "UNKNOWN"
            },

            "volume": {
                "ratio": 0,
                "state": "UNKNOWN"
            },

            "support": None,

            "resistance": None,

            "range": {
                "position": 0,
                "state": "UNKNOWN"
            },

            "breakout": {
                "state": "UNKNOWN"
            }
        }

    # -----------------------------------------
    # CALCULATIONS
    # -----------------------------------------

    structure = analyze_structure(
        candles
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
        candles
    )

    range_data = calculate_range_position(
        candles
    )

    breakout = detect_breakout(
        candles
    )

    regime = determine_regime(
        structure,
        momentum,
        volatility,
        volume,
        breakout
    )

    return {

        "data_quality": {
            "sufficient": True,
            "candles": len(candles),
            "required": MIN_CANDLES
        },

        "price": candles[-1]["close"],

        "regime": regime,

        "trend": structure["trend"],

        "strength": structure["strength"],

        "high_structure": (
            structure["high_structure"]
        ),

        "low_structure": (
            structure["low_structure"]
        ),

        "momentum": momentum,

        "volatility": volatility,

        "volume": volume,

        "support": levels["support"],

        "resistance": levels["resistance"],

        "range": range_data,

        "breakout": breakout
    }


# ============================================================
# COIN ANALYSIS
# ============================================================

def analyze_coin(symbol, market_data):

    result = {
        "symbol": symbol,
        "timeframes": {}
    }

    for tf in TIMEFRAMES.keys():

        candles = market_data.get(
            symbol,
            {}
        ).get(tf, [])

        result["timeframes"][tf] = (
            analyze_market_state(candles)
        )

    return result


# ============================================================
# MULTI TIMEFRAME
# ============================================================

def analyze_multi_timeframe(
    coin_analysis
):

    tf = coin_analysis["timeframes"]

    state_15m = tf["15m"]
    state_1h = tf["1h"]
    state_4h = tf["4h"]

    # -----------------------------------------
    # DATA CHECK
    # -----------------------------------------

    if not all(
        [
            state_15m["data_quality"]["sufficient"],
            state_1h["data_quality"]["sufficient"],
            state_4h["data_quality"]["sufficient"]
        ]
    ):

        return {
            "state": "INSUFFICIENT_DATA",
            "confidence": 0,
            "reason": "Недостаточно истории на одном или нескольких TF"
        }

    trend_15m = state_15m["trend"]
    trend_1h = state_1h["trend"]
    trend_4h = state_4h["trend"]

    regime_15m = state_15m["regime"]
    regime_1h = state_1h["regime"]
    regime_4h = state_4h["regime"]

    # -----------------------------------------
    # FULL BULLISH ALIGNMENT
    # -----------------------------------------

    if (
        trend_4h == "UP"
        and trend_1h == "UP"
        and trend_15m == "UP"
    ):

        return {
            "state": "ALIGNED_BULLISH",
            "confidence": 85,
            "reason": (
                "4H + 1H + 15M имеют бычью структуру"
            )
        }

    # -----------------------------------------
    # FULL BEARISH ALIGNMENT
    # -----------------------------------------

    if (
        trend_4h == "DOWN"
        and trend_1h == "DOWN"
        and trend_15m == "DOWN"
    ):

        return {
            "state": "ALIGNED_BEARISH",
            "confidence": 85,
            "reason": (
                "4H + 1H + 15M имеют медвежью структуру"
            )
        }

    # -----------------------------------------
    # BULLISH CORRECTION
    # -----------------------------------------

    if (
        trend_4h == "UP"
        and trend_1h == "UP"
        and trend_15m == "DOWN"
    ):

        return {
            "state": "CORRECTION_IN_BULL_TREND",
            "confidence": 70,
            "reason": (
                "Старшие TF бычьи, "
                "15M находится в коррекции"
            )
        }

    # -----------------------------------------
    # BEARISH CORRECTION
    # -----------------------------------------

    if (
        trend_4h == "DOWN"
        and trend_1h == "DOWN"
        and trend_15m == "UP"
    ):

        return {
            "state": "CORRECTION_IN_BEAR_TREND",
            "confidence": 70,
            "reason": (
                "Старшие TF медвежьи, "
                "15M находится в коррекции"
            )
        }

    # -----------------------------------------
    # HIGHER TF CONFLICT
    # -----------------------------------------

    if (
        trend_4h == "UP"
        and trend_1h == "DOWN"
    ):

        return {
            "state": "HIGHER_TF_CONFLICT",
            "confidence": 20,
            "reason": (
                "4H бычий, 1H медвежий — "
                "структурного согласия нет"
            )
        }

    if (
        trend_4h == "DOWN"
        and trend_1h == "UP"
    ):

        return {
            "state": "HIGHER_TF_CONFLICT",
            "confidence": 20,
            "reason": (
                "4H медвежий, 1H бычий — "
                "структурного согласия нет"
            )
        }

    # -----------------------------------------
    # TRANSITION
    # -----------------------------------------

    if (
        trend_4h == "TRANSITION"
        or trend_1h == "TRANSITION"
        or trend_15m == "TRANSITION"
    ):

        return {
            "state": "TRANSITION",
            "confidence": 30,
            "reason": (
                "На одном или нескольких TF "
                "структура находится в переходной фазе"
            )
        }

    # -----------------------------------------
    # MIXED
    # -----------------------------------------

    return {
        "state": "MIXED",
        "confidence": 25,
        "reason": (
            "Таймфреймы не дают согласованной структуры"
        )
    }


# ============================================================
# FORMAT PRICE
# ============================================================

def format_price(price):

    if price is None:
        return "N/A"

    if price >= 1000:
        return f"{price:,.2f}"

    if price >= 1:
        return f"{price:.4f}"

    if price >= 0.01:
        return f"{price:.6f}"

    return f"{price:.8f}"


# ============================================================
# DETAILED OUTPUT
# ============================================================

def print_detailed_analysis(
    symbol,
    analysis
):

    print(
        "\n"
        + "=" * 70,
        flush=True
    )

    print(
        f"{symbol} | MARKET ANALYSIS",
        flush=True
    )

    print(
        "=" * 70,
        flush=True
    )

    for tf in [
        "4h",
        "1h",
        "15m"
    ]:

        state = analysis[
            "timeframes"
        ][tf]

        quality = state[
            "data_quality"
        ]

        print(
            f"\n--- {tf} ---",
            flush=True
        )

        print(
            f"Data: "
            f"{quality['candles']} "
            f"/ required {quality['required']}",
            flush=True
        )

        print(
            f"Price: "
            f"{format_price(state['price'])}",
            flush=True
        )

        print(
            f"Regime: "
            f"{state['regime']}",
            flush=True
        )

        print(
            f"Trend: "
            f"{state['trend']}",
            flush=True
        )

        print(
            f"Strength: "
            f"{state['strength']}",
            flush=True
        )

        print(
            f"Structure High: "
            f"{state['high_structure']}",
            flush=True
        )

        print(
            f"Structure Low: "
            f"{state['low_structure']}",
            flush=True
        )

        momentum = state["momentum"]

        print(
            f"Momentum: "
            f"{momentum['state']} "
            f"({momentum['percent']:.2f}%) "
            f"ATR-normalized: "
            f"{momentum['normalized']:.2f}",
            flush=True
        )

        volatility = state["volatility"]

        if volatility["atr_percent"] is not None:

            print(
                f"Volatility: "
                f"{volatility['state']} "
                f"ATR={volatility['atr_percent']:.2f}%",
                flush=True
            )

        else:

            print(
                "Volatility: UNKNOWN",
                flush=True
            )

        volume = state["volume"]

        print(
            f"Volume: "
            f"{volume['state']} "
            f"ratio={volume['ratio']:.2f}",
            flush=True
        )

        print(
            f"Support: "
            f"{format_price(state['support'])}",
            flush=True
        )

        print(
            f"Resistance: "
            f"{format_price(state['resistance'])}",
            flush=True
        )

        range_data = state["range"]

        if range_data["position"]:

            print(
                f"Range position: "
                f"{range_data['position']:.1f}% "
                f"({range_data['state']})",
                flush=True
            )

        breakout = state["breakout"]

        print(
            f"Breakout: "
            f"{breakout['state']}",
            flush=True
        )

    # -----------------------------------------
    # MULTI TF
    # -----------------------------------------

    mtf = analyze_multi_timeframe(
        analysis
    )

    print(
        "\nMULTI-TIMEFRAME:",
        flush=True
    )

    print(
        f"State: {mtf['state']}",
        flush=True
    )

    print(
        f"Confidence: {mtf['confidence']}%",
        flush=True
    )

    print(
        f"Reason: {mtf['reason']}",
        flush=True
    )


# ============================================================
# MARKET MONITOR
# ============================================================

def market_monitor():

    print(
        "BYBIT CRYPTO MARKET ANALYZER",
        flush=True
    )

    print(
        "PRICE + STRUCTURE + MOMENTUM + "
        "VOLUME + VOLATILITY",
        flush=True
    )

    while True:

        try:

            print(
                "\n"
                + "#" * 70,
                flush=True
            )

            print(
                "NEW MARKET SCAN",
                flush=True
            )

            print(
                "#" * 70,
                flush=True
            )

            # -----------------------------------------
            # TOP COINS
            # -----------------------------------------

            coins = get_top_30()

            if not coins:

                print(
                    "TOP COINS EMPTY",
                    flush=True
                )

                time.sleep(
                    MONITOR_INTERVAL
                )

                continue

            print(
                f"Found {len(coins)} coins",
                flush=True
            )

            # -----------------------------------------
            # MARKET DATA
            # -----------------------------------------

            market_data = load_market_data(
                coins
            )

            # -----------------------------------------
            # ANALYZE
            # -----------------------------------------

            for symbol in coins:

                try:

                    analysis = analyze_coin(
                        symbol,
                        market_data
                    )

                    print_detailed_analysis(
                        symbol,
                        analysis
                    )

                except Exception as coin_error:

                    print(
                        f"COIN ANALYSIS ERROR "
                        f"{symbol}: "
                        f"{coin_error}",
                        flush=True
                    )

                # Небольшая пауза между монетами
                time.sleep(0.05)

        except Exception as e:

            print(
                f"MONITOR ERROR: {e}",
                flush=True
            )

        print(
            f"\nWaiting "
            f"{MONITOR_INTERVAL} seconds...",
            flush=True
        )

        time.sleep(
            MONITOR_INTERVAL
        )


# ============================================================
# FASTAPI STARTUP
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


# ============================================================
# ROUTES
# ============================================================

@app.get("/")
def root():

    return {
        "status": "online",
        "service": "Crypto Market Analyzer",
        "version": "0.2"
    }


@app.get("/health")
def health():

    return {
        "status": "healthy"
    }


# ============================================================
# LOCAL RUN
# ============================================================

if __name__ == "__main__":

    import uvicorn

    port = int(
        os.environ.get(
            "PORT",
            8000
        )
    )

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port
    )