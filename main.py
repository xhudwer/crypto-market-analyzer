import threading
import time

from fastapi import FastAPI

from config import TIMEFRAMES, CANDLE_LIMIT, MIN_CANDLES
from data.bybit_rest import BybitREST
from data.bybit_ws import BybitWebSocket
from storage.state import MarketStore

from analysis.structure import analyze_structure
from analysis.technical import (
    atr,
    volume_ratio,
    momentum_pct,
    atr_normalized_momentum,
    classify_momentum,
)
from analysis.levels import analyze_levels
from analysis.regime import determine_regime
from analysis.conflicts import build_conflicts
from analysis.decision import determine_decision
from analysis.mtf import analyze_mtf
from analysis.setups import detect_setup


app = FastAPI()

rest = BybitREST()
store = MarketStore()
ws = None


# ============================================================
# ANALYSIS
# ============================================================

def analyze_symbol(symbol):

    results = {}

    for timeframe, interval in TIMEFRAMES.items():

        candles = store.candles.get(
            symbol,
            {}
        ).get(interval, [])

        # ----------------------------------------------------
        # CHECK DATA
        # ----------------------------------------------------

        if len(candles) < MIN_CANDLES:

            results[timeframe] = {
                "status": "INSUFFICIENT_DATA",
                "trend": "INSUFFICIENT_DATA",
            }

            continue

        # ----------------------------------------------------
        # MARKET STRUCTURE
        # ----------------------------------------------------

        structure = analyze_structure(
            candles
        )

        # ----------------------------------------------------
        # TECHNICAL DATA
        # ----------------------------------------------------

        atr_value = atr(
            candles
        )

        volume_value = volume_ratio(
            candles
        )

        momentum_value = momentum_pct(
            candles
        )

        normalized_momentum = atr_normalized_momentum(
            candles
        )

        momentum_state = classify_momentum(
            normalized_momentum
        )

        # ----------------------------------------------------
        # SUPPORT / RESISTANCE
        # ----------------------------------------------------

        levels = analyze_levels(
            candles,
            structure["swing_highs"],
            structure["swing_lows"],
        )

        # ----------------------------------------------------
        # VOLATILITY
        # ----------------------------------------------------

        if (
            atr_value is not None
            and candles[-1]["close"] > 0
            and (
                atr_value
                / candles[-1]["close"]
            ) >= 0.02
        ):

            volatility = "HIGH"

        else:

            volatility = "NORMAL"

        # ----------------------------------------------------
        # MARKET REGIME
        # ----------------------------------------------------

        regime = determine_regime(
            trend=structure["trend"],
            momentum=momentum_state,
            volatility=volatility,
            range_position=levels[
                "range_position"
            ],
        )

        # ----------------------------------------------------
        # CONFLICTS
        # ----------------------------------------------------

        conflicts = build_conflicts(
            trend=structure["trend"],
            momentum=momentum_state,
            range_position=levels[
                "range_position"
            ],
            volume_ratio=volume_value,
            volatility=volatility,
            regime=regime,
            support=levels["support"],
            resistance=levels["resistance"],
        )

        # ----------------------------------------------------
        # DECISION
        # ----------------------------------------------------

        decision = determine_decision(
            trend=structure["trend"],
            momentum=momentum_state,
            volume_ratio=volume_value,
            range_position=levels[
                "range_position"
            ],
            regime=regime,
            conflict_count=conflicts[
                "conflict_count"
            ],
            warning_count=conflicts[
                "warning_count"
            ],
        )

        # ----------------------------------------------------
        # SAVE RESULT
        # ----------------------------------------------------

        results[timeframe] = {

            "status": "OK",

            "price": candles[-1][
                "close"
            ],

            "trend": structure[
                "trend"
            ],

            "strength": structure[
                "strength"
            ],

            "high_labels": structure[
                "high_labels"
            ],

            "low_labels": structure[
                "low_labels"
            ],

            "atr": atr_value,

            "volume_ratio": volume_value,

            "momentum_pct": momentum_value,

            "momentum_normalized":
                normalized_momentum,

            "momentum_state":
                momentum_state,

            "support":
                levels["support"],

            "resistance":
                levels["resistance"],

            "range_position":
                levels[
                    "range_position"
                ],

            "location":
                levels["location"],

            "regime":
                regime,

            "volatility":
                volatility,

            "conflicts":
                conflicts,

            "decision":
                decision,
        }

    # ========================================================
    # MULTI-TIMEFRAME ANALYSIS
    # ========================================================

    mtf = analyze_mtf(
        results
    )

    # ========================================================
    # SETUP DETECTION
    # ========================================================

    setup = detect_setup(
        results,
        mtf,
    )

    # ========================================================
    # FINAL RESULT
    # ========================================================

    return {

        "symbol":
            symbol,

        "timeframes":
            results,

        "mtf":
            mtf,

        "setup":
            setup,
    }


