import time
import requests

from config import (
    BYBIT_REST_URL,
    TOP_COINS,
    CANDLE_LIMIT,
)


class BybitREST:

    def __init__(self):
        self.session = requests.Session()

        self.session.headers.update({
            "User-Agent": "crypto-market-analyzer/1.0"
        })

    def _get(self, path, params, attempts=4):

        last_error = None

        for attempt in range(attempts):

            try:
                response = self.session.get(
                    BYBIT_REST_URL + path,
                    params=params,
                    timeout=15,
                )

                response.raise_for_status()

                payload = response.json()

                if payload.get("retCode") != 0:
                    raise RuntimeError(
                        f"Bybit error "
                        f"{payload.get('retCode')}: "
                        f"{payload.get('retMsg')}"
                    )

                return payload["result"]

            except Exception as exc:

                last_error = exc

                time.sleep(
                    1.5 * (attempt + 1)
                )

        raise RuntimeError(
            f"REST request failed: "
            f"{path}: {last_error}"
        )

    def top_linear_usdt(
        self,
        limit=TOP_COINS
    ):

        result = self._get(
            "/v5/market/tickers",
            {
                "category": "linear"
            }
        )

        rows = []

        for item in result.get("list", []):

            symbol = item.get(
                "symbol",
                ""
            )

            if not symbol.endswith("USDT"):
                continue

            if item.get(
                "lastPrice"
            ) in (None, "", "0"):

                continue

            try:

                turnover = float(
                    item.get(
                        "turnover24h",
                        0
                    )
                )

            except Exception:

                turnover = 0

            rows.append(
                (
                    symbol,
                    turnover
                )
            )

        rows.sort(
            key=lambda x: x[1],
            reverse=True
        )

        return [
            symbol
            for symbol, _ in rows[:limit]
        ]

    def get_klines(
        self,
        symbol,
        interval,
        limit=CANDLE_LIMIT
    ):

        result = self._get(
            "/v5/market/kline",
            {
                "category": "linear",
                "symbol": symbol,
                "interval": interval,
                "limit": limit,
            }
        )

        candles = []

        for item in reversed(
            result.get("list", [])
        ):

            candles.append({
                "start": int(item[0]),
                "open": float(item[1]),
                "high": float(item[2]),
                "low": float(item[3]),
                "close": float(item[4]),
                "volume": float(item[5]),
                "turnover": float(item[6]),
                "closed": True,
            })

        return candles

    def get_ticker(
        self,
        symbol
    ):

        result = self._get(
            "/v5/market/tickers",
            {
                "category": "linear",
                "symbol": symbol,
            }
        )

        items = result.get(
            "list",
            []
        )

        if not items:
            return {}

        return items[0]