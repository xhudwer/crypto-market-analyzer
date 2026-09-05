import requests
import time


BASE_URL = "https://api.bybit.com"


def get_top_30():
    url = f"{BASE_URL}/v5/market/tickers"
    
    params = {
        "category": "linear"
    }

    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()

    data = response.json()

    if data["retCode"] != 0:
        raise Exception(data["retMsg"])

    tickers = data["result"]["list"]

    usdt_contracts = []

    for ticker in tickers:
        symbol = ticker["symbol"]

        if not symbol.endswith("USDT"):
            continue

        try:
            turnover = float(ticker["turnover24h"])
            price = float(ticker["lastPrice"])
            change = float(ticker["price24hPcnt"]) * 100
        except (ValueError, TypeError):
            continue

        usdt_contracts.append({
            "symbol": symbol,
            "turnover": turnover,
            "price": price,
            "change": change
        })

    usdt_contracts.sort(
        key=lambda x: x["turnover"],
        reverse=True
    )

    return usdt_contracts[:30]


def main():
    print("=" * 60)
    print("CRYPTO MARKET ANALYZER")
    print("Bybit — TOP 30 USDT Perpetual")
    print("=" * 60)

    while True:
        try:
            coins = get_top_30()

            print("\nTOP 30:\n")

            for i, coin in enumerate(coins, 1):
                print(
                    f"{i:2}. "
                    f"{coin['symbol']:15} "
                    f"${coin['turnover']:,.0f} "
                    f"{coin['change']:+.2f}%"
                )

            print("\nОбновление через 60 секунд...")

        except Exception as error:
            print(f"\nОшибка: {error}")

        time.sleep(60)


if __name__ == "__main__":
    main()