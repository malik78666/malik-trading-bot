import pandas as pd
from binance.um_futures import UMFutures
from ta.trend import EMAIndicator
from ta.momentum import RSIIndicator
from ta.trend import MACD
import time
import os
from dotenv
import load_dotenv
# ... rest of imports

# --- 1. SECURITY AND TESTNET SETUP ---
# Load environment variables from key.env
load_dotenv(dotenv_path='key.env') 

# Load keys from the environment variables
API_KEY = os.getenv("BINANCE_API_KEY") 
API_SECRET = os.getenv("BINANCE_API_SECRET")

if not API_KEY or not API_SECRET:
    raise ValueError("API_KEY or API_SECRET not found. Ensure 'key.env' is present.")
# ... rest of your script

# CRITICAL: Set the base URL to the Binance Futures TESTNET 
BASE_URL = 'https://testnet.binancefuture.com'
LEVERAGE = 5 # Moved leverage here for easy access in config

# Initialize the client using the Testnet URL and loaded keys
client = UMFutures(key=API_KEY, secret=API_SECRET, base_url=BASE_URL)

# --- 2. CONFIGURATION ---
symbol = "BTCUSDT"
interval = "5m"
limit = 200
POSITION_SIZE = 0.001 # Example size for BTC/USDT
STOP_LOSS_PCT = 0.01  # 1% stop loss
TAKE_PROFIT_PCT = 0.02 # 2% take profit

# --- 3. DATA & SIGNAL FUNCTIONS (Unchanged) ---

