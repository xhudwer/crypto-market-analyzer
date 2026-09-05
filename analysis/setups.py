def detect_setup(results, mtf):
    if mtf.get("status") != "OK":
        return {
            "setup": "NONE",
            "quality": "LOW",
            "reason": "Недостаточно данных для анализа setup.",
        }

    state = mtf.get("state")
    bias = mtf.get("bias")

    tf4h = results.get("4h", {})
    tf1h = results.get("1h", {})
    tf15m = results.get("15m", {})

    setups = []

    # --------------------------------------------------
    # BULLISH TREND
    # --------------------------------------------------

    if (
        bias == "BULLISH"
        and state == "ALIGNED_BULLISH"
    ):
        setups.append("TREND_LONG")

    # --------------------------------------------------
    # BEARISH TREND
    # --------------------------------------------------

    if (
        bias == "BEARISH"
        and state == "ALIGNED_BEARISH"
    ):
        setups.append("TREND_SHORT")

    # --------------------------------------------------
    # BULLISH CORRECTION
    # --------------------------------------------------

    if state == "BULLISH_CORRECTION":

        setups.append(
            "PULLBACK_LONG_WATCH"
        )

    # --------------------------------------------------
    # BEARISH CORRECTION
    # --------------------------------------------------

    if state == "BEARISH_CORRECTION":

        setups.append(
            "PULLBACK_SHORT_WATCH"
        )

    # --------------------------------------------------
    # REVERSAL WATCH
    # --------------------------------------------------

    if state == "REVERSAL_WATCH":

        if bias == "BULLISH":
            setups.append(
                "REVERSAL_LONG_WATCH"
            )

        elif bias == "BEARISH":
            setups.append(
                "REVERSAL_SHORT_WATCH"
            )

    # --------------------------------------------------
    # LATE IMPULSE FILTER
    # --------------------------------------------------

    if (
        tf15m.get("regime")
        == "BULLISH_LATE_IMPULSE"
    ):

        setups = [
            setup
            for setup in setups
            if setup != "TREND_LONG"
        ]

        setups.append(
            "LATE_LONG"
        )

    if (
        tf15m.get("regime")
        == "BEARISH_LATE_IMPULSE"
    ):

        setups = [
            setup
            for setup in setups
            if setup != "TREND_SHORT"
        ]

        setups.append(
            "LATE_SHORT"
        )

    # --------------------------------------------------
    # CONFLICT FILTER
    # --------------------------------------------------

    total_conflicts = 0

    for timeframe in (
        tf4h,
        tf1h,
        tf15m,
    ):
        conflicts = timeframe.get(
            "conflicts",
            {},
        )

        total_conflicts += conflicts.get(
            "conflict_count",
            0,
        )

    if total_conflicts >= 2:

        return {
            "setup": "NONE",
            "quality": "LOW",
            "reason": (
                "Слишком много конфликтов "
                "между рыночными факторами."
            ),
        }

    # --------------------------------------------------
    # NO SETUP
    # --------------------------------------------------

    if not setups:

        return {
            "setup": "NONE",
            "quality": "LOW",
            "reason": (
                "Подтверждённой торговой "
                "модели сейчас нет."
            ),
        }

    # --------------------------------------------------
    # QUALITY
    # --------------------------------------------------

    primary_setup = setups[0]

    if primary_setup in (
        "TREND_LONG",
        "TREND_SHORT",
    ):

        quality = "MEDIUM"

    elif primary_setup in (
        "PULLBACK_LONG_WATCH",
        "PULLBACK_SHORT_WATCH",
    ):

        quality = "MEDIUM"

    elif primary_setup in (
        "REVERSAL_LONG_WATCH",
        "REVERSAL_SHORT_WATCH",
    ):

        quality = "LOW"

    elif primary_setup in (
        "LATE_LONG",
        "LATE_SHORT",
    ):

        quality = "LOW"

    else:

        quality = "LOW"

    return {
        "setup": primary_setup,
        "quality": quality,
        "all_setups": setups,
        "reason": (
            f"Обнаружен setup: "
            f"{primary_setup}"
        ),
    }