# ============================================================
# INITIAL DATA
# ============================================================

def load_initial_data():

    global ws

    print(
        ">>> LOADING INITIAL MARKET DATA <<<",
        flush=True,
    )

    # --------------------------------------------------------
    # SELECT TOP COINS
    # --------------------------------------------------------

    symbols = rest.top_linear_usdt()

    if not symbols:

        print(
            ">>> NO SYMBOLS FOUND <<<",
            flush=True,
        )

        return

    store.set_symbols(
        symbols
    )

    print(
        f">>> SELECTED "
        f"{len(symbols)} SYMBOLS <<<",
        flush=True,
    )

    # --------------------------------------------------------
    # LOAD HISTORICAL CANDLES
    # --------------------------------------------------------

    for symbol in symbols:

        for timeframe, interval in TIMEFRAMES.items():

            try:

                candles = rest.get_klines(
                    symbol,
                    interval,
                    CANDLE_LIMIT,
                )

                store.set_candles(
                    symbol,
                    interval,
                    candles,
                )

                print(
                    f"LOADED "
                    f"{symbol} "
                    f"{timeframe}: "
                    f"{len(candles)} candles",
                    flush=True,
                )

            except Exception as exc:

                print(
                    f"DATA ERROR "
                    f"{symbol} "
                    f"{timeframe}: "
                    f"{exc}",
                    flush=True,
                )

    # --------------------------------------------------------
    # START WEBSOCKET
    # --------------------------------------------------------

    ws = BybitWebSocket(
        store
    )

    ws.update_symbols(
        symbols
    )

    print(
        ">>> INITIAL DATA LOADED <<<",
        flush=True,
    )


# ============================================================
# CONSOLE OUTPUT
# ============================================================

