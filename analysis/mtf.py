def analyze_mtf(results):
    required = ("4h", "1h", "15m")

    for timeframe in required:
        data = results.get(timeframe)

        if not data:
            return {
                "status": "INSUFFICIENT_DATA",
                "bias": "NEUTRAL",
                "state": "INSUFFICIENT_DATA",
                "score": 0,
                "reason": "Отсутствуют данные одного из таймфреймов.",
            }

        if data.get("status") != "OK":
            return {
                "status": "INSUFFICIENT_DATA",
                "bias": "NEUTRAL",
                "state": "INSUFFICIENT_DATA",
                "score": 0,
                "reason": (
                    f"Недостаточно данных на {timeframe}."
                ),
            }

    tf4h = results["4h"]
    tf1h = results["1h"]
    tf15m = results["15m"]

    trend4h = tf4h["trend"]
    trend1h = tf1h["trend"]
    trend15m = tf15m["trend"]

    score = 0

    # 4H — главный вес
    if trend4h == "UP":
        score += 40
    elif trend4h == "DOWN":
        score -= 40

    # 1H — средний вес
    if trend1h == "UP":
        score += 30
    elif trend1h == "DOWN":
        score -= 30

    # 15M — вес для текущего движения
    if trend15m == "UP":
        score += 30
    elif trend15m == "DOWN":
        score -= 30

    # Определяем общий bias
    if score >= 50:
        bias = "BULLISH"
    elif score <= -50:
        bias = "BEARISH"
    else:
        bias = "NEUTRAL"

    # Полное совпадение всех ТФ
    if (
        trend4h == "UP"
        and trend1h == "UP"
        and trend15m == "UP"
    ):
        state = "ALIGNED_BULLISH"

    elif (
        trend4h == "DOWN"
        and trend1h == "DOWN"
        and trend15m == "DOWN"
    ):
        state = "ALIGNED_BEARISH"

    # Коррекция внутри старшего тренда
    elif (
        trend4h == "UP"
        and trend1h == "UP"
        and trend15m == "DOWN"
    ):
        state = "BULLISH_CORRECTION"

    elif (
        trend4h == "DOWN"
        and trend1h == "DOWN"
        and trend15m == "UP"
    ):
        state = "BEARISH_CORRECTION"

    # Возможная смена структуры
    elif (
        trend4h == "UP"
        and trend1h == "DOWN"
        and trend15m == "DOWN"
    ):
        state = "REVERSAL_WATCH"

    elif (
        trend4h == "DOWN"
        and trend1h == "UP"
        and trend15m == "UP"
    ):
        state = "REVERSAL_WATCH"

    # Переходная структура
    elif (
        trend4h == "TRANSITION"
        or trend1h == "TRANSITION"
        or trend15m == "TRANSITION"
    ):
        state = "TRANSITION"

    else:
        state = "MIXED"

    reasons = []

    if state == "ALIGNED_BULLISH":
        reasons.append(
            "4H, 1H и 15M имеют бычью структуру."
        )

    elif state == "ALIGNED_BEARISH":
        reasons.append(
            "4H, 1H и 15M имеют медвежью структуру."
        )

    elif state == "BULLISH_CORRECTION":
        reasons.append(
            "Старший тренд бычий, но 15M находится "
            "в коррекции."
        )

    elif state == "BEARISH_CORRECTION":
        reasons.append(
            "Старший тренд медвежий, но 15M находится "
            "в коррекции."
        )

    elif state == "REVERSAL_WATCH":
        reasons.append(
            "Средний и младший таймфреймы движутся "
            "против старшего тренда."
        )

    elif state == "TRANSITION":
        reasons.append(
            "Один или несколько таймфреймов находятся "
            "в переходной структуре."
        )

    else:
        reasons.append(
            "Таймфреймы не дают согласованного сигнала."
        )

    return {
        "status": "OK",
        "bias": bias,
        "state": state,
        "score": score,
        "reason": " ".join(reasons),
        "timeframes": {
            "4h": trend4h,
            "1h": trend1h,
            "15m": trend15m,
        },
    }