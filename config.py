import os

BYBIT_TESTNET = os.getenv("BYBIT_TESTNET", "false").lower() == "true"

BYBIT_REST_URL = (
    "https://api-testnet.bybit.com"
    if BYBIT_TESTNET
    else "https://api.bybit.com"
)

TOP_COINS = int(os.getenv("TOP_COINS", "30"))
CANDLE_LIMIT = int(os.getenv("CANDLE_LIMIT", "200"))
MIN_CANDLES = int(os.getenv("MIN_CANDLES", "80"))

MONITOR_SECONDS = int(os.getenv("MONITOR_SECONDS", "60"))
SYMBOL_REFRESH_SECONDS = int(
    os.getenv("SYMBOL_REFRESH_SECONDS", "600")
)

TIMEFRAMES = {
    "15m": "15",
    "1h": "60",
    "4h": "240",
}

SWING_WINDOW = int(
    os.getenv("SWING_WINDOW", "3")
)

ATR_PERIOD = int(
    os.getenv("ATR_PERIOD", "14")
)

VOLUME_PERIOD = int(
    os.getenv("VOLUME_PERIOD", "20")
)

FLOW_WINDOW_SECONDS = int(
    os.getenv("FLOW_WINDOW_SECONDS", "300")
)

OI_WINDOW_SECONDS = int(
    os.getenv("OI_WINDOW_SECONDS", "300")
)

MAX_FLOW_EVENTS = int(
    os.getenv("MAX_FLOW_EVENTS", "5000")
)

DECISION_MIN_SCORE = int(
    os.getenv("DECISION_MIN_SCORE", "70")
)

MAX_ENTRY_DISTANCE_ATR = float(
    os.getenv("MAX_ENTRY_DISTANCE_ATR", "0.60")
)