def print_market_analysis(
    symbol,
    result,
):

    print(
        "",
        flush=True,
    )

    print(
        "=" * 70,
        flush=True,
    )

    print(
        symbol,
        flush=True,
    )

    print(
        "=" * 70,
        flush=True,
    )

    # ========================================================
    # MULTI-TIMEFRAME
    # ========================================================

    mtf = result.get(
        "mtf",
        {},
    )

    print(
        "",
        flush=True,
    )

    print(
        "MARKET STRUCTURE",
        flush=True,
    )

    print(
        f"BIAS: "
        f"{mtf.get('bias', 'UNKNOWN')}",
        flush=True,
    )

    print(
        f"STATE: "
        f"{mtf.get('state', 'UNKNOWN')}",
        flush=True,
    )

    print(
        f"MTF SCORE: "
        f"{mtf.get('score', 0)}",
        flush=True,
    )

    print(
        f"REASON: "
        f"{mtf.get('reason', '')}",
        flush=True,
    )

    # ========================================================
    # TIMEFRAMES
    # ========================================================

    print(
        "",
        flush=True,
    )

    print(
        "TIMEFRAMES",
        flush=True,
    )

    for timeframe in (
        "4h",
        "1h",
        "15m",
    ):

        data = result[
            "timeframes"
        ].get(
            timeframe,
            {},
        )

        print(
            "",
            flush=True,
        )

        print(
            f"[{timeframe}]",
            flush=True,
        )

        # ----------------------------------------------------
        # DATA STATUS
        # ----------------------------------------------------

        if data.get(
            "status"
        ) != "OK":

            print(
                f"STATUS: "
                f"{data.get('status')}",
                flush=True,
            )

            continue

        # ----------------------------------------------------
        # BASIC
        # ----------------------------------------------------

        print(
            f"PRICE: "
            f"{data.get('price')}",
            flush=True,
        )

        print(
            f"TREND: "
            f"{data.get('trend')}",
            flush=True,
        )

        print(
            f"STRUCTURE STRENGTH: "
            f"{data.get('strength')}",
            flush=True,
        )

        # ----------------------------------------------------
        # MOMENTUM
        # ----------------------------------------------------

        print(
            f"MOMENTUM: "
            f"{data.get('momentum_state')}",
            flush=True,
        )

        print(
            f"MOMENTUM %: "
            f"{data.get('momentum_pct')}",
            flush=True,
        )

        print(
            f"MOMENTUM / ATR: "
            f"{data.get('momentum_normalized')}",
            flush=True,
        )

        # ----------------------------------------------------
        # VOLUME
        # ----------------------------------------------------

        print(
            f"VOLUME RATIO: "
            f"{data.get('volume_ratio')}",
            flush=True,
        )

        # ----------------------------------------------------
        # LEVELS
        # ----------------------------------------------------

        print(
            f"SUPPORT: "
            f"{data.get('support')}",
            flush=True,
        )

        print(
            f"RESISTANCE: "
            f"{data.get('resistance')}",
            flush=True,
        )

        print(
            f"RANGE POSITION: "
            f"{data.get('range_position')}",
            flush=True,
        )

        print(
            f"LOCATION: "
            f"{data.get('location')}",
            flush=True,
        )

        # ----------------------------------------------------
        # REGIME
        # ----------------------------------------------------

        print(
            f"REGIME: "
            f"{data.get('regime')}",
            flush=True,
        )

        print(
            f"VOLATILITY: "
            f"{data.get('volatility')}",
            flush=True,
        )

        # ----------------------------------------------------
        # CONFLICTS
        # ----------------------------------------------------

        conflicts = data.get(
            "conflicts",
            {},
        )

        conflict_list = conflicts.get(
            "conflicts",
            [],
        )

        warning_list = conflicts.get(
            "warnings",
            [],
        )

        print(
            f"CONFLICT COUNT: "
            f"{len(conflict_list)}",
            flush=True,
        )

        print(
            f"WARNING COUNT: "
            f"{len(warning_list)}",
            flush=True,
        )

        for conflict in conflict_list:

            print(
                f"  CONFLICT: "
                f"{conflict}",
                flush=True,
            )

        for warning in warning_list:

            print(
                f"  WARNING: "
                f"{warning}",
                flush=True,
            )

        # ----------------------------------------------------
        # CURRENT TECHNICAL DECISION
        # ----------------------------------------------------

        technical_decision = data.get(
            "decision",
            {},
        )

        print(
            f"TECHNICAL SCORE: "
            f"{technical_decision.get('score')}",
            flush=True,
        )

        print(
            f"TECHNICAL DECISION: "
            f"{technical_decision.get('decision')}",
            flush=True,
        )

    # ========================================================
    # SETUP
    # ========================================================

    setup = result.get(
        "setup",
        {},
    )

    print(
        "",
        flush=True,
    )

    print(
        "SETUP",
        flush=True,
    )

    print(
        f"TYPE: "
        f"{setup.get('setup', 'NONE')}",
        flush=True,
    )

    print(
        f"QUALITY: "
        f"{setup.get('quality', 'LOW')}",
        flush=True,
    )

    print(
        f"REASON: "
        f"{setup.get('reason', '')}",
        flush=True,
    )

    all_setups = setup.get(
        "all_setups",
        [],
    )

    if all_setups:

        print(
            f"ALL SETUPS: "
            f"{', '.join(all_setups)}",
            flush=True,
        )

    # ========================================================
    # FINAL DECISION
    # ========================================================

    print(
        "",
        flush=True,
    )

    print(
        "FINAL DECISION",
        flush=True,
    )

    # --------------------------------------------------------
    # IMPORTANT:
    # Пока setup engine ещё не подтверждает реальную
    # точку входа. Поэтому LONG/SHORT здесь запрещены.
    # --------------------------------------------------------

    final_decision = "NO TRADE"

    print(
        f"DECISION: "
        f"{final_decision}",
        flush=True,
    )

    print(
        "REASON: "
        "Торговая модель ещё не прошла "
        "полное подтверждение.",
        flush=True,
    )

    # ========================================================
    # WAIT CONDITIONS
    # ========================================================

    print(
        "",
        flush=True,
    )

    print(
        "WAIT CONDITIONS",
        flush=True,
    )

    if setup.get(
        "setup"
    ) == "TREND_LONG":

        print(
            "LONG WATCH:",
            flush=True,
        )

        print(
            "1. Дождаться нормального отката.",
            flush=True,
        )

        print(
            "2. Проверить поддержку.",
            flush=True,
        )

        print(
            "3. Проверить объём.",
            flush=True,
        )

        print(
            "4. Проверить OI.",
            flush=True,
        )

        print(
            "5. Проверить order flow.",
            flush=True,
        )

        print(
            "6. После подтверждения "
            "оценить вход.",
            flush=True,
        )

    elif setup.get(
        "setup"
    ) == "TREND_SHORT":

        print(
            "SHORT WATCH:",
            flush=True,
        )

        print(
            "1. Дождаться нормального отката.",
            flush=True,
        )

        print(
            "2. Проверить сопротивление.",
            flush=True,
        )

        print(
            "3. Проверить объём.",
            flush=True,
        )

        print(
            "4. Проверить OI.",
            flush=True,
        )

        print(
            "5. Проверить order flow.",
            flush=True,
        )

        print(
            "6. После подтверждения "
            "оценить вход.",
            flush=True,
        )

    elif setup.get(
        "setup"
    ) in (
        "PULLBACK_LONG_WATCH",
        "PULLBACK_SHORT_WATCH",
    ):

        print(
            "Ждать завершения коррекции "
            "и подтверждения продолжения тренда.",
            flush=True,
        )

    elif setup.get(
        "setup"
    ) in (
        "REVERSAL_LONG_WATCH",
        "REVERSAL_SHORT_WATCH",
    ):

        print(
            "Ждать подтверждения смены "
            "рыночной структуры.",
            flush=True,
        )

    else:

        print(
            "Подтверждённой модели "
            "для входа нет.",
            flush=True,
        )


