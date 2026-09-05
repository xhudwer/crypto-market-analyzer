from collections import defaultdict, deque
from threading import RLock

from config import MAX_FLOW_EVENTS


class MarketStore:
    def __init__(self):
        self.lock = RLock()

        self.symbols = []

        self.candles = defaultdict(
            lambda: defaultdict(list)
        )

        self.tickers = {}

        self.oi_history = defaultdict(
            lambda: deque(maxlen=300)
        )

        self.trades = defaultdict(
            lambda: deque(maxlen=MAX_FLOW_EVENTS)
        )

        self.liquidations = defaultdict(
            lambda: deque(maxlen=2000)
        )

        self.last_ws_event = {}
        self.last_error = {}

    def set_symbols(self, symbols):
        with self.lock:
            self.symbols = list(symbols)

    def get_symbols(self):
        with self.lock:
            return list(self.symbols)

    def set_candles(self, symbol, interval, candles):
        with self.lock:
            self.candles[symbol][interval] = list(candles)

    def upsert_candle(self, symbol, interval, candle):
        with self.lock:
            candles = self.candles[symbol][interval]

            if not candles:
                candles.append(candle)
                return

            last = candles[-1]

            if candle["start"] == last["start"]:
                candles[-1] = candle

            elif candle["start"] > last["start"]:
                candles.append(candle)

            else:
                for index, existing in enumerate(candles):
                    if existing["start"] == candle["start"]:
                        candles[index] = candle
                        break

    def set_ticker(self, symbol, data):
        with self.lock:
            current = self.tickers.get(symbol, {})

            current.update(data)

            self.tickers[symbol] = current

            if "openInterest" in current:
                try:
                    self.oi_history[symbol].append({
                        "timestamp": current.get("timestamp"),
                        "open_interest": float(
                            current["openInterest"]
                        ),
                    })
                except (TypeError, ValueError):
                    pass

            self.last_ws_event[symbol] = (
                data.get("timestamp")
            )

    def add_trade(self, symbol, trade):
        with self.lock:
            self.trades[symbol].append(trade)

            self.last_ws_event[symbol] = (
                trade.get("timestamp")
            )

    def add_liquidation(self, symbol, liquidation):
        with self.lock:
            self.liquidations[symbol].append(
                liquidation
            )

            self.last_ws_event[symbol] = (
                liquidation.get("timestamp")
            )

    def snapshot_symbol(self, symbol):
        with self.lock:
            return {
                "symbol": symbol,

                "candles": {
                    interval: list(candles)
                    for interval, candles
                    in self.candles[symbol].items()
                },

                "ticker": dict(
                    self.tickers.get(symbol, {})
                ),

                "oi_history": list(
                    self.oi_history[symbol]
                ),

                "trades": list(
                    self.trades[symbol]
                ),

                "liquidations": list(
                    self.liquidations[symbol]
                ),

                "last_ws_event": (
                    self.last_ws_event.get(symbol)
                ),

                "last_error": (
                    self.last_error.get(symbol)
                ),
            }