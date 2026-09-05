from collections import defaultdict, deque
from threading import RLock
import time


class MarketStore:

    def __init__(self, max_flow_events=5000):

        self.lock = RLock()

        # Текущий список инструментов TOP-30
        self.symbols = []

        # Свечи:
        # candles[BTCUSDT]["15m"]
        self.candles = defaultdict(
            lambda: defaultdict(list)
        )

        # Последний ticker по каждому инструменту
        self.tickers = {}

        # История Open Interest
        self.oi_history = defaultdict(
            lambda: deque(maxlen=300)
        )

        # Поток реальных сделок
        self.trades = defaultdict(
            lambda: deque(
                maxlen=max_flow_events
            )
        )

        # Ликвидации
        self.liquidations = defaultdict(
            lambda: deque(maxlen=2000)
        )

        # Время последнего WebSocket-события
        self.last_ws_event = {}

        # Последняя ошибка
        self.last_error = None

    # --------------------------------------------------
    # SYMBOLS
    # --------------------------------------------------

    def set_symbols(self, symbols):

        with self.lock:

            self.symbols = list(symbols)

    # --------------------------------------------------
    # CANDLES
    # --------------------------------------------------

    def set_candles(
        self,
        symbol,
        timeframe,
        candles
    ):

        with self.lock:

            self.candles[symbol][
                timeframe
            ] = list(candles)

    def upsert_candle(
        self,
        symbol,
        timeframe,
        candle
    ):

        with self.lock:

            candles = self.candles[
                symbol
            ][timeframe]

            # Если это обновление
            # уже существующей свечи
            if (
                candles
                and candles[-1]["start"]
                == candle["start"]
            ):

                candles[-1] = candle

            # Если пришла новая свеча
            elif (
                not candles
                or candles[-1]["start"]
                < candle["start"]
            ):

                candles.append(candle)

            # Если сообщение пришло
            # не по порядку
            else:

                for i, old in enumerate(
                    candles
                ):

                    if (
                        old["start"]
                        == candle["start"]
                    ):

                        candles[i] = candle

                        break

            # Не позволяем памяти
            # бесконечно расти
            if len(candles) > 1000:

                del candles[:-1000]

    # --------------------------------------------------
    # TICKER / OI / FUNDING
    # --------------------------------------------------

    def set_ticker(
        self,
        symbol,
        data
    ):

        with self.lock:

            old = self.tickers.get(
                symbol,
                {}
            )

            # Bybit ticker работает
            # через snapshot + delta.
            # Поэтому объединяем старое
            # состояние с новым.
            merged = dict(old)

            merged.update(data)

            self.tickers[
                symbol
            ] = merged

            now = time.time()

            self.last_ws_event[
                symbol
            ] = now

            # OI сохраняем во временной
            # истории для расчёта изменения
            if (
                "openInterest"
                in merged
            ):

                try:

                    oi = float(
                        merged[
                            "openInterest"
                        ]
                    )

                    self.oi_history[
                        symbol
                    ].append(
                        (
                            now,
                            oi
                        )
                    )

                except (
                    TypeError,
                    ValueError
                ):

                    pass

    # --------------------------------------------------
    # PUBLIC TRADES
    # --------------------------------------------------

    def add_trade(
        self,
        symbol,
        event
    ):

        with self.lock:

            self.trades[
                symbol
            ].append(event)

    # --------------------------------------------------
    # LIQUIDATIONS
    # --------------------------------------------------

    def add_liquidation(
        self,
        symbol,
        event
    ):

        with self.lock:

            self.liquidations[
                symbol
            ].append(event)

    # --------------------------------------------------
    # SNAPSHOT
    # --------------------------------------------------

    def snapshot_symbol(
        self,
        symbol
    ):

        with self.lock:

            return {

                "candles": {
                    timeframe: list(
                        self.candles[
                            symbol
                        ][timeframe]
                    )
                    for timeframe
                    in self.candles[
                        symbol
                    ]
                },

                "ticker": dict(
                    self.tickers.get(
                        symbol,
                        {}
                    )
                ),

                "oi_history": list(
                    self.oi_history[
                        symbol
                    ]
                ),

                "trades": list(
                    self.trades[
                        symbol
                    ]
                ),

                "liquidations": list(
                    self.liquidations[
                        symbol
                    ]
                ),

                "last_ws_event":
                    self.last_ws_event.get(
                        symbol
                    ),
            }