# ============================================================
# MARKET MONITOR
# ============================================================

def market_monitor():

    print(
        ">>> MARKET MONITOR STARTED <<<",
        flush=True,
    )

    # --------------------------------------------------------
    # INITIALIZATION
    # --------------------------------------------------------

    try:

        load_initial_data()

    except Exception as exc:

        print(
            f">>> INITIALIZATION ERROR: "
            f"{exc} <<<",
            flush=True,
        )

        return

    # --------------------------------------------------------
    # MAIN LOOP
    # --------------------------------------------------------

    while True:

        try:

            symbols = store.get_symbols()

            print(
                "",
                flush=True,
            )

            print(
                "#" * 70,
                flush=True,
            )

            print(
                f"MARKET SCAN | "
                f"SYMBOLS: {len(symbols)}",
                flush=True,
            )

            print(
                "#" * 70,
                flush=True,
            )

            # ------------------------------------------------
            # ANALYZE EVERY SYMBOL
            # ------------------------------------------------

            for symbol in symbols:

                try:

                    result = analyze_symbol(
                        symbol
                    )

                    print_market_analysis(
                        symbol,
                        result,
                    )

                except Exception as exc:

                    print(
                        f"ANALYSIS ERROR "
                        f"{symbol}: "
                        f"{exc}",
                        flush=True,
                    )

        except Exception as exc:

            print(
                f"MONITOR ERROR: "
                f"{exc}",
                flush=True,
            )

        # ----------------------------------------------------
        # WAIT
        # ----------------------------------------------------

        time.sleep(
            60
        )


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root():

    return {

        "status":
            "ok",

        "service":
            "crypto-market-analyzer",

        "symbols":
            len(
                store.get_symbols()
            ),
    }


# ============================================================
# HEALTH
# ============================================================

@app.get("/health")
def health():

    return {

        "status":
            "ok",

        "symbols":
            len(
                store.get_symbols()
            ),

        "websocket":
            ws is not None,
    }


# ============================================================
# MARKET API
# ============================================================

@app.get(
    "/market/{symbol}"
)
def market(
    symbol: str
):

    symbol = symbol.upper()

    if symbol not in store.get_symbols():

        return {

            "error":
                "symbol_not_found",

            "symbol":
                symbol,
        }

    return analyze_symbol(
        symbol
    )


# ============================================================
# STARTUP
# ============================================================

@app.on_event(
    "startup"
)
def startup_event():

    print(
        ">>> STARTUP EVENT WORKS <<<",
        flush=True,
    )

    thread = threading.Thread(
        target=market_monitor,
        daemon=True,
    )

    thread.start()

    print(
        ">>> MARKET MONITOR THREAD STARTED <<<",
        flush=True,
    )