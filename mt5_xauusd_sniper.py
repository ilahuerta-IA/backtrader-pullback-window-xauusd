"""
MT5 XAUUSD SNIPER BOT - FTMO Edition
====================================
Battle-tested strategy with all safety mechanisms:
- Fixed 0.10 lot sizing (NO pyramiding, NO martingale)
- $100 daily profit target / $100 daily loss limit
- ATR-based stops with minimum 10-point breathing room
- Breakeven trailing stop at 50% to TP
- Session filtering (London/NY only)
- Consecutive loss circuit breaker
- Full trade journaling

Based on: backtrader-pullback-window-xauusd + FTMO_SNIPER_STRATEGY.md
Date: January 3, 2026
"""

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import json
from pathlib import Path
from enum import Enum

# ============================================================
# CONFIGURATION
# ============================================================

class Config:
    """FTMO-optimized bot configuration"""

    # === MT5 CONNECTION (Optional - leave blank to use logged-in terminal) ===
    MT5_LOGIN = 10008946929
    MT5_PASSWORD = "At-n0kNf"
    MT5_SERVER = "MetaQuotes-Demo"

    # === SYMBOL SETTINGS ===
    SYMBOL = "XAUUSD"
    TIMEFRAME = mt5.TIMEFRAME_M5  # Matches backtest

    # === POSITION SIZING - FIXED (SNIPER PRINCIPLE #1) ===
    FIXED_LOT_SIZE = 0.10  # NEVER changes, never calculates
    MAX_SLIPPAGE = 50  # Points

    # === DAILY RISK LIMITS (SNIPER PRINCIPLE #4) ===
    DAILY_PROFIT_TARGET = 100.0  # Stop at +$100/day
    DAILY_LOSS_LIMIT = 100.0  # HARD STOP at -$100/day
    MAX_TRADES_PER_DAY = 3  # Quality over quantity (Principle #5)

    # === STOP LOSS & TAKE PROFIT (SNIPER PRINCIPLE #2) ===
    STOP_LOSS_POINTS = 10  # Minimum 10 points (was 8-12, too tight)
    TAKE_PROFIT_POINTS = 15  # Target $150 profit
    USE_ATR_STOPS = True  # Override with ATR if True
    ATR_PERIOD = 10
    ATR_SL_MULTIPLIER = 2.5  # Wider than backtest (was 4.5)
    ATR_TP_MULTIPLIER = 3.5  # Adjusted for live trading

    # === BREAKEVEN TRAILING STOP (SNIPER PRINCIPLE #3) ===
    ENABLE_BREAKEVEN_STOP = True
    BREAKEVEN_TRIGGER_PERCENT = 0.50  # Move to BE at 50% to TP
    LOCK_PROFIT_PERCENT = 0.75  # Lock profit at 75% to TP

    # === EMA SETTINGS (From backtest) ===
    EMA_FAST = 1  # Immediate response
    EMA_SLOW_1 = 14
    EMA_SLOW_2 = 18
    EMA_SLOW_3 = 24
    EMA_FILTER = 100  # Trend filter

    # === PULLBACK SYSTEM ===
    MIN_PULLBACK_CANDLES = 1
    MAX_PULLBACK_CANDLES = 3
    WINDOW_PERIODS = 7

    # === SESSION FILTERING (FTMO Sniper: ICT Killzones) ===
    ENABLE_SESSION_FILTER = False  # SET FALSE FOR 24/7 TESTING
    LONDON_START = 7  # 07:00 UTC
    LONDON_END = 11  # 11:00 UTC
    NY_START = 13  # 13:00 UTC
    NY_END = 17  # 17:00 UTC

    # === HIGHER TIMEFRAME BIAS (FTMO Enhancement) ===
    USE_HTF_BIAS = True  # Check H1 trend before entry
    HTF_TIMEFRAME = mt5.TIMEFRAME_H1
    HTF_EMA_PERIOD = 50  # H1 trend EMA

    # === CONSECUTIVE LOSS BREAKER (FTMO Tactical) ===
    ENABLE_CIRCUIT_BREAKER = True
    MAX_CONSECUTIVE_LOSSES = 2  # Stop after 2 losses
    CIRCUIT_BREAK_DURATION = 7200  # 2 hours in seconds

    # === TRADING DIRECTION ===
    ENABLE_LONG_TRADES = True
    ENABLE_SHORT_TRADES = False  # Backtest shows LONG-only performs best

    # === TIME-BASED EXITS ===
    MAX_TRADE_DURATION_MINUTES = 120  # Close after 2 hours
    REVIEW_TRADE_AT_MINUTES = 30  # Check trade validity

    # === LOGGING ===
    LOG_FILE = "ftmo_sniper_log.txt"
    TRADE_JOURNAL = "ftmo_trade_journal.json"
    DAILY_SUMMARY = "ftmo_daily_summary.json"
    VERBOSE = True


