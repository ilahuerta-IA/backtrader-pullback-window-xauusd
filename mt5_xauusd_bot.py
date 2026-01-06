"""
MT5 XAUUSD Trading Bot - Fixed Risk Version
============================================
Based on Sunrise OGLE strategy with critical fixes:
- Fixed 0.1 lot position sizing (no compounding)
- $100 daily profit target
- $100 daily loss limit
- ATR-based stop loss and take profit
- 4-phase entry system: SCANNING → ARMED → WINDOW_OPEN → ENTRY

Author: Adapted from backtrader-pullback-window-xauusd
Date: January 3, 2026
"""

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import json
from pathlib import Path

# ============================================================
# CONFIGURATION - EDIT THESE PARAMETERS
# ============================================================

class Config:
    """Trading bot configuration"""

    # MT5 CONNECTION (Optional - leave blank to use already logged-in terminal)
    MT5_LOGIN = 10008946929
    MT5_PASSWORD = "At-n0kNf"
    MT5_SERVER = "MetaQuotes-Demo"

    # SYMBOL SETTINGS
    SYMBOL = "XAUUSD"
    TIMEFRAME = mt5.TIMEFRAME_M5  # 5-minute chart (matches backtest)

    # POSITION SIZING - FIXED (NO COMPOUNDING)
    LOT_SIZE = 0.1  # Fixed 0.1 lots per trade
    MAX_SLIPPAGE = 50  # Maximum slippage in points

    # DAILY RISK LIMITS
    DAILY_PROFIT_TARGET = 100.0  # Stop trading at +$100 profit
    DAILY_LOSS_LIMIT = 100.0  # Stop trading at -$100 loss
    MAX_TRADES_PER_DAY = 5  # Maximum number of trades per day

    # EMA SETTINGS (from backtest)
    EMA_FAST = 1  # Immediate price response
    EMA_SLOW_1 = 14  # First slow EMA
    EMA_SLOW_2 = 18  # Second slow EMA
    EMA_SLOW_3 = 24  # Third slow EMA
    EMA_FILTER = 100  # Price filter EMA

    # ATR SETTINGS
    ATR_PERIOD = 10
    SL_ATR_MULTIPLIER = 6.0  # Stop loss = 6 × ATR (wider for live trading)
    TP_ATR_MULTIPLIER = 6.5  # Take profit = 6.5 × ATR

    # PULLBACK SETTINGS
    MIN_PULLBACK_CANDLES = 1  # Minimum pullback candles
    MAX_PULLBACK_CANDLES = 3  # Maximum pullback candles
    WINDOW_PERIODS = 7  # Bars to wait for breakout

    # TRADING HOURS (UTC)
    TRADE_START_HOUR = 7  # 7 AM UTC (London open)
    TRADE_END_HOUR = 17  # 5 PM UTC (NY close)

    # TRADING DIRECTION
    ENABLE_LONG_TRADES = True
    ENABLE_SHORT_TRADES = False  # Disabled by default (backtest shows LONG only)

    # LOGGING
    LOG_FILE = "mt5_bot_log.txt"
    TRADE_JOURNAL = "trade_journal.json"
    VERBOSE = True  # Print debug information


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def log(message):
    """Log message to console and file"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_msg = f"[{timestamp}] {message}"

    if Config.VERBOSE:
        print(log_msg)

    with open(Config.LOG_FILE, "a") as f:
        f.write(log_msg + "\n")


def calculate_ema(prices, period):
    """Calculate Exponential Moving Average"""
    return pd.Series(prices).ewm(span=period, adjust=False).mean().iloc[-1]


def calculate_atr(highs, lows, closes, period):
    """Calculate Average True Range"""
    high = pd.Series(highs)
    low = pd.Series(lows)
    close = pd.Series(closes)

    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())

    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean().iloc[-1]

    return atr


def get_candle_data(symbol, timeframe, count=200):
    """Get recent candle data from MT5"""
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)

    if rates is None or len(rates) == 0:
        log(f"ERROR: Failed to get rates for {symbol}")
        return None

    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')

    return df


def is_trading_hours():
    """Check if current time is within trading hours"""
    now = datetime.utcnow()
    current_hour = now.hour

    if Config.TRADE_START_HOUR <= current_hour < Config.TRADE_END_HOUR:
        return True
    return False


# ============================================================
# DAILY RISK MANAGEMENT
# ============================================================

class DailyRiskManager:
    """Manages daily profit/loss limits"""

    def __init__(self):
        self.daily_pnl = 0.0
        self.trade_count = 0
        self.last_reset = datetime.now().date()

    def reset_if_new_day(self):
        """Reset counters at start of new day"""
        today = datetime.now().date()
        if today != self.last_reset:
            self.daily_pnl = 0.0
            self.trade_count = 0
            self.last_reset = today
            log("🔄 Daily counters reset for new trading day")

    def update_pnl(self):
        """Update daily P&L from MT5 history"""
        self.reset_if_new_day()

        # Get today's deals
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        deals = mt5.history_deals_get(today_start, datetime.now())

        if deals is None:
            return self.daily_pnl

        # Calculate total P&L
        self.daily_pnl = sum(deal.profit for deal in deals if deal.symbol == Config.SYMBOL)
        self.trade_count = len([d for d in deals if d.symbol == Config.SYMBOL and d.entry == mt5.DEAL_ENTRY_IN])

        return self.daily_pnl

    def can_trade(self):
        """Check if trading is allowed based on daily limits"""
        self.update_pnl()

        # Check profit target
        if self.daily_pnl >= Config.DAILY_PROFIT_TARGET:
            log(f"✅ Daily profit target reached: ${self.daily_pnl:.2f} >= ${Config.DAILY_PROFIT_TARGET}")
            return False, "PROFIT_TARGET_REACHED"

        # Check loss limit
        if self.daily_pnl <= -Config.DAILY_LOSS_LIMIT:
            log(f"🛑 Daily loss limit reached: ${self.daily_pnl:.2f} <= -${Config.DAILY_LOSS_LIMIT}")
            return False, "LOSS_LIMIT_REACHED"

        # Check trade count
        if self.trade_count >= Config.MAX_TRADES_PER_DAY:
            log(f"🛑 Max trades per day reached: {self.trade_count} >= {Config.MAX_TRADES_PER_DAY}")
            return False, "MAX_TRADES_REACHED"

        # Check trading hours
        if not is_trading_hours():
            return False, "OUTSIDE_TRADING_HOURS"

        return True, "OK"


# ============================================================
# TRADING STRATEGY - 4-PHASE ENTRY SYSTEM
# ============================================================

class PullbackStrategy:
    """Implements the 4-phase pullback entry system"""

    def __init__(self):
        self.state = "SCANNING"  # SCANNING, ARMED_LONG, ARMED_SHORT, WINDOW_OPEN
        self.signal_bar = None
        self.pullback_count = 0
        self.window_start_bar = None
        self.window_high = None
        self.window_low = None
        self.signal_direction = None

        log("📊 Strategy initialized - State: SCANNING")

    def reset(self):
        """Reset strategy state"""
        self.state = "SCANNING"
        self.signal_bar = None
        self.pullback_count = 0
        self.window_start_bar = None
        self.window_high = None
        self.window_low = None
        self.signal_direction = None
        log("🔄 Strategy state reset to SCANNING")

    def check_entry(self, df):
        """
        Check for entry signals using 4-phase system

        Returns:
            tuple: (should_enter, direction, entry_price, sl_price, tp_price)
        """
        if len(df) < 100:
            return False, None, None, None, None

        # Get latest data
        current_bar = len(df) - 1
        current = df.iloc[-1]
        previous = df.iloc[-2]

        # Calculate indicators
        closes = df['close'].values
        highs = df['high'].values
        lows = df['low'].values

        ema_fast = calculate_ema(closes, Config.EMA_FAST)
        ema_slow_1 = calculate_ema(closes, Config.EMA_SLOW_1)
        ema_slow_2 = calculate_ema(closes, Config.EMA_SLOW_2)
        ema_slow_3 = calculate_ema(closes, Config.EMA_SLOW_3)
        ema_filter = calculate_ema(closes, Config.EMA_FILTER)

        atr = calculate_atr(highs, lows, closes, Config.ATR_PERIOD)

        current_close = current['close']
        current_open = current['open']
        current_high = current['high']
        current_low = current['low']

        # PHASE 1: SCANNING - Look for EMA crossover
        if self.state == "SCANNING":
            # LONG signal: Fast EMA crosses above any slow EMA
            if Config.ENABLE_LONG_TRADES:
                if (ema_fast > ema_slow_1 or ema_fast > ema_slow_2 or ema_fast > ema_slow_3):
                    # Price filter: Close above filter EMA
                    if current_close > ema_filter:
                        self.state = "ARMED_LONG"
                        self.signal_bar = current_bar
                        self.signal_direction = "LONG"
                        self.pullback_count = 0
                        log(f"🎯 LONG signal detected! EMA crossover at {current_close:.2f}")
                        log(f"   Fast EMA: {ema_fast:.2f}, Slow EMAs: {ema_slow_1:.2f}/{ema_slow_2:.2f}/{ema_slow_3:.2f}")

            # SHORT signal: Fast EMA crosses below any slow EMA
            if Config.ENABLE_SHORT_TRADES:
                if (ema_fast < ema_slow_1 or ema_fast < ema_slow_2 or ema_fast < ema_slow_3):
                    # Price filter: Close below filter EMA
                    if current_close < ema_filter:
                        self.state = "ARMED_SHORT"
                        self.signal_bar = current_bar
                        self.signal_direction = "SHORT"
                        self.pullback_count = 0
                        log(f"🎯 SHORT signal detected! EMA crossover at {current_close:.2f}")

        # PHASE 2: ARMED - Wait for pullback
        elif self.state == "ARMED_LONG":
            # Count red candles (pullback)
            if current_close < current_open:
                self.pullback_count += 1
                log(f"📉 LONG pullback candle #{self.pullback_count}: Close {current_close:.2f} < Open {current_open:.2f}")

            # Check if pullback is complete
            if self.pullback_count >= Config.MIN_PULLBACK_CANDLES:
                # Pullback complete - open window
                self.state = "WINDOW_OPEN"
                self.window_start_bar = current_bar
                self.window_high = current_high
                log(f"🚪 LONG window opened! Pullback complete with {self.pullback_count} red candles")
                log(f"   Window high: {self.window_high:.2f}, watching for breakout...")

            # Reset if pullback too long
            if self.pullback_count > Config.MAX_PULLBACK_CANDLES:
                log(f"❌ LONG pullback too long ({self.pullback_count} candles), resetting")
                self.reset()

            # Global invalidation: opposite signal
            if current_close < ema_filter or ema_fast < ema_slow_1:
                log("❌ LONG signal invalidated (bearish conditions)")
                self.reset()

        elif self.state == "ARMED_SHORT":
            # Count green candles (pullback)
            if current_close > current_open:
                self.pullback_count += 1
                log(f"📈 SHORT pullback candle #{self.pullback_count}: Close {current_close:.2f} > Open {current_open:.2f}")

            # Check if pullback is complete
            if self.pullback_count >= Config.MIN_PULLBACK_CANDLES:
                # Pullback complete - open window
                self.state = "WINDOW_OPEN"
                self.window_start_bar = current_bar
                self.window_low = current_low
                log(f"🚪 SHORT window opened! Pullback complete with {self.pullback_count} green candles")
                log(f"   Window low: {self.window_low:.2f}, watching for breakdown...")

            # Reset if pullback too long
            if self.pullback_count > Config.MAX_PULLBACK_CANDLES:
                log(f"❌ SHORT pullback too long ({self.pullback_count} candles), resetting")
                self.reset()

            # Global invalidation: opposite signal
            if current_close > ema_filter or ema_fast > ema_slow_1:
                log("❌ SHORT signal invalidated (bullish conditions)")
                self.reset()

        # PHASE 3: WINDOW_OPEN - Wait for breakout
        elif self.state == "WINDOW_OPEN":
            bars_in_window = current_bar - self.window_start_bar

            # LONG breakout: Price breaks above window high
            if self.signal_direction == "LONG":
                if current_high > self.window_high:
                    # ENTRY!
                    entry_price = current_close
                    sl_price = entry_price - (atr * Config.SL_ATR_MULTIPLIER)
                    tp_price = entry_price + (atr * Config.TP_ATR_MULTIPLIER)

                    log(f"✅ LONG BREAKOUT! Price {current_high:.2f} > Window {self.window_high:.2f}")
                    log(f"   Entry: {entry_price:.2f}, SL: {sl_price:.2f}, TP: {tp_price:.2f}")
                    log(f"   ATR: {atr:.2f}, Risk: ${atr * Config.SL_ATR_MULTIPLIER:.2f}")

                    self.reset()  # Reset for next signal
                    return True, "LONG", entry_price, sl_price, tp_price

            # SHORT breakout: Price breaks below window low
            elif self.signal_direction == "SHORT":
                if current_low < self.window_low:
                    # ENTRY!
                    entry_price = current_close
                    sl_price = entry_price + (atr * Config.SL_ATR_MULTIPLIER)
                    tp_price = entry_price - (atr * Config.TP_ATR_MULTIPLIER)

                    log(f"✅ SHORT BREAKDOWN! Price {current_low:.2f} < Window {self.window_low:.2f}")
                    log(f"   Entry: {entry_price:.2f}, SL: {sl_price:.2f}, TP: {tp_price:.2f}")

                    self.reset()  # Reset for next signal
                    return True, "SHORT", entry_price, sl_price, tp_price

            # Window expires after N bars
            if bars_in_window >= Config.WINDOW_PERIODS:
                log(f"⏰ {self.signal_direction} window expired after {bars_in_window} bars, resetting")
                self.reset()

        return False, None, None, None, None


# ============================================================
# TRADE EXECUTION
# ============================================================

class TradeExecutor:
    """Handles order placement and management"""

    def __init__(self):
        self.magic_number = 123456
        self.current_position = None

    def place_order(self, direction, entry_price, sl_price, tp_price):
        """
        Place market order with SL and TP

        Args:
            direction: "LONG" or "SHORT"
            entry_price: Entry price
            sl_price: Stop loss price
            tp_price: Take profit price

        Returns:
            bool: True if order placed successfully
        """
        symbol_info = mt5.symbol_info(Config.SYMBOL)
        if symbol_info is None:
            log(f"ERROR: Symbol {Config.SYMBOL} not found")
            return False

        if not symbol_info.visible:
            if not mt5.symbol_select(Config.SYMBOL, True):
                log(f"ERROR: Failed to select {Config.SYMBOL}")
                return False

        # Get current price
        tick = mt5.symbol_info_tick(Config.SYMBOL)
        if tick is None:
            log("ERROR: Failed to get tick data")
            return False

        # Prepare request
        if direction == "LONG":
            order_type = mt5.ORDER_TYPE_BUY
            price = tick.ask
        else:
            order_type = mt5.ORDER_TYPE_SELL
            price = tick.bid

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": Config.SYMBOL,
            "volume": Config.LOT_SIZE,
            "type": order_type,
            "price": price,
            "sl": round(sl_price, 2),
            "tp": round(tp_price, 2),
            "deviation": Config.MAX_SLIPPAGE,
            "magic": self.magic_number,
            "comment": f"Bot {direction} Entry",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        # Send order
        result = mt5.order_send(request)

        if result is None:
            log(f"ERROR: order_send failed, error code: {mt5.last_error()}")
            return False

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            log(f"ERROR: Order failed, retcode: {result.retcode}")
            return False

        # Success!
        log(f"🎉 {direction} ORDER PLACED SUCCESSFULLY!")
        log(f"   Ticket: {result.order}")
        log(f"   Volume: {Config.LOT_SIZE} lots")
        log(f"   Entry: {result.price:.2f}")
        log(f"   SL: {sl_price:.2f}")
        log(f"   TP: {tp_price:.2f}")

        # Save trade to journal
        self.save_trade_journal(result, direction, sl_price, tp_price)

        return True

    def save_trade_journal(self, result, direction, sl, tp):
        """Save trade details to journal file"""
        trade_data = {
            "timestamp": datetime.now().isoformat(),
            "ticket": result.order,
            "direction": direction,
            "entry": result.price,
            "sl": sl,
            "tp": tp,
            "volume": Config.LOT_SIZE,
            "comment": f"Bot {direction} Entry"
        }

        # Append to journal file
        journal_file = Path(Config.TRADE_JOURNAL)
        if journal_file.exists():
            with open(journal_file, 'r') as f:
                journal = json.load(f)
        else:
            journal = []

        journal.append(trade_data)

        with open(journal_file, 'w') as f:
            json.dump(journal, f, indent=2)

    def has_open_position(self):
        """Check if there's an open position"""
        positions = mt5.positions_get(symbol=Config.SYMBOL)
        if positions is None or len(positions) == 0:
            return False
        return True


