from config import DECISION_MIN_SCORE, MAX_ENTRY_DISTANCE_ATR


def calculate_score(
    trend,
    momentum,
    volume_ratio,
    range_position,
    regime,
    conflict_count,
    warning_count,
):
    score = 0

    # Направление структуры
    if trend == "UP":
        score += 30
    elif trend == "DOWN":
        score += 30

    # Импульс
    if momentum in ("STRONG_POSITIVE", "STRONG_NEGATIVE"):
        score += 20
    elif momentum in ("POSITIVE", "NEGATIVE"):
        score += 10

    # Объём
    if volume_ratio is not None:
        if volume_ratio >= 1.5:
            score += 15
        elif volume_ratio >= 1.0:
            score += 8

    # Режим
    if regime in (
        "BULLISH_BREAKOUT",
        "BEARISH_BREAKOUT",
    ):
        score += 20

    elif regime in (
        "BULLISH_TREND",
        "BEARISH_TREND",
    ):
        score += 15

    elif regime in (
        "BULLISH_LATE_IMPULSE",
        "BEARISH_LATE_IMPULSE",
    ):
        score += 5

    # Конфликты уменьшают качество сигнала
    score -= conflict_count * 15
    score -= warning_count * 5

    return max(0, min(score, 100))


def determine_decision(
    trend,
    momentum,
    volume_ratio,
    range_position,
    regime,
    conflict_count,
    warning_count,
):
    score = calculate_score(
        trend=trend,
        momentum=momentum,
        volume_ratio=volume_ratio,
        range_position=range_position,
        regime=regime,
        conflict_count=conflict_count,
        warning_count=warning_count,
    )

    # По умолчанию сделки нет.
    decision = "NO TRADE"

    # Бычий сценарий
    if trend == "UP":
        if (
            score >= DECISION_MIN_SCORE
            and regime not in (
                "BULLISH_LATE_IMPULSE",
                "UNKNOWN",
            )
            and conflict_count == 0
        ):
            decision = "LONG"

    # Медвежий сценарий
    elif trend == "DOWN":
        if (
            score >= DECISION_MIN_SCORE
            and regime not in (
                "BEARISH_LATE_IMPULSE",
                "UNKNOWN",
            )
            and conflict_count == 0
        ):
            decision = "SHORT"

    return {
        "decision": decision,
        "score": score,
    }


def build_trade_plan(
    decision,
    price,
    support=None,
    resistance=None,
):
    """
    Пока только формирует базовый сценарий.
    SL/TP и размер позиции добавим позже,
    после полноценного модуля управления риском.
    """

    if decision == "NO TRADE":
        return {
            "entry": None,
            "stop_loss": None,
            "take_profit": None,
            "risk_reward": None,
            "reason": "Нет подтверждённой точки входа.",
        }

    if decision == "LONG":
        return {
            "entry": price,
            "stop_loss": support,
            "take_profit": resistance,
            "risk_reward": None,
            "reason": "Бычий сценарий с подтверждённым направлением.",
        }

    if decision == "SHORT":
        return {
            "entry": price,
            "stop_loss": resistance,
            "take_profit": support,
            "risk_reward": None,
            "reason": "Медвежий сценарий с подтверждённым направлением.",
        }

    return {
        "entry": None,
        "stop_loss": None,
        "take_profit": None,
        "risk_reward": None,
        "reason": "Неизвестное решение.",
    }