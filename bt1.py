import pandas as pd
from binance.um_futures import UMFutures
from ta.trend import EMAIndicator
from ta.momentum import RSIIndicator
from ta.trend import MACD
import time

API_KEY = "rZKNjMYCp9fET4715CQ3D5LOjrUzyEjCB1Gw8RSXD3qiRBaFmMzkUHbFe9p3BOgN"
API_SECRET = "SDhQluHzs5OlIFurMRO1nUJBgJ11AYBMkcEq7vkkCLMvm2AO2vylk88zf29Q9JdY"

client = UMFutures(key=API_KEY, secret=API_SECRET)

symbol = "BTCUSDT"
interval = "5m"
limit = 200

def get_klines():
    data = client.klines(symbol=symbol, interval=interval, limit=limit)
    df = pd.DataFrame(data, columns=[
        "timestamp","open","high","low","close","volume","close_time",
        "quote_asset_vol","trades","tb_base","tb_quote","ignore"
    ])
    df["close"] = df["close"].astype(float)
    return df

def trading_signal(df):
    # Indicators
    ema_fast = EMAIndicator(df["close"], window=20).ema_indicator()
    ema_slow = EMAIndicator(df["close"], window=50).ema_indicator()
    rsi = RSIIndicator(df["close"], window=14).rsi()
    macd = MACD(df["close"]).macd()

    last_close = df["close"].iloc[-1]

    # Long Signal
    if ema_fast.iloc[-1] > ema_slow.iloc[-1] and rsi.iloc[-1] > 50 and macd.iloc[-1] > 0:
        return "LONG", last_close

    # Short Signal
    if ema_fast.iloc[-1] < ema_slow.iloc[-1] and rsi.iloc[-1] < 50 and macd.iloc[-1] < 0:
        return "SHORT", last_close

    return "NO TRADE", last_close

def run_bot():
    print("Starting Bot...")
    while True:
        try:
            df = get_klines()
            signal, price = trading_signal(df)
            print(f"Signal: {signal} @ {price}")

            # Later we will add:
            # place_long_order(), place_short_order()
            # stop_loss, take_profit, position sizing

            time.sleep(10)

        except Exception as e:
            print("Error:", e)
            time.sleep(10)

run_bot()

