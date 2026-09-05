from statistics import mean


def _safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def calculate_average_volume(candles, period=20):
    if len(candles) < period + 1:
        return None

    volumes = []

    for candle in candles[-period - 1:-1]:
        volume = _safe_float(
            candle.get("volume")
        )

        if volume is not None:
            volumes.append(volume)

    if not volumes:
        return None

    return mean(volumes)


def detect_breakout(
    candles,
    resistance=None,
    support=None,
    atr_value=None,
    volume_ratio=None,
):
    """
    Определяет состояние пробоя уровня.

    Возможные состояния:

    NO_BREAKOUT
    BREAKOUT_DEVELOPING
    VALID_BREAKOUT
    BREAKOUT_RETEST
    FAILED_BREAKOUT
    BREAKOUT_EXHAUSTION
    """

    result = {
        "state": "NO_BREAKOUT",
        "direction": None,
        "level": None,
        "distance_atr": None,
        "volume_ratio": volume_ratio,
        "reason": "",
    }

    if len(candles) < 5:
        result["reason"] = (
            "Недостаточно свечей для анализа пробоя."
        )

        return result

    current = candles[-1]
    previous = candles[-2]

    current_close = _safe_float(
        current.get("close")
    )

    current_high = _safe_float(
        current.get("high")
    )

    current_low = _safe_float(
        current.get("low")
    )

    previous_close = _safe_float(
        previous.get("close")
    )

    if (
        current_close is None
        or current_high is None
        or current_low is None
        or previous_close is None
    ):
        result["reason"] = (
            "Некорректные данные свечи."
        )

        return result

    # ========================================================
    # ATR
    # ========================================================

    atr_value = _safe_float(
        atr_value
    )

    # ========================================================
    # BREAKOUT ABOVE RESISTANCE
    # ========================================================

    if resistance is not None:

        resistance = _safe_float(
            resistance
        )

        if resistance is not None:

            # ------------------------------------------------
            # Цена уже выше сопротивления
            # ------------------------------------------------

            if current_close > resistance:

                result["direction"] = "UP"
                result["level"] = resistance

                distance = (
                    current_close
                    - resistance
                )

                if (
                    atr_value is not None
                    and atr_value > 0
                ):

                    result[
                        "distance_atr"
                    ] = distance / atr_value

                # --------------------------------------------
                # Проверяем качество пробоя
                # --------------------------------------------

                if (
                    volume_ratio is not None
                    and volume_ratio >= 1.5
                ):

                    result["state"] = (
                        "VALID_BREAKOUT"
                    )

                    result["reason"] = (
                        "Цена закрылась выше "
                        "сопротивления при "
                        "повышенном объёме."
                    )

                else:

                    result["state"] = (
                        "BREAKOUT_DEVELOPING"
                    )

                    result["reason"] = (
                        "Цена находится выше "
                        "сопротивления, но "
                        "подтверждение объёмом "
                        "недостаточное."
                    )

                # --------------------------------------------
                # Слишком сильное удаление от уровня
                # --------------------------------------------

                if (
                    result["distance_atr"]
                    is not None
                    and result["distance_atr"] >= 2.0
                ):

                    result["state"] = (
                        "BREAKOUT_EXHAUSTION"
                    )

                    result["reason"] = (
                        "Цена слишком далеко "
                        "ушла от уровня после пробоя."
                    )

                return result

            # ------------------------------------------------
            # Wick above resistance but close below
            # ------------------------------------------------

            if (
                current_high > resistance
                and current_close <= resistance
            ):

                result["direction"] = "UP"
                result["level"] = resistance

                result["state"] = (
                    "FAILED_BREAKOUT"
                )

                result["reason"] = (
                    "Цена вышла выше сопротивления, "
                    "но закрылась обратно ниже него."
                )

                return result

            # ------------------------------------------------
            # Developing breakout inside candle
            # ------------------------------------------------

            if current_high > resistance:

                result["direction"] = "UP"
                result["level"] = resistance

                result["state"] = (
                    "BREAKOUT_DEVELOPING"
                )

                result["reason"] = (
                    "Цена тестирует сопротивление "
                    "и пытается его пробить."
                )

                return result

    # ========================================================
    # BREAKOUT BELOW SUPPORT
    # ========================================================

    if support is not None:

        support = _safe_float(
            support
        )

        if support is not None:

            # ------------------------------------------------
            # Цена уже ниже поддержки
            # ------------------------------------------------

            if current_close < support:

                result["direction"] = "DOWN"
                result["level"] = support

                distance = (
                    support
                    - current_close
                )

                if (
                    atr_value is not None
                    and atr_value > 0
                ):

                    result[
                        "distance_atr"
                    ] = distance / atr_value

                # --------------------------------------------
                # Качественный пробой
                # --------------------------------------------

                if (
                    volume_ratio is not None
                    and volume_ratio >= 1.5
                ):

                    result["state"] = (
                        "VALID_BREAKOUT"
                    )

                    result["reason"] = (
                        "Цена закрылась ниже "
                        "поддержки при "
                        "повышенном объёме."
                    )

                else:

                    result["state"] = (
                        "BREAKOUT_DEVELOPING"
                    )

                    result["reason"] = (
                        "Цена находится ниже "
                        "поддержки, но "
                        "подтверждение объёмом "
                        "недостаточное."
                    )

                # --------------------------------------------
                # Слишком сильное удаление
                # --------------------------------------------

                if (
                    result["distance_atr"]
                    is not None
                    and result["distance_atr"] >= 2.0
                ):

                    result["state"] = (
                        "BREAKOUT_EXHAUSTION"
                    )

                    result["reason"] = (
                        "Цена слишком далеко "
                        "ушла от уровня после пробоя."
                    )

                return result

            # ------------------------------------------------
            # Wick below support but close above
            # ------------------------------------------------

            if (
                current_low < support
                and current_close >= support
            ):

                result["direction"] = "DOWN"
                result["level"] = support

                result["state"] = (
                    "FAILED_BREAKOUT"
                )

                result["reason"] = (
                    "Цена вышла ниже поддержки, "
                    "но закрылась обратно выше неё."
                )

                return result

            # ------------------------------------------------
            # Testing support
            # ------------------------------------------------

            if current_low < support:

                result["direction"] = "DOWN"
                result["level"] = support

                result["state"] = (
                    "BREAKOUT_DEVELOPING"
                )

                result["reason"] = (
                    "Цена тестирует поддержку "
                    "и пытается её пробить."
                )

                return result

    # ========================================================
    # NO BREAKOUT
    # ========================================================

    result["state"] = "NO_BREAKOUT"

    result["reason"] = (
        "Подтверждённого пробоя уровня нет."
    )

    return result


