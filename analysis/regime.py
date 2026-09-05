def determine_regime(
    trend,
    momentum,
    volatility,
    range_position,
    breakout_state=None,
):
    """
    Определяет текущий режим рынка.

    Режим и направление — разные вещи.
    Например, рынок может быть BULLISH, но находиться
    в LATE_IMPULSE и быть плохим местом для входа.
    """

    if trend == "INSUFFICIENT_DATA":
        return "UNKNOWN"

    if breakout_state in (
        "VALID_BREAKOUT",
        "BREAKOUT_RETEST",
    ):
        if trend == "UP":
            return "BULLISH_BREAKOUT"

        if trend == "DOWN":
            return "BEARISH_BREAKOUT"

    if trend == "UP":
        if range_position is not None and range_position >= 85:
            if momentum in (
                "STRONG_POSITIVE",
                "POSITIVE",
            ):
                return "BULLISH_LATE_IMPULSE"

        return "BULLISH_TREND"

    if trend == "DOWN":
        if range_position is not None and range_position <= 15:
            if momentum in (
                "STRONG_NEGATIVE",
                "NEGATIVE",
            ):
                return "BEARISH_LATE_IMPULSE"

        return "BEARISH_TREND"

    if trend == "TRANSITION":
        if momentum in (
            "STRONG_POSITIVE",
            "STRONG_NEGATIVE",
        ):
            return "TRANSITION_IMPULSE"

        return "TRANSITION"

    return "UNKNOWN"


def regime_description(regime):
    descriptions = {
        "BULLISH_TREND":
            "Устойчивый бычий тренд.",

        "BEARISH_TREND":
            "Устойчивый медвежий тренд.",

        "BULLISH_LATE_IMPULSE":
            "Бычий тренд, но цена находится в поздней фазе импульса.",

        "BEARISH_LATE_IMPULSE":
            "Медвежий тренд, но цена находится в поздней фазе импульса.",

        "BULLISH_BREAKOUT":
            "Бычий тренд с подтверждённым пробоем.",

        "BEARISH_BREAKOUT":
            "Медвежий тренд с подтверждённым пробоем.",

        "TRANSITION":
            "Рынок находится в переходной фазе.",

        "TRANSITION_IMPULSE":
            "Структура переходная, но появился сильный импульс.",

        "UNKNOWN":
            "Недостаточно данных для определения режима.",
    }

    return descriptions.get(
        regime,
        "Режим не определён.",
    )