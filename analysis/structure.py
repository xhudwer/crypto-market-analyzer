from config import SWING_WINDOW


def is_swing_high(candles, index, window=SWING_WINDOW):
    if index < window or index >= len(candles) - window:
        return False

    current_high = candles[index]["high"]

    for i in range(index - window, index + window + 1):
        if i == index:
            continue

        if candles[i]["high"] >= current_high:
            return False

    return True


def is_swing_low(candles, index, window=SWING_WINDOW):
    if index < window or index >= len(candles) - window:
        return False

    current_low = candles[index]["low"]

    for i in range(index - window, index + window + 1):
        if i == index:
            continue

        if candles[i]["low"] <= current_low:
            return False

    return True


def find_swings(candles, window=SWING_WINDOW):
    """
    Находит только подтверждённые swing high / swing low.

    Последние `window` свечей не используются,
    поскольку для подтверждения swing требуется
    наличие свечей справа.
    """

    highs = []
    lows = []

    if len(candles) < window * 2 + 1:
        return highs, lows

    last_confirmed_index = len(candles) - window - 1

    for index in range(window, last_confirmed_index + 1):

        if is_swing_high(candles, index, window):
            highs.append({
                "index": index,
                "price": candles[index]["high"],
                "time": candles[index]["start"],
            })

        if is_swing_low(candles, index, window):
            lows.append({
                "index": index,
                "price": candles[index]["low"],
                "time": candles[index]["start"],
            })

    return highs, lows


def classify_highs(swings):
    """
    Классификация swing high:

    HH = Higher High
    LH = Lower High
    """

    if len(swings) < 2:
        return []

    result = []

    for i in range(1, len(swings)):
        previous = swings[i - 1]["price"]
        current = swings[i]["price"]

        if current > previous:
            label = "HH"
        else:
            label = "LH"

        result.append({
            **swings[i],
            "label": label,
        })

    return result


def classify_lows(swings):
    """
    Классификация swing low:

    HL = Higher Low
    LL = Lower Low
    """

    if len(swings) < 2:
        return []

    result = []

    for i in range(1, len(swings)):
        previous = swings[i - 1]["price"]
        current = swings[i]["price"]

        if current > previous:
            label = "HL"
        else:
            label = "LL"

        result.append({
            **swings[i],
            "label": label,
        })

    return result


def determine_trend(highs, lows):
    """
    Определяет базовую структуру рынка.

    UP:
        HH + HL

    DOWN:
        LH + LL

    TRANSITION:
        структура смешанная или недостаточно данных.
    """

    if not highs or not lows:
        return "INSUFFICIENT_DATA"

    latest_high = highs[-1]["label"]
    latest_low = lows[-1]["label"]

    if latest_high == "HH" and latest_low == "HL":
        return "UP"

    if latest_high == "LH" and latest_low == "LL":
        return "DOWN"

    return "TRANSITION"


def structure_strength(highs, lows):
    """
    Простая оценка силы структуры.

    Возвращает значение от 0 до 100.

    Это НЕ вероятность движения цены.
    """

    if not highs or not lows:
        return 0

    score = 0

    latest_high = highs[-1]["label"]
    latest_low = lows[-1]["label"]

    if latest_high == "HH":
        score += 50
    elif latest_high == "LH":
        score += 25

    if latest_low == "HL":
        score += 50
    elif latest_low == "LL":
        score += 25

    return min(score, 100)


def analyze_structure(candles):
    """
    Главная функция анализа структуры рынка.
    """

    highs, lows = find_swings(candles)

    classified_highs = classify_highs(highs)
    classified_lows = classify_lows(lows)

    trend = determine_trend(
        classified_highs,
        classified_lows,
    )

    strength = structure_strength(
        classified_highs,
        classified_lows,
    )

    return {
        "trend": trend,
        "strength": strength,
        "swing_highs": classified_highs,
        "swing_lows": classified_lows,
        "high_labels": [
            item["label"]
            for item in classified_highs[-3:]
        ],
        "low_labels": [
            item["label"]
            for item in classified_lows[-3:]
        ],
    }