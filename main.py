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


app = FastAPI()

rest = BybitREST()
store = MarketStore()
ws = None


def analyze_symbol(symbol):
    results = {}

    for timeframe, interval in TIMEFRAMES.items():
        candles = store.candles.get(
            symbol,
            {}
        ).get(interval, [])

        if len(candles) < MIN_CANDLES:
            results[timeframe] = {
                "status": "INSUFFICIENT_DATA",
                "trend": "INSUFFICIENT_DATA",
            }
            continue

        structure = analyze_structure(candles)

        atr_value = atr(candles)
        volume_value = volume_ratio(candles)
        momentum_value = momentum_pct(candles)
        normalized_momentum = atr_normalized_momentum(candles)

        momentum_state = classify_momentum(
            normalized_momentum
        )

        levels = analyze_levels(
            candles,
            structure["swing_highs"],
            structure["swing_lows"],
        )

        regime = determine_regime(
            trend=structure["trend"],
            momentum=momentum_state,
            volatility=(
                "HIGH"
                if atr_value is not None
                and candles[-1]["close"] > 0
                and atr_value / candles[-1]["close"] >= 0.02
                else "NORMAL"
            ),
            range_position=levels["range_position"],
        )

        conflicts = build_conflicts(
            trend=structure["trend"],
            momentum=momentum_state,
            range_position=levels["range_position"],
            volume_ratio=volume_value,
            volatility=(
                "HIGH"
                if atr_value is not None
                and candles[-1]["close"] > 0
                and atr_value / candles[-1]["close"] >= 0.02
                else "NORMAL"
            ),
            regime=regime,
            support=levels["support"],
            resistance=levels["resistance"],
        )

        decision = determine_decision(
            trend=structure["trend"],
            momentum=momentum_state,
            volume_ratio=volume_value,
            range_position=levels["range_position"],
            regime=regime,
            conflict_count=conflicts["conflict_count"],
            warning_count=conflicts["warning_count"],
        )

        results[timeframe] = {
            "status": "OK",
            "price": candles[-1]["close"],
            "trend": structure["trend"],
            "strength": structure["strength"],
            "high_labels": structure["high_labels"],
            "low_labels": structure["low_labels"],
            "atr": atr_value,
            "volume_ratio": volume_value,
            "momentum_pct": momentum_value,
            "momentum_normalized": normalized_momentum,
            "momentum_state": momentum_state,
            "support": levels["support"],
            "resistance": levels["resistance"],
            "range_position": levels["range_position"],
            "location": levels["location"],
            "regime": regime,
            "conflicts": conflicts,
            "decision": decision,
        }

    return results


def load_initial_data():
    global ws

    print(">>> LOADING INITIAL MARKET DATA <<<", flush=True)

    symbols = rest.top_linear_usdt()

    if not symbols:
        print(">>> NO SYMBOLS FOUND <<<", flush=True)
        return

    store.set_symbols(symbols)

    print(
        f">>> SELECTED {len(symbols)} SYMBOLS <<<",
        flush=True,
    )

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

            except Exception as exc:
                print(
                    f"DATA ERROR {symbol} {timeframe}: {exc}",
                    flush=True,
                )

    ws = BybitWebSocket(store)
    ws.update_symbols(symbols)

    print(
        ">>> INITIAL DATA LOADED <<<",
        flush=True,
    )


def market_monitor():
    print(
        ">>> MARKET MONITOR STARTED <<<",
        flush=True,
    )

    try:
        load_initial_data()
    except Exception as exc:
        print(
            f">>> INITIALIZATION ERROR: {exc} <<<",
            flush=True,
        )
        return

    while True:
        try:
            symbols = store.get_symbols()

            print(
                "\n"
                + "=" * 70,
                flush=True,
            )

            print(
                f"MARKET SCAN | SYMBOLS: {len(symbols)}",
                flush=True,
            )

            print(
                "=" * 70,
                flush=True,
            )

            for symbol in symbols:
                try:
                    result = analyze_symbol(symbol)

                    print(
                        f"\n{symbol}",
                        flush=True,
                    )

                    for timeframe in (
                        "4h",
                        "1h",
                        "15m",
                    ):
                        data = result.get(timeframe, {})

                        if data.get("status") != "OK":
                            print(
                                f"{timeframe}: "
                                f"{data.get('status')}",
                                flush=True,
                            )
                            continue

                        print(
                            f"{timeframe}: "
                            f"{data['trend']} | "
                            f"{data['momentum_state']} | "
                            f"{data['regime']} | "
                            f"score={data['decision']['score']} | "
                            f"{data['decision']['decision']}",
                            flush=True,
                        )

                except Exception as exc:
                    print(
                        f"ANALYSIS ERROR {symbol}: {exc}",
                        flush=True,
                    )

        except Exception as exc:
            print(
                f"MONITOR ERROR: {exc}",
                flush=True,
            )

        time.sleep(60)


@app.get("/")
def root():
    return {
        "status": "ok",
        "service": "crypto-market-analyzer",
        "symbols": len(store.get_symbols()),
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "symbols": len(store.get_symbols()),
        "websocket": ws is not None,
    }


@app.get("/market/{symbol}")
def market(symbol: str):
    symbol = symbol.upper()

    if symbol not in store.get_symbols():
        return {
            "error": "symbol_not_found",
            "symbol": symbol,
        }

    return {
        "symbol": symbol,
        "analysis": analyze_symbol(symbol),
    }


@app.on_event("startup")
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