def get_klines():
    """Fetches candlestick data and converts columns to numeric types."""
    # print("Fetching klines...") # Reduced print statements for clean loop
    data = client.klines(symbol=symbol, interval=interval, limit=limit)
    df = pd.DataFrame(data, columns=[
        "timestamp","open","high","low","close","volume","close_time",
        "quote_asset_vol","trades","tb_base","tb_quote","ignore"
    ])
    
    numeric_cols = ["open", "high", "low", "close", "volume"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    return df

def trading_signal(df):
    # ... (Your existing logic is robust, keeping it as is) ...
    if len(df) < 50:
        return "NO TRADE - INSUFFICIENT DATA", df["close"].iloc[-1] if not df.empty else None

    # Indicators
    ema_fast = EMAIndicator(df["close"], window=20).ema_indicator()
    ema_slow = EMAIndicator(df["close"], window=50).ema_indicator()
    rsi = RSIIndicator(df["close"], window=14).rsi()
    macd = MACD(df["close"]).macd()

    last_close = df["close"].iloc[-1]
    latest_ema_fast = ema_fast.iloc[-1]
    latest_ema_slow = ema_slow.iloc[-1]
    latest_rsi = rsi.iloc[-1]
    latest_macd = macd.iloc[-1]

    # Long Signal
    if (latest_ema_fast > latest_ema_slow and 
        latest_rsi > 50 and 
        latest_macd > 0):
        return "LONG", last_close

    # Short Signal
    if (latest_ema_fast < latest_ema_slow and 
        latest_rsi < 50 and 
        latest_macd < 0):
        return "SHORT", last_close

    return "NO TRADE", last_close

# --- 4. LIVE TRADING FUNCTIONS (IMPLEMENTED) ---

def set_initial_account_settings():
    """Sets the margin type and leverage for the symbol on Testnet."""
    try:
        # Set margin type to ISOLATED (Recommended)
        client.change_margin_type(symbol=symbol, marginType="ISOLATED")
    except Exception:
        # Pass on error if position/order is already open
        pass

    try:
        client.change_leverage(symbol=symbol, leverage=LEVERAGE)
        print(f"Leverage set to {LEVERAGE}x.")
    except Exception as e:
        print(f"Could not set leverage: {e}")

def check_position():
    """Queries Binance API to check for an active position."""
    try:
        positions = client.get_position_risk(symbol=symbol)
        # positionAmt is the current position size. 0 means no position.
        position_amount = float(positions[0]['positionAmt'])
        
        if abs(position_amount) > 0:
            return True # Position is active
        return False
    except Exception as e:
        print(f"Error checking position risk: {e}")
        return False

def cancel_all_open_orders():
    """Cancels all open orders for the trading symbol (crucial cleanup)."""
    try:
        client.cancel_open_orders(symbol=symbol)
        print("🧹 Existing SL/TP orders cancelled.")
    except Exception as e:
        # This often fails if no orders exist, which is fine
        if "No orders found" not in str(e):
             print(f"Error cancelling orders: {e}")

def place_order(signal, price):
    """Opens a position and sets simultaneous SL/TP orders."""
    
    side = "BUY" if signal == "LONG" else "SELL"
    is_long = side == "BUY"
    
    # Calculate SL/TP prices
    # For LONG: SL is lower (1-x), TP is higher (1+x)
    # For SHORT: SL is higher (1+x), TP is lower (1-x)
    sl_price = price * (1 - STOP_LOSS_PCT) if is_long else price * (1 + STOP_LOSS_PCT)
    tp_price = price * (1 + TAKE_PROFIT_PCT) if is_long else price * (1 - TAKE_PROFIT_PCT)
    
    # Round to 2 decimals for BTCUSDT (adjust for other pairs)
    sl_price = round(sl_price, 2)
    tp_price = round(tp_price, 2)
    
    # Determine closure side (Opposite of entry side)
    closure_side = "SELL" if is_long else "BUY"
    
    print(f"--- 🚀 PLACING {signal} ORDER ---")
    print(f"Entry: {price:.2f} | SL: {sl_price:.2f} | TP: {tp_price:.2f}")

    # 1. Place the Market Entry Order
    try:
        entry_order = client.new_order(
            symbol=symbol,
            side=side,
            type="MARKET",
            quantity=POSITION_SIZE
        )
        print(f"✅ ENTRY {side} executed. Order ID: {entry_order['orderId']}")
    except Exception as e:
        print(f"❌ ERROR placing ENTRY order: {e}")
        return

    # 2. Place simultaneous Stop-Loss and Take-Profit orders
    try:
        # Order to close position (Take Profit)
        client.new_order(
            symbol=symbol,
            side=closure_side,
            type="TAKE_PROFIT_MARKET",
            quantity=POSITION_SIZE,
            stopPrice=tp_price,
            closePosition=True
        )
        # Order to close position (Stop Loss)
        client.new_order(
            symbol=symbol,
            side=closure_side,
            type="STOP_MARKET",
            quantity=POSITION_SIZE,
            stopPrice=sl_price,
            closePosition=True
        )
        print(f"🛑💰 SL and TP set.")
    except Exception as e:
        print(f"❌ ERROR placing SL/TP orders: {e}")


# --- 5. MAIN EXECUTION ---

def run_bot():
    """Main loop for the trading bot."""
    print("🤖 Starting Trading Bot on Binance Futures TESTNET...")
    set_initial_account_settings() # Configure leverage and margin
    
    while True:
        current_time = time.strftime("%Y-%m-%d %H:%M:%S")
        
        try:
            df = get_klines()
            signal, price = trading_signal(df)
            position_active = check_position()
            
            print(f"\n[{current_time}] Market Price: {price:.2f} | Signal: {signal} | Position Active: {position_active}")

            # Only enter a trade if there is NO position open
            if not position_active:
                if signal == "LONG":
                    cancel_all_open_orders()
                    place_order(signal="LONG", price=price)
                
                elif signal == "SHORT":
                    cancel_all_open_orders()
                    place_order(signal="SHORT", price=price)
            
            elif position_active:
                print("Position active. SL/TP orders are monitoring the trade...")
            
            else:
                print("Signal is NO TRADE. Waiting for entry conditions...")

            # Wait 10 seconds before the next check
            time.sleep(10)

        except Exception as e:
            print(f"🚨 Critical Error: {e}")
            print("Restarting check in 10 seconds...")
            time.sleep(10)

# Execute the bot
run_bot()