# ============================================================
# MAIN BOT LOOP
# ============================================================

def main():
    """Main bot execution loop"""

    # Initialize MT5
    if not mt5.initialize():
        log("ERROR: MT5 initialization failed")
        return

    # Login if credentials provided
    if Config.MT5_LOGIN and Config.MT5_PASSWORD and Config.MT5_SERVER:
        authorized = mt5.login(Config.MT5_LOGIN, Config.MT5_PASSWORD, Config.MT5_SERVER)
        if not authorized:
            log(f"ERROR: Login failed for account {Config.MT5_LOGIN}")
            log(f"Error: {mt5.last_error()}")
            mt5.shutdown()
            return
        log(f"[OK] Logged in to MT5: {Config.MT5_LOGIN} @ {Config.MT5_SERVER}")
    else:
        log("Using already logged-in MT5 terminal")

    log("=" * 60)
    log("MT5 XAUUSD TRADING BOT STARTED")
    log("=" * 60)
    log(f"Symbol: {Config.SYMBOL}")
    log(f"Lot Size: {Config.LOT_SIZE} (FIXED)")
    log(f"Daily Profit Target: ${Config.DAILY_PROFIT_TARGET}")
    log(f"Daily Loss Limit: ${Config.DAILY_LOSS_LIMIT}")
    log(f"ATR Stop Loss: {Config.SL_ATR_MULTIPLIER}× ATR")
    log(f"ATR Take Profit: {Config.TP_ATR_MULTIPLIER}× ATR")
    log(f"Trading Hours: {Config.TRADE_START_HOUR:02d}:00 - {Config.TRADE_END_HOUR:02d}:00 UTC")
    log("=" * 60)

    # Initialize components
    risk_manager = DailyRiskManager()
    strategy = PullbackStrategy()
    executor = TradeExecutor()

    try:
        while True:
            # Check if we can trade
            can_trade, reason = risk_manager.can_trade()

            if not can_trade:
                if reason == "OUTSIDE_TRADING_HOURS":
                    # Sleep for 5 minutes during off-hours
                    time.sleep(300)
                    continue
                else:
                    # Daily limit reached - wait until next day
                    log(f"⏸️  Trading paused: {reason}")
                    log(f"   Daily P&L: ${risk_manager.daily_pnl:.2f}")
                    log(f"   Trades today: {risk_manager.trade_count}")
                    time.sleep(3600)  # Sleep for 1 hour
                    continue

            # Check if we already have a position
            if executor.has_open_position():
                # Don't open new positions while one is active
                time.sleep(60)  # Check every minute
                continue

            # Get market data
            df = get_candle_data(Config.SYMBOL, Config.TIMEFRAME, count=200)
            if df is None:
                log("ERROR: Failed to get market data")
                time.sleep(60)
                continue

            # Check for entry signal
            should_enter, direction, entry, sl, tp = strategy.check_entry(df)

            if should_enter:
                # Place the trade
                success = executor.place_order(direction, entry, sl, tp)

                if success:
                    log(f"✅ Trade executed successfully!")
                else:
                    log(f"❌ Trade execution failed")
                    strategy.reset()  # Reset strategy on failure

            # Sleep for 30 seconds before next check
            time.sleep(30)

    except KeyboardInterrupt:
        log("\n🛑 Bot stopped by user (Ctrl+C)")

    except Exception as e:
        log(f"ERROR: {str(e)}")

    finally:
        # Cleanup
        mt5.shutdown()
        log("=" * 60)
        log("MT5 XAUUSD TRADING BOT STOPPED")
        log("=" * 60)


if __name__ == "__main__":
    main()
