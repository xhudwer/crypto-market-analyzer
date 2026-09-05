import threading
import time

from pybit.unified_trading import WebSocket


class BybitWebSocket:

    def __init__(self, store):

        self.store = store

        self._thread = None
        self._stop = threading.Event()

        self._ws = None
        self._symbols = []

        self._started = False

    def start(self, symbols):

        self._symbols = list(symbols)

        if self._started:
            return

        self._started = True

        self._thread = threading.Thread(
            target=self._run,
            name="bybit-ws-supervisor",
            daemon=True,
        )

        self._thread.start()

    def update_symbols(self, symbols):

        symbols = list(symbols)

        if symbols != self._symbols:

            self._symbols = symbols

            self._restart_connection()

    def _restart_connection(self):

        try:

            if self._ws is not None:
                self._ws.exit()

        except Exception:
            pass

    def stop(self):

        self._stop.set()

        self._restart_connection()

    def _run(self):

        while not self._stop.is_set():

            try:

                self._connect_and_subscribe()

                while not self._stop.is_set():

                    time.sleep(2)

                    if self._ws is None:
                        break

            except Exception as exc:

                self.store.last_error = (
                    f"WS: {exc}"
                )

                print(
                    f"[WS ERROR] {exc}",
                    flush=True
                )

                time.sleep(5)

    def _connect_and_subscribe(self):

        print(
            f">>> CONNECTING BYBIT WS: "
            f"{len(self._symbols)} symbols <<<",
            flush=True
        )

        self._ws = WebSocket(
            testnet=False,
            channel_type="linear",
        )

        for symbol in self._symbols:

            # TICKER
            self._ws.ticker_stream(
                symbol=symbol,
                callback=self._on_ticker,
            )

            # KLINE
            for interval in (
                15,
                60,
                240,
            ):

                self._ws.kline_stream(
                    interval=interval,
                    symbol=symbol,
                    callback=self._on_kline,
                )

            # PUBLIC TRADES
            self._ws.public_trade_stream(
                symbol=symbol,
                callback=self._on_trade,
            )

            # LIQUIDATIONS
            self._ws.all_liquidation_stream(
                symbol=symbol,
                callback=self._on_liquidation,
            )

        print(
            ">>> BYBIT WS SUBSCRIPTIONS READY <<<",
            flush=True
        )

    def _on_ticker(self, message):

        data = message.get("data")

        if isinstance(data, list):

            data = (
                data[0]
                if data
                else {}
            )

        if not isinstance(data, dict):
            return

        symbol = data.get("symbol")

        if symbol:

            self.store.set_ticker(
                symbol,
                data
            )

    def _on_kline(self, message):

        data = message.get(
            "data",
            []
        )

        topic = message.get(
            "topic",
            ""
        )

        parts = topic.split(".")

        if len(parts) != 3:
            return

        _, interval, symbol = parts

        timeframe = {
            "15": "15m",
            "60": "1h",
            "240": "4h",
        }.get(interval)

        if not timeframe:
            return

        for item in data:

            candle = {

                "start": int(
                    item["start"]
                ),

                "open": float(
                    item["open"]
                ),

                "high": float(
                    item["high"]
                ),

                "low": float(
                    item["low"]
                ),

                "close": float(
                    item["close"]
                ),

                "volume": float(
                    item.get(
                        "volume",
                        0
                    )
                ),

                "turnover": float(
                    item.get(
                        "turnover",
                        0
                    )
                ),

                "closed": bool(
                    item.get(
                        "confirm",
                        False
                    )
                ),
            }

            self.store.upsert_candle(
                symbol,
                timeframe,
                candle
            )

    def _on_trade(self, message):

        data = message.get(
            "data",
            []
        )

        for item in data:

            symbol = item.get("s")

            if not symbol:
                continue

            self.store.add_trade(
                symbol,
                {
                    "ts": int(
                        item.get(
                            "T",
                            message.get(
                                "ts",
                                0
                            )
                        )
                    ) / 1000,

                    "side": item.get("S"),

                    "price": float(
                        item.get(
                            "p",
                            0
                        )
                    ),

                    "size": float(
                        item.get(
                            "v",
                            0
                        )
                    ),
                }
            )

    def _on_liquidation(
        self,
        message
    ):

        data = message.get(
            "data",
            []
        )

        for item in data:

            symbol = item.get("s")

            if not symbol:
                continue

            self.store.add_liquidation(
                symbol,
                {
                    "ts": int(
                        item.get(
                            "T",
                            message.get(
                                "ts",
                                0
                            )
                        )
                    ) / 1000,

                    "side": item.get("S"),

                    "size": float(
                        item.get(
                            "v",
                            0
                        )
                    ),

                    "price": float(
                        item.get(
                            "p",
                            0
                        )
                    ),
                }
            )