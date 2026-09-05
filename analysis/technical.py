from statistics import mean


def atr(candles, period=14):
    """
    Average True Range.
    Показывает текущую волатильность инструмента.
    """

    if len(candles) < period + 1:
        return None

    true_ranges = []

    for i in range(1, len(candles)):

        current = candles[i]
        previous = candles[i - 1]

        high = current["high"]
        low = current["low"]
        previous_close = previous["close"]

        tr = max(
            high - low,
            abs(high - previous_close),
            abs(low - previous_close),
        )

        true_ranges.append(tr)

    return mean(
        true_ranges[-period:]
    )


def volume_ratio(candles, period=20):
    """
    Текущий объём относительно среднего
    объёма предыдущих закрытых свечей.

    Например:
    1.0x = обычный объём
    2.0x = в два раза выше среднего
    """

    if len(candles) < period + 1:
        return None

    previous_volumes = [
        candle["volume"]
        for candle in candles[
            -period - 1:-1
        ]
    ]

    average_volume = mean(
        previous_volumes
    )

    if average_volume <= 0:
        return None

    return (
        candles[-1]["volume"]
        / average_volume
    )


def momentum_pct(
    candles,
    lookback=5
):
    """
    Процентное изменение цены
    за заданное количество свечей.
    """

    if len(candles) <= lookback:
        return None

    old_price = candles[
        -1 - lookback
    ]["close"]

    current_price = candles[-1]["close"]

    if old_price == 0:
        return None

    return (
        current_price / old_price - 1
    ) * 100


def atr_normalized_momentum(
    candles,
    period=14,
    lookback=5
):
    """
    Momentum, нормализованный через ATR.

    Это важнее обычного процента:
    движение +1% на спокойном рынке
    и +1% на очень волатильном рынке
    имеют разное значение.
    """

    current_atr = atr(
        candles,
        period
    )

    if (
        current_atr is None
        or current_atr <= 0
    ):
        return None

    if len(candles) <= lookback:
        return None

    old_price = candles[
        -1 - lookback
    ]["close"]

    current_price = candles[
        -1
    ]["close"]

    movement = (
        current_price
        - old_price
    )

    return movement / current_atr


def classify_momentum(
    normalized_momentum
):
    """
    Классификация momentum.

    Пороговые значения работают
    относительно ATR, а не абсолютного
    процента движения.
    """

    if normalized_momentum is None:
        return "UNKNOWN"

    if normalized_momentum >= 2:
        return "STRONG_POSITIVE"

    if normalized_momentum >= 0.75:
        return "POSITIVE"

    if normalized_momentum <= -2:
        return "STRONG_NEGATIVE"

    if normalized_momentum <= -0.75:
        return "NEGATIVE"

    return "NEUTRAL"