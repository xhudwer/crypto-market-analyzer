def find_support_resistance(candles, swing_highs, swing_lows):
    if not candles:
        return {
            "support": None,
            "resistance": None,
            "range_position": None,
            "location": "UNKNOWN",
        }

    current_price = candles[-1]["close"]

    support_candidates = [
        item["price"]
        for item in swing_lows
        if item["price"] < current_price
    ]

    resistance_candidates = [
        item["price"]
        for item in swing_highs
        if item["price"] > current_price
    ]

    support = max(support_candidates) if support_candidates else None
    resistance = min(resistance_candidates) if resistance_candidates else None

    if support is not None and resistance is not None:
        price_range = resistance - support

        if price_range > 0:
            range_position = (
                (current_price - support)
                / price_range
                * 100
            )
        else:
            range_position = None
    else:
        range_position = None

    if range_position is None:
        location = "UNKNOWN"
    elif range_position >= 85:
        location = "RANGE_HIGH"
    elif range_position <= 15:
        location = "RANGE_LOW"
    else:
        location = "RANGE_MIDDLE"

    return {
        "support": support,
        "resistance": resistance,
        "range_position": range_position,
        "location": location,
    }


def distance_to_level(price, level):
    if price is None or level is None or level == 0:
        return None

    return abs(price - level) / level * 100


def analyze_levels(candles, swing_highs, swing_lows):
    if not candles:
        return {
            "support": None,
            "resistance": None,
            "range_position": None,
            "location": "UNKNOWN",
            "distance_to_support_pct": None,
            "distance_to_resistance_pct": None,
        }

    price = candles[-1]["close"]

    levels = find_support_resistance(
        candles,
        swing_highs,
        swing_lows,
    )

    return {
        **levels,
        "distance_to_support_pct": distance_to_level(
            price,
            levels["support"],
        ),
        "distance_to_resistance_pct": distance_to_level(
            price,
            levels["resistance"],
        ),
    }