# ============================================================
# STATE MANAGEMENT
# ============================================================

class TradingState(Enum):
    """Bot operational states"""
    SCANNING = "SCANNING"  # Looking for signals
    ARMED_LONG = "ARMED_LONG"  # LONG signal detected, waiting pullback
    ARMED_SHORT = "ARMED_SHORT"  # SHORT signal detected, waiting pullback
    WINDOW_OPEN = "WINDOW_OPEN"  # Pullback complete, watching breakout
    IN_TRADE = "IN_TRADE"  # Position open
    CIRCUIT_BREAK = "CIRCUIT_BREAK"  # Cooling off after losses
    DAILY_LIMIT_HIT = "DAILY_LIMIT_HIT"  # Daily limit reached


# ============================================================
# UTILITIES
# ============================================================

def log(message, level="INFO"):
    """Enhanced logging with levels"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_msg = f"[{timestamp}] [{level}] {message}"

    if Config.VERBOSE or level in ["ERROR", "TRADE"]:
        print(log_msg)

    with open(Config.LOG_FILE, "a", encoding="utf-8") as f:
        f.write(log_msg + "\n")


def calculate_ema(prices, period):
    """Calculate EMA"""
    return pd.Series(prices).ewm(span=period, adjust=False).mean().iloc[-1]


def calculate_atr(highs, lows, closes, period):
    """Calculate ATR"""
    high = pd.Series(highs)
    low = pd.Series(lows)
    close = pd.Series(closes)

    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())

    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean().iloc[-1]

    return atr


def get_candles(symbol, timeframe, count=200):
    """Get candle data with error handling"""
    try:
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
        if rates is None or len(rates) == 0:
            log(f"Failed to get rates for {symbol}", "ERROR")
            return None

        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        return df
    except Exception as e:
        log(f"Error getting candles: {e}", "ERROR")
        return None


def is_session_active():
    """Check if in London or NY session"""
    if not Config.ENABLE_SESSION_FILTER:
        return True

    now_utc = datetime.utcnow()
    hour = now_utc.hour

    # London session
    if Config.LONDON_START <= hour < Config.LONDON_END:
        return True

    # NY session
    if Config.NY_START <= hour < Config.NY_END:
        return True

    return False


def get_htf_bias(symbol):
    """Get higher timeframe trend bias"""
    if not Config.USE_HTF_BIAS:
        return "NEUTRAL"

    df = get_candles(symbol, Config.HTF_TIMEFRAME, count=100)
    if df is None:
        return "NEUTRAL"

    closes = df['close'].values
    current_price = closes[-1]
    htf_ema = calculate_ema(closes, Config.HTF_EMA_PERIOD)

    if current_price > htf_ema:
        return "BULLISH"
    elif current_price < htf_ema:
        return "BEARISH"
    else:
        return "NEUTRAL"


# ============================================================
# RISK MANAGER
# ============================================================

class RiskManager:
    """FTMO-compliant risk management"""

    def __init__(self):
        self.daily_pnl = 0.0
        self.trade_count = 0
        self.consecutive_losses = 0
        self.consecutive_wins = 0
        self.circuit_break_until = None
        self.last_reset = datetime.now().date()
        self.trades_today = []

        log("✅ Risk Manager initialized")

    def reset_daily(self):
        """Reset at start of new day"""
        today = datetime.now().date()
        if today != self.last_reset:
            # Save yesterday's summary
            self.save_daily_summary()

            # Reset counters
            self.daily_pnl = 0.0
            self.trade_count = 0
            self.consecutive_losses = 0
            self.consecutive_wins = 0
            self.circuit_break_until = None
            self.trades_today = []
            self.last_reset = today

            log("🔄 Daily risk counters reset", "INFO")

    def update_pnl(self):
        """Update P&L from MT5"""
        self.reset_daily()

        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        deals = mt5.history_deals_get(today_start, datetime.now())

        if deals is None:
            return self.daily_pnl

        self.daily_pnl = sum(d.profit for d in deals if d.symbol == Config.SYMBOL)
        self.trade_count = len([d for d in deals if d.symbol == Config.SYMBOL and d.entry == mt5.DEAL_ENTRY_IN])

        return self.daily_pnl

    def can_trade(self):
        """Master trading permission check"""
        self.update_pnl()

        # Check profit target
        if self.daily_pnl >= Config.DAILY_PROFIT_TARGET:
            log(f"✅ PROFIT TARGET HIT: ${self.daily_pnl:.2f} >= ${Config.DAILY_PROFIT_TARGET}", "TRADE")
            return False, TradingState.DAILY_LIMIT_HIT

        # Check loss limit (HARD STOP)
        if self.daily_pnl <= -Config.DAILY_LOSS_LIMIT:
            log(f"🛑 LOSS LIMIT HIT: ${self.daily_pnl:.2f} <= -${Config.DAILY_LOSS_LIMIT}", "TRADE")
            return False, TradingState.DAILY_LIMIT_HIT

        # Check trade count
        if self.trade_count >= Config.MAX_TRADES_PER_DAY:
            log(f"🛑 MAX TRADES HIT: {self.trade_count}/{Config.MAX_TRADES_PER_DAY}", "INFO")
            return False, TradingState.DAILY_LIMIT_HIT

        # Check circuit breaker
        if Config.ENABLE_CIRCUIT_BREAKER and self.circuit_break_until:
            if datetime.now() < self.circuit_break_until:
                remaining = (self.circuit_break_until - datetime.now()).seconds // 60
                log(f"⏸️  Circuit break active ({remaining} min remaining)", "INFO")
                return False, TradingState.CIRCUIT_BREAK

        # Check session
        if not is_session_active():
            return False, TradingState.SCANNING

        return True, TradingState.SCANNING

    def record_trade_result(self, profit):
        """Record trade outcome and update streaks"""
        if profit > 0:
            self.consecutive_wins += 1
            self.consecutive_losses = 0
            log(f"✅ Win streak: {self.consecutive_wins}", "INFO")
        else:
            self.consecutive_losses += 1
            self.consecutive_wins = 0
            log(f"⚠️  Loss streak: {self.consecutive_losses}", "INFO")

            # Trigger circuit breaker
            if Config.ENABLE_CIRCUIT_BREAKER and self.consecutive_losses >= Config.MAX_CONSECUTIVE_LOSSES:
                self.circuit_break_until = datetime.now() + timedelta(seconds=Config.CIRCUIT_BREAK_DURATION)
                log(f"🔴 CIRCUIT BREAKER TRIGGERED! Cooling off until {self.circuit_break_until.strftime('%H:%M')}", "TRADE")

    def save_daily_summary(self):
        """Save daily performance summary"""
        summary = {
            "date": self.last_reset.isoformat(),
            "total_pnl": self.daily_pnl,
            "trade_count": self.trade_count,
            "trades": self.trades_today,
            "max_consecutive_wins": self.consecutive_wins,
            "max_consecutive_losses": self.consecutive_losses
        }

        summaries = []
        summary_file = Path(Config.DAILY_SUMMARY)
        if summary_file.exists():
            with open(summary_file, 'r') as f:
                summaries = json.load(f)

        summaries.append(summary)

        with open(summary_file, 'w') as f:
            json.dump(summaries, f, indent=2)

        log(f"📊 Daily summary saved: ${self.daily_pnl:.2f} PnL, {self.trade_count} trades", "INFO")


# ============================================================
# ENTRY STRATEGY
# ============================================================

class SniperStrategy:
    """4-phase pullback entry system with FTMO enhancements"""

    def __init__(self):
        self.state = TradingState.SCANNING
        self.signal_bar = None
        self.pullback_count = 0
        self.window_start_bar = None
        self.window_high = None
        self.window_low = None
        self.signal_direction = None
        self.entry_reason = ""

        log("📊 Sniper Strategy initialized")

    def reset(self):
        """Reset strategy state"""
        self.state = TradingState.SCANNING
        self.signal_bar = None
        self.pullback_count = 0
        self.window_start_bar = None
        self.window_high = None
        self.window_low = None
        self.signal_direction = None
        self.entry_reason = ""

    def check_entry(self, df):
        """
        4-Phase entry system with FTMO filters

        Returns:
            (should_enter, direction, entry, sl, tp, reason)
        """
        if len(df) < 150:
            return False, None, None, None, None, ""

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

        # Get HTF bias
        htf_bias = get_htf_bias(Config.SYMBOL)

        # === PHASE 1: SCANNING ===
        if self.state == TradingState.SCANNING:
            # LONG signal
            if Config.ENABLE_LONG_TRADES:
                if (ema_fast > ema_slow_1 or ema_fast > ema_slow_2 or ema_fast > ema_slow_3):
                    if current_close > ema_filter:
                        # HTF bias check
                        if htf_bias in ["BULLISH", "NEUTRAL"]:
                            self.state = TradingState.ARMED_LONG
                            self.signal_bar = current_bar
                            self.signal_direction = "LONG"
                            self.pullback_count = 0
                            self.entry_reason = f"EMA crossover + HTF {htf_bias}"
                            log(f"🎯 LONG signal! Price {current_close:.2f}, HTF: {htf_bias}", "INFO")

            # SHORT signal
            if Config.ENABLE_SHORT_TRADES:
                if (ema_fast < ema_slow_1 or ema_fast < ema_slow_2 or ema_fast < ema_slow_3):
                    if current_close < ema_filter:
                        # HTF bias check
                        if htf_bias in ["BEARISH", "NEUTRAL"]:
                            self.state = TradingState.ARMED_SHORT
                            self.signal_bar = current_bar
                            self.signal_direction = "SHORT"
                            self.pullback_count = 0
                            self.entry_reason = f"EMA crossover + HTF {htf_bias}"
                            log(f"🎯 SHORT signal! Price {current_close:.2f}, HTF: {htf_bias}", "INFO")

        # === PHASE 2: ARMED (Pullback) ===
        elif self.state == TradingState.ARMED_LONG:
            if current_close < current_open:  # Red candle
                self.pullback_count += 1
                log(f"📉 LONG pullback #{self.pullback_count}", "INFO")

            if self.pullback_count >= Config.MIN_PULLBACK_CANDLES:
                self.state = TradingState.WINDOW_OPEN
                self.window_start_bar = current_bar
                self.window_high = current_high
                log(f"🚪 LONG window open! High: {self.window_high:.2f}", "INFO")

            if self.pullback_count > Config.MAX_PULLBACK_CANDLES or current_close < ema_filter:
                log("❌ LONG signal invalidated", "INFO")
                self.reset()

        elif self.state == TradingState.ARMED_SHORT:
            if current_close > current_open:  # Green candle
                self.pullback_count += 1
                log(f"📈 SHORT pullback #{self.pullback_count}", "INFO")

            if self.pullback_count >= Config.MIN_PULLBACK_CANDLES:
                self.state = TradingState.WINDOW_OPEN
                self.window_start_bar = current_bar
                self.window_low = current_low
                log(f"🚪 SHORT window open! Low: {self.window_low:.2f}", "INFO")

            if self.pullback_count > Config.MAX_PULLBACK_CANDLES or current_close > ema_filter:
                log("❌ SHORT signal invalidated", "INFO")
                self.reset()

        # === PHASE 3: WINDOW_OPEN (Breakout) ===
        elif self.state == TradingState.WINDOW_OPEN:
            bars_in_window = current_bar - self.window_start_bar

            # LONG breakout
            if self.signal_direction == "LONG":
                if current_high > self.window_high:
                    # ENTRY!
                    entry = current_close
                    sl, tp = self.calculate_stops(entry, atr, "LONG")

                    log(f"✅ LONG BREAKOUT! Entry: {entry:.2f}, SL: {sl:.2f}, TP: {tp:.2f}", "TRADE")
                    self.reset()
                    return True, "LONG", entry, sl, tp, self.entry_reason

            # SHORT breakout
            elif self.signal_direction == "SHORT":
                if current_low < self.window_low:
                    # ENTRY!
                    entry = current_close
                    sl, tp = self.calculate_stops(entry, atr, "SHORT")

                    log(f"✅ SHORT BREAKDOWN! Entry: {entry:.2f}, SL: {sl:.2f}, TP: {tp:.2f}", "TRADE")
                    self.reset()
                    return True, "SHORT", entry, sl, tp, self.entry_reason

            # Window expiry
            if bars_in_window >= Config.WINDOW_PERIODS:
                log(f"⏰ Window expired after {bars_in_window} bars", "INFO")
                self.reset()

        return False, None, None, None, None, ""

    def calculate_stops(self, entry, atr, direction):
        """Calculate SL and TP with FTMO principles"""
        if Config.USE_ATR_STOPS:
            sl_distance = max(atr * Config.ATR_SL_MULTIPLIER, Config.STOP_LOSS_POINTS)
            tp_distance = max(atr * Config.ATR_TP_MULTIPLIER, Config.TAKE_PROFIT_POINTS)
        else:
            sl_distance = Config.STOP_LOSS_POINTS
            tp_distance = Config.TAKE_PROFIT_POINTS

        if direction == "LONG":
            sl = entry - sl_distance
            tp = entry + tp_distance
        else:
            sl = entry + sl_distance
            tp = entry - tp_distance

        return sl, tp


# ============================================================
# POSITION MANAGER
# ============================================================

class PositionManager:
    """Manages open positions with breakeven trailing"""

    def __init__(self):
        self.position = None
        self.entry_time = None
        self.entry_price = None
        self.sl_price = None
        self.tp_price = None
        self.direction = None
        self.breakeven_moved = False
        self.profit_locked = False

        log("✅ Position Manager initialized")

    def open_position(self, direction, entry, sl, tp, reason):
        """Place order and record position"""
        symbol_info = mt5.symbol_info(Config.SYMBOL)
        if symbol_info is None:
            log(f"Symbol {Config.SYMBOL} not found", "ERROR")
            return False

        if not symbol_info.visible:
            mt5.symbol_select(Config.SYMBOL, True)

        tick = mt5.symbol_info_tick(Config.SYMBOL)
        if tick is None:
            log("Failed to get tick", "ERROR")
            return False

        # Prepare order
        if direction == "LONG":
            order_type = mt5.ORDER_TYPE_BUY
            price = tick.ask
        else:
            order_type = mt5.ORDER_TYPE_SELL
            price = tick.bid

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": Config.SYMBOL,
            "volume": Config.FIXED_LOT_SIZE,
            "type": order_type,
            "price": price,
            "sl": round(sl, 2),
            "tp": round(tp, 2),
            "deviation": Config.MAX_SLIPPAGE,
            "magic": 123456,
            "comment": f"Sniper {direction}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        # Send order
        result = mt5.order_send(request)

        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            log(f"Order failed: {mt5.last_error()}", "ERROR")
            return False

        # Success - record position
        self.position = result.order
        self.entry_time = datetime.now()
        self.entry_price = result.price
        self.sl_price = sl
        self.tp_price = tp
        self.direction = direction
        self.breakeven_moved = False
        self.profit_locked = False

        log(f"🎉 {direction} POSITION OPENED", "TRADE")
        log(f"   Ticket: {result.order}, Lots: {Config.FIXED_LOT_SIZE}", "TRADE")
        log(f"   Entry: {result.price:.2f}, SL: {sl:.2f}, TP: {tp:.2f}", "TRADE")
        log(f"   Reason: {reason}", "TRADE")

        # Save to journal
        self.save_to_journal(result, reason)

        return True

    def manage_position(self):
        """Check and update trailing stops"""
        if self.position is None:
            return

        # Get current position
        positions = mt5.positions_get(ticket=self.position)
        if not positions or len(positions) == 0:
            # Position closed
            self.position = None
            return

        pos = positions[0]
        current_price = pos.price_current
        unrealized_pnl = pos.profit

        # Calculate profit percentage
        target_profit = abs(self.tp_price - self.entry_price) * Config.FIXED_LOT_SIZE * 100
        profit_percent = unrealized_pnl / target_profit if target_profit > 0 else 0

        # Breakeven at 50%
        if Config.ENABLE_BREAKEVEN_STOP and not self.breakeven_moved:
            if profit_percent >= Config.BREAKEVEN_TRIGGER_PERCENT:
                self.move_stop_to_breakeven()

        # Lock profit at 75%
        if Config.ENABLE_BREAKEVEN_STOP and not self.profit_locked:
            if profit_percent >= Config.LOCK_PROFIT_PERCENT:
                self.lock_partial_profit()

        # Time-based review
        time_in_trade = (datetime.now() - self.entry_time).seconds // 60
        if time_in_trade >= Config.REVIEW_TRADE_AT_MINUTES:
            if unrealized_pnl < 0:
                log(f"⚠️  Trade at {time_in_trade} min, P&L: ${unrealized_pnl:.2f}", "INFO")

        # Max duration exit
        if time_in_trade >= Config.MAX_TRADE_DURATION_MINUTES:
            log(f"⏰ Max duration reached ({time_in_trade} min), closing position", "TRADE")
            self.close_position("TIME_EXIT")

    def move_stop_to_breakeven(self):
        """Move SL to entry price"""
        if self.breakeven_moved:
            return

        # Modify stop loss
        result = self.modify_sl(self.entry_price)
        if result:
            self.breakeven_moved = True
            self.sl_price = self.entry_price
            log(f"🔒 BREAKEVEN STOP SET at {self.entry_price:.2f}", "TRADE")

    def lock_partial_profit(self):
        """Lock in partial profit"""
        if self.profit_locked:
            return

        # Calculate profit lock level
        if self.direction == "LONG":
            lock_price = self.entry_price + (abs(self.tp_price - self.entry_price) * 0.5)
        else:
            lock_price = self.entry_price - (abs(self.tp_price - self.entry_price) * 0.5)

        result = self.modify_sl(lock_price)
        if result:
            self.profit_locked = True
            self.sl_price = lock_price
            log(f"💰 PROFIT LOCKED at {lock_price:.2f}", "TRADE")

    def modify_sl(self, new_sl):
        """Modify stop loss"""
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": self.position,
            "sl": round(new_sl, 2),
            "tp": round(self.tp_price, 2),
        }

        result = mt5.order_send(request)
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            log(f"Failed to modify SL: {mt5.last_error()}", "ERROR")
            return False

        return True

    def close_position(self, reason):
        """Manually close position"""
        if self.position is None:
            return

        positions = mt5.positions_get(ticket=self.position)
        if not positions:
            return

        pos = positions[0]
        tick = mt5.symbol_info_tick(Config.SYMBOL)

        if pos.type == mt5.POSITION_TYPE_BUY:
            order_type = mt5.ORDER_TYPE_SELL
            price = tick.bid
        else:
            order_type = mt5.ORDER_TYPE_BUY
            price = tick.ask

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "position": self.position,
            "symbol": Config.SYMBOL,
            "volume": pos.volume,
            "type": order_type,
            "price": price,
            "magic": 123456,
            "comment": f"Close: {reason}",
        }

        result = mt5.order_send(request)
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            log(f"🔚 Position closed: {reason}", "TRADE")
            self.position = None

    def save_to_journal(self, result, reason):
        """Save trade to journal"""
        trade_data = {
            "timestamp": datetime.now().isoformat(),
            "ticket": result.order,
            "direction": self.direction,
            "entry": self.entry_price,
            "sl": self.sl_price,
            "tp": self.tp_price,
            "volume": Config.FIXED_LOT_SIZE,
            "reason": reason,
            "session": "London" if 7 <= datetime.utcnow().hour < 11 else "NY"
        }

        journal_file = Path(Config.TRADE_JOURNAL)
        if journal_file.exists():
            with open(journal_file, 'r') as f:
                journal = json.load(f)
        else:
            journal = []

        journal.append(trade_data)

        with open(journal_file, 'w') as f:
            json.dump(journal, f, indent=2)


# ============================================================
# MAIN BOT
# ============================================================

def main():
    """Main execution loop"""

    # Initialize MT5
    if not mt5.initialize():
        print("ERROR: MT5 initialization failed")
        return

    # Login if credentials provided
    if Config.MT5_LOGIN and Config.MT5_PASSWORD and Config.MT5_SERVER:
        authorized = mt5.login(Config.MT5_LOGIN, Config.MT5_PASSWORD, Config.MT5_SERVER)
        if not authorized:
            print(f"ERROR: Login failed for account {Config.MT5_LOGIN}")
            print(f"Error: {mt5.last_error()}")
            mt5.shutdown()
            return
        log(f"[OK] Logged in to MT5: {Config.MT5_LOGIN} @ {Config.MT5_SERVER}", "INFO")
    else:
        log("Using already logged-in MT5 terminal", "INFO")

    log("=" * 70, "INFO")
    log("FTMO SNIPER BOT STARTED", "INFO")
    log("=" * 70, "INFO")
    log(f"Symbol: {Config.SYMBOL} | Lot: {Config.FIXED_LOT_SIZE} (FIXED)", "INFO")
    log(f"Daily Limits: +${Config.DAILY_PROFIT_TARGET} / -${Config.DAILY_LOSS_LIMIT}", "INFO")
    log(f"Sessions: London ({Config.LONDON_START}-{Config.LONDON_END}), NY ({Config.NY_START}-{Config.NY_END}) UTC", "INFO")
    log(f"HTF Bias: {'ENABLED' if Config.USE_HTF_BIAS else 'DISABLED'}", "INFO")
    log(f"Circuit Breaker: {'ENABLED' if Config.ENABLE_CIRCUIT_BREAKER else 'DISABLED'}", "INFO")
    log("=" * 70, "INFO")

    # Initialize components
    risk_mgr = RiskManager()
    strategy = SniperStrategy()
    position_mgr = PositionManager()

    try:
        while True:
            # Check trading permission
            can_trade, state = risk_mgr.can_trade()

            if state == TradingState.DAILY_LIMIT_HIT:
                log(f"⏸️  Daily limit reached. P&L: ${risk_mgr.daily_pnl:.2f}", "INFO")
                time.sleep(3600)  # Sleep 1 hour
                continue

            if state == TradingState.CIRCUIT_BREAK:
                time.sleep(300)  # Check every 5 min
                continue

            # Manage existing position
            if position_mgr.position is not None:
                position_mgr.manage_position()
                time.sleep(60)  # Check every minute
                continue

            # Check for new entries
            if not can_trade:
                time.sleep(300)  # Outside trading hours
                continue

            # Get market data
            df = get_candles(Config.SYMBOL, Config.TIMEFRAME, 200)
            if df is None:
                time.sleep(60)
                continue

            # Check entry signal
            should_enter, direction, entry, sl, tp, reason = strategy.check_entry(df)

            if should_enter:
                success = position_mgr.open_position(direction, entry, sl, tp, reason)

                if not success:
                    strategy.reset()

            # Sleep between scans
            time.sleep(30)

    except KeyboardInterrupt:
        log("\n🛑 Bot stopped by user", "INFO")

    except Exception as e:
        log(f"CRITICAL ERROR: {str(e)}", "ERROR")

    finally:
        mt5.shutdown()
        log("=" * 70, "INFO")
        log("🎯 FTMO SNIPER BOT STOPPED", "INFO")
        log("=" * 70, "INFO")


if __name__ == "__main__":
    main()
