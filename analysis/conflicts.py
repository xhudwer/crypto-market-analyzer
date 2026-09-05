def build_conflicts(
    trend,
    momentum,
    range_position,
    volume_ratio,
    volatility,
    regime,
    support=None,
    resistance=None,
):
    conflicts = []
    warnings = []

    # 1. Цена слишком близко к сопротивлению
    if (
        trend == "UP"
        and range_position is not None
        and range_position >= 85
    ):
        conflicts.append(
            "Цена находится близко к верхней границе диапазона."
        )

    # 2. Цена слишком близко к поддержке
    if (
        trend == "DOWN"
        and range_position is not None
        and range_position <= 15
    ):
        conflicts.append(
            "Цена находится близко к нижней границе диапазона."
        )

    # 3. Сильный импульс в конце движения
    if regime in (
        "BULLISH_LATE_IMPULSE",
        "BEARISH_LATE_IMPULSE",
    ):
        conflicts.append(
            "Рынок находится в поздней фазе импульса."
        )

    # 4. Сильный импульс без подтверждающего объёма
    if momentum in (
        "STRONG_POSITIVE",
        "STRONG_NEGATIVE",
    ):
        if volume_ratio is not None and volume_ratio < 1.0:
            conflicts.append(
                "Сильное движение происходит без повышенного объёма."
            )

    # 5. Очень высокий объём
    if volume_ratio is not None and volume_ratio >= 2.0:
        warnings.append(
            "Очень высокий объём: возможна кульминация движения."
        )

    # 6. Высокая волатильность
    if volatility == "HIGH":
        warnings.append(
            "Высокая волатильность увеличивает риск резкого движения."
        )

    # 7. Несоответствие направления и импульса
    if trend == "UP" and momentum in (
        "STRONG_NEGATIVE",
        "NEGATIVE",
    ):
        conflicts.append(
            "Бычья структура противоречит текущему медвежьему импульсу."
        )

    if trend == "DOWN" and momentum in (
        "STRONG_POSITIVE",
        "POSITIVE",
    ):
        conflicts.append(
            "Медвежья структура противоречит текущему бычьему импульсу."
        )

    # 8. Неопределённая структура
    if trend == "TRANSITION":
        warnings.append(
            "Структура рынка переходная."
        )

    return {
        "conflicts": conflicts,
        "warnings": warnings,
        "conflict_count": len(conflicts),
        "warning_count": len(warnings),
    }