def detect_retest(
    candles,
    breakout,
    atr_value=None,
):
    """
    Определяет ретест уже пробитого уровня.

    Ретест — это не просто нахождение цены возле уровня.
    Нужно, чтобы ранее был пробой, затем цена вернулась
    к уровню и удержала его.
    """

    result = {
        "state": "NO_RETEST",
        "direction": None,
        "level": None,
        "reason": "",
    }

    if not breakout:
        result["reason"] = (
            "Нет данных о пробое."
        )

        return result

    breakout_state = breakout.get(
        "state"
    )

    direction = breakout.get(
        "direction"
    )

    level = _safe_float(
        breakout.get("level")
    )

    if level is None:
        result["reason"] = (
            "Уровень пробоя неизвестен."
        )

        return result

    if breakout_state not in (
        "VALID_BREAKOUT",
        "BREAKOUT_DEVELOPING",
        "BREAKOUT_EXHAUSTION",
    ):
        result["reason"] = (
            "Нет подтверждённого пробоя "
            "для анализа ретеста."
        )

        return result

    if len(candles) < 3:
        result["reason"] = (
            "Недостаточно свечей "
            "для анализа ретеста."
        )

        return result

    current = candles[-1]
    previous = candles[-2]

    current_close = _safe_float(
        current.get("close")
    )

    current_high = _safe_float(
        current.get("high")
    )

    current_low = _safe_float(
        current.get("low")
    )

    previous_close = _safe_float(
        previous.get("close")
    )

    if None in (
        current_close,
        current_high,
        current_low,
        previous_close,
    ):
        result["reason"] = (
            "Некорректные данные свечей."
        )

        return result

    result["direction"] = direction
    result["level"] = level

    # ========================================================
    # BULLISH RETEST
    # ========================================================

    if direction == "UP":

        touched_level = (
            current_low <= level
        )

        closed_above = (
            current_close > level
        )

        previous_above = (
            previous_close > level
        )

        if (
            touched_level
            and closed_above
            and previous_above
        ):

            result["state"] = (
                "BREAKOUT_RETEST"
            )

            result["reason"] = (
                "Цена вернулась к пробитому "
                "сопротивлению и удержалась выше."
            )

            return result

    # ========================================================
    # BEARISH RETEST
    # ========================================================

    if direction == "DOWN":

        touched_level = (
            current_high >= level
        )

        closed_below = (
            current_close < level
        )

        previous_below = (
            previous_close < level
        )

        if (
            touched_level
            and closed_below
            and previous_below
        ):

            result["state"] = (
                "BREAKOUT_RETEST"
            )

            result["reason"] = (
                "Цена вернулась к пробитой "
                "поддержке и удержалась ниже."
            )

            return result

    result["reason"] = (
        "Возврата к уровню с подтверждением "
        "удержания пока нет."
    )

    return result


def analyze_breakout(
    candles,
    resistance=None,
    support=None,
    atr_value=None,
    volume_ratio=None,
):
    """
    Основная функция breakout engine.
    """

    breakout = detect_breakout(
        candles=candles,
        resistance=resistance,
        support=support,
        atr_value=atr_value,
        volume_ratio=volume_ratio,
    )

    retest = detect_retest(
        candles=candles,
        breakout=breakout,
        atr_value=atr_value,
    )

    # Если есть полноценный ретест,
    # он важнее первоначального состояния.
    if retest["state"] == "BREAKOUT_RETEST":

        state = "BREAKOUT_RETEST"

        reason = retest["reason"]

    else:

        state = breakout["state"]

        reason = breakout["reason"]

    return {
        "state": state,
        "direction": breakout.get(
            "direction"
        ),
        "level": breakout.get(
            "level"
        ),
        "distance_atr": breakout.get(
            "distance_atr"
        ),
        "volume_ratio": volume_ratio,
        "breakout": breakout,
        "retest": retest,
        "reason": reason,
    }