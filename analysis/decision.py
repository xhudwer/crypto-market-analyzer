from config import DECISION_MIN_SCORE


def direction_from_momentum(momentum):
    if momentum in ("STRONG_POSITIVE", "POSITIVE"):
        return "BULLISH"

    if momentum in ("STRONG_NEGATIVE", "NEGATIVE"):
        return "BEARISH"

    return "NEUTRAL"


def calculate_direction_score(
    trend,
    momentum,
    volume_ratio,
    regime,
    conflict_count,
    warning_count,
):
    score = 0

    momentum_direction = direction_from_momentum(momentum)

    # Структура
    if trend == "UP":
        score += 30

    elif trend == "DOWN":
        score -= 30

    # Momentum должен совпадать со структурой
    if trend == "UP":
        if momentum == "STRONG_POSITIVE":
            score += 25
        elif momentum == "POSITIVE":
            score += 15
        elif momentum == "STRONG_NEGATIVE":
            score -= 25
        elif momentum == "NEGATIVE":
            score -= 15

    elif trend == "DOWN":
        if momentum == "STRONG_NEGATIVE":
            score -= 25
        elif momentum == "NEGATIVE":
            score -= 15
        elif momentum == "STRONG_POSITIVE":
            score += 25
        elif momentum == "POSITIVE":
            score += 15

    # Объём
    if volume_ratio is not None:
        if volume_ratio >= 2.0:
            if momentum_direction == "BULLISH":
                score += 15
            elif momentum_direction == "BEARISH":
                score -= 15

        elif volume_ratio >= 1.5:
            if momentum_direction == "BULLISH":
                score += 10
            elif momentum_direction == "BEARISH":
                score -= 10

        elif volume_ratio >= 1.0:
            if momentum_direction == "BULLISH":
                score += 5
            elif momentum_direction == "BEARISH":
                score -= 5

    # Режим
    if regime in (
        "BULLISH_BREAKOUT",
        "BULLISH_TREND",
    ):
        score += 15

    elif regime in (
        "BEARISH_BREAKOUT",
        "BEARISH_TREND",
    ):
        score -= 15

    elif regime == "BULLISH_LATE_IMPULSE":
        score += 5

    elif regime == "BEARISH_LATE_IMPULSE":
        score -= 5

    # Конфликты
    score -= conflict_count * 15

    # Предупреждения
    score -= warning_count * 5

    return max(-100, min(score, 100))


def determine_decision(
    trend,
    momentum,
    volume_ratio,
    range_position,
    regime,
    conflict_count,
    warning_count,
):
    score = calculate_direction_score(
        trend=trend,
        momentum=momentum,
        volume_ratio=volume_ratio,
        regime=regime,
        conflict_count=conflict_count,
        warning_count=warning_count,
    )

    decision = "NO TRADE"

    # LONG
    if (
        score >= DECISION_MIN_SCORE
        and trend == "UP"
        and direction_from_momentum(momentum) == "BULLISH"
        and conflict_count == 0
        and regime not in (
            "BULLISH_LATE_IMPULSE",
            "UNKNOWN",
        )
    ):
        decision = "LONG"

    # SHORT
    elif (
        score <= -DECISION_MIN_SCORE
        and trend == "DOWN"
        and direction_from_momentum(momentum) == "BEARISH"
        and conflict_count == 0
        and regime not in (
            "BEARISH_LATE_IMPULSE",
            "UNKNOWN",
        )
    ):
        decision = "SHORT"

    return {
        "decision": decision,
        "score": score,
        "direction": (
            "BULLISH"
            if score > 0
            else "BEARISH"
            if score < 0
            else "NEUTRAL"
        ),
    }


def build_trade_plan(
    decision,
    price,
    support=None,
    resistance=None,
):
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