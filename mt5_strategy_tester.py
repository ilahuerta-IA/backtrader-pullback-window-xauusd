"""
MT5 Strategy Tester - Analyze Bot Performance
==============================================
Tests the Sniper strategy on historical MT5 data without live trading.
Analyzes:
- Win rate
- Profit factor
- Maximum drawdown
- Trade distribution
- Session performance
- Entry signal accuracy

Usage:
1. Ensure MT5 is running and logged in
2. Set test period in Config
3. Run: python mt5_strategy_tester.py
4. Review generated reports

Date: January 3, 2026
"""

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
from pathlib import Path

# Import strategy logic from sniper bot
from mt5_xauusd_sniper import (
    Config, calculate_ema, calculate_atr, get_htf_bias,
    is_session_active, TradingState
)

# ============================================================
# TEST CONFIGURATION
# ============================================================

class TestConfig:
    """Backtesting parameters"""

    # TEST PERIOD
    START_DATE = datetime(2026, 1, 1)  # January 1, 2026
    END_DATE = datetime(2026, 1, 3, 23, 59)  # January 3, 2026

    # ACCOUNT
    STARTING_BALANCE = 10000.0  # FTMO challenge starting balance

    # OUTPUT
    REPORT_FILE = "strategy_test_report.json"
    DETAILED_LOG = "strategy_test_detailed.txt"
    TRADE_CSV = "strategy_test_trades.csv"

    # VERBOSITY
    SHOW_EACH_TRADE = True
    SHOW_SIGNALS = False  # Show all signals, not just entries


# ============================================================
# STRATEGY TESTER
# ============================================================

class StrategyTester:
    """Backtests the Sniper strategy on historical data"""

    def __init__(self):
        self.balance = TestConfig.STARTING_BALANCE
        self.equity = TestConfig.STARTING_BALANCE
        self.trades = []
        self.current_position = None
        self.daily_pnl = {}

        # Strategy state
        self.state = TradingState.SCANNING
        self.signal_bar = None
        self.pullback_count = 0
        self.window_start_bar = None
        self.window_high = None
        self.window_low = None
        self.signal_direction = None

        print("🧪 Strategy Tester initialized")
        print(f"Test period: {TestConfig.START_DATE} to {TestConfig.END_DATE}")
        print(f"Starting balance: ${TestConfig.STARTING_BALANCE:,.2f}")
        print("-" * 70)

    def reset_state(self):
        """Reset strategy state"""
        self.state = TradingState.SCANNING
        self.signal_bar = None
        self.pullback_count = 0
        self.window_start_bar = None
        self.window_high = None
        self.window_low = None
        self.signal_direction = None

    def check_entry_signal(self, df, bar_index):
        """
        Check for entry signals (mirroring live bot logic)

        Returns:
            (should_enter, direction, entry_price, sl_price, tp_price)
        """
        if bar_index < 100:  # Need history
            return False, None, None, None, None

        # Get data up to current bar
        current_df = df.iloc[:bar_index + 1].copy()
        current = current_df.iloc[-1]

        # Calculate indicators
        closes = current_df['close'].values
        highs = current_df['high'].values
        lows = current_df['low'].values

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

        # === PHASE 1: SCANNING ===
        if self.state == TradingState.SCANNING:
            # LONG signal
            if Config.ENABLE_LONG_TRADES:
                if (ema_fast > ema_slow_1 or ema_fast > ema_slow_2 or ema_fast > ema_slow_3):
                    if current_close > ema_filter:
                        self.state = TradingState.ARMED_LONG
                        self.signal_bar = bar_index
                        self.signal_direction = "LONG"
                        self.pullback_count = 0

                        if TestConfig.SHOW_SIGNALS:
                            print(f"[{current['time']}] 🎯 LONG signal at {current_close:.2f}")

            # SHORT signal
            if Config.ENABLE_SHORT_TRADES:
                if (ema_fast < ema_slow_1 or ema_fast < ema_slow_2 or ema_fast < ema_slow_3):
                    if current_close < ema_filter:
                        self.state = TradingState.ARMED_SHORT
                        self.signal_bar = bar_index
                        self.signal_direction = "SHORT"
                        self.pullback_count = 0

                        if TestConfig.SHOW_SIGNALS:
                            print(f"[{current['time']}] 🎯 SHORT signal at {current_close:.2f}")

        # === PHASE 2: ARMED ===
        elif self.state == TradingState.ARMED_LONG:
            if current_close < current_open:  # Red candle
                self.pullback_count += 1

            if self.pullback_count >= Config.MIN_PULLBACK_CANDLES:
                self.state = TradingState.WINDOW_OPEN
                self.window_start_bar = bar_index
                self.window_high = current_high

                if TestConfig.SHOW_SIGNALS:
                    print(f"[{current['time']}] 🚪 LONG window open at {self.window_high:.2f}")

            if self.pullback_count > Config.MAX_PULLBACK_CANDLES or current_close < ema_filter:
                self.reset_state()

        elif self.state == TradingState.ARMED_SHORT:
            if current_close > current_open:  # Green candle
                self.pullback_count += 1

            if self.pullback_count >= Config.MIN_PULLBACK_CANDLES:
                self.state = TradingState.WINDOW_OPEN
                self.window_start_bar = bar_index
                self.window_low = current_low

                if TestConfig.SHOW_SIGNALS:
                    print(f"[{current['time']}] 🚪 SHORT window open at {self.window_low:.2f}")

            if self.pullback_count > Config.MAX_PULLBACK_CANDLES or current_close > ema_filter:
                self.reset_state()

        # === PHASE 3: WINDOW_OPEN ===
        elif self.state == TradingState.WINDOW_OPEN:
            bars_in_window = bar_index - self.window_start_bar

            # LONG breakout
            if self.signal_direction == "LONG":
                if current_high > self.window_high:
                    entry = current_close
                    sl, tp = self.calculate_stops(entry, atr, "LONG")

                    self.reset_state()
                    return True, "LONG", entry, sl, tp

            # SHORT breakout
            elif self.signal_direction == "SHORT":
                if current_low < self.window_low:
                    entry = current_close
                    sl, tp = self.calculate_stops(entry, atr, "SHORT")

                    self.reset_state()
                    return True, "SHORT", entry, sl, tp

            # Window expiry
            if bars_in_window >= Config.WINDOW_PERIODS:
                self.reset_state()

        return False, None, None, None, None

    def calculate_stops(self, entry, atr, direction):
        """Calculate SL and TP"""
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

    def simulate_trade(self, df, entry_bar, direction, entry_price, sl_price, tp_price):
        """
        Simulate trade execution from entry to exit

        Returns:
            (exit_price, exit_reason, exit_bar, pnl)
        """
        entry_time = df.iloc[entry_bar]['time']

        # Scan forward bars until SL, TP, or max duration
        max_bars = Config.MAX_TRADE_DURATION_MINUTES // 5  # Convert minutes to 5-min bars

        for i in range(entry_bar + 1, min(entry_bar + max_bars, len(df))):
            bar = df.iloc[i]
            high = bar['high']
            low = bar['low']
            close = bar['close']

            # Check for SL hit
            if direction == "LONG":
                if low <= sl_price:
                    # Stop loss hit
                    pnl = (sl_price - entry_price) * Config.FIXED_LOT_SIZE * 100
                    return sl_price, "STOP_LOSS", i, pnl

                # Check for TP hit
                if high >= tp_price:
                    # Take profit hit
                    pnl = (tp_price - entry_price) * Config.FIXED_LOT_SIZE * 100
                    return tp_price, "TAKE_PROFIT", i, pnl

            else:  # SHORT
                if high >= sl_price:
                    # Stop loss hit
                    pnl = (entry_price - sl_price) * Config.FIXED_LOT_SIZE * 100
                    return sl_price, "STOP_LOSS", i, pnl

                # Check for TP hit
                if low <= tp_price:
                    # Take profit hit
                    pnl = (entry_price - tp_price) * Config.FIXED_LOT_SIZE * 100
                    return tp_price, "TAKE_PROFIT", i, pnl

        # Max duration reached - close at current price
        final_bar = df.iloc[min(entry_bar + max_bars, len(df) - 1)]
        exit_price = final_bar['close']

        if direction == "LONG":
            pnl = (exit_price - entry_price) * Config.FIXED_LOT_SIZE * 100
        else:
            pnl = (entry_price - exit_price) * Config.FIXED_LOT_SIZE * 100

        return exit_price, "TIME_EXIT", min(entry_bar + max_bars, len(df) - 1), pnl

    def run_backtest(self):
        """Run full backtest on historical data"""

        # Get historical data from MT5
        print("📊 Fetching historical data from MT5...")

        if not mt5.initialize():
            print("ERROR: MT5 initialization failed")
            return None

        # Calculate number of bars needed
        start_timestamp = TestConfig.START_DATE.timestamp()
        end_timestamp = TestConfig.END_DATE.timestamp()

        # Get rates
        rates = mt5.copy_rates_range(
            Config.SYMBOL,
            Config.TIMEFRAME,
            TestConfig.START_DATE,
            TestConfig.END_DATE
        )

        if rates is None or len(rates) == 0:
            print(f"ERROR: Failed to get rates for {Config.SYMBOL}")
            mt5.shutdown()
            return None

        # Convert to DataFrame
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')

        print(f"✅ Loaded {len(df)} candles")
        print(f"Date range: {df['time'].iloc[0]} to {df['time'].iloc[-1]}")
        print("-" * 70)
        print("🔍 Running backtest...")
        print("-" * 70)

        # Iterate through bars
        for i in range(100, len(df)):  # Start after warm-up period
            current_bar = df.iloc[i]
            current_time = current_bar['time']

            # Check for entry signal
            should_enter, direction, entry, sl, tp = self.check_entry_signal(df, i)

            if should_enter:
                # Simulate the trade
                exit_price, exit_reason, exit_bar, pnl = self.simulate_trade(
                    df, i, direction, entry, sl, tp
                )

                exit_time = df.iloc[exit_bar]['time']
                duration_minutes = (exit_bar - i) * 5

                # Update balance
                self.balance += pnl
                self.equity = self.balance

                # Record trade
                trade = {
                    "entry_time": current_time,
                    "exit_time": exit_time,
                    "direction": direction,
                    "entry_price": entry,
                    "exit_price": exit_price,
                    "sl": sl,
                    "tp": tp,
                    "pnl": pnl,
                    "exit_reason": exit_reason,
                    "duration_min": duration_minutes,
                    "balance_after": self.balance
                }

                self.trades.append(trade)

                # Daily P&L tracking
                day = current_time.date()
                if day not in self.daily_pnl:
                    self.daily_pnl[day] = 0
                self.daily_pnl[day] += pnl

                # Print trade details
                if TestConfig.SHOW_EACH_TRADE:
                    result = "WIN ✅" if pnl > 0 else "LOSS ❌"
                    print(f"[{current_time}] {direction} {result}")
                    print(f"  Entry: {entry:.2f} | Exit: {exit_price:.2f} | {exit_reason}")
                    print(f"  P&L: ${pnl:+.2f} | Balance: ${self.balance:.2f}")
                    print(f"  Duration: {duration_minutes} min")
                    print("-" * 70)

        mt5.shutdown()

        # Generate report
        return self.generate_report()

    def generate_report(self):
        """Generate comprehensive backtest report"""

        if len(self.trades) == 0:
            print("⚠️  No trades executed during test period")
            return None

        # Calculate statistics
        total_trades = len(self.trades)
        wins = [t for t in self.trades if t['pnl'] > 0]
        losses = [t for t in self.trades if t['pnl'] < 0]

        win_count = len(wins)
        loss_count = len(losses)
        win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0

        total_pnl = sum(t['pnl'] for t in self.trades)
        gross_profit = sum(t['pnl'] for t in wins)
        gross_loss = abs(sum(t['pnl'] for t in losses))

        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 0

        avg_win = (gross_profit / win_count) if win_count > 0 else 0
        avg_loss = (gross_loss / loss_count) if loss_count > 0 else 0

        largest_win = max((t['pnl'] for t in wins), default=0)
        largest_loss = min((t['pnl'] for t in losses), default=0)

        # Calculate maximum drawdown
        running_balance = TestConfig.STARTING_BALANCE
        peak = TestConfig.STARTING_BALANCE
        max_dd = 0

        for trade in self.trades:
            running_balance += trade['pnl']
            if running_balance > peak:
                peak = running_balance
            dd = peak - running_balance
            if dd > max_dd:
                max_dd = dd

        max_dd_percent = (max_dd / peak * 100) if peak > 0 else 0

        # Print report
        print("\n" + "=" * 70)
        print("📊 BACKTEST RESULTS")
        print("=" * 70)
        print(f"Test Period: {TestConfig.START_DATE.date()} to {TestConfig.END_DATE.date()}")
        print(f"Symbol: {Config.SYMBOL} | Timeframe: M5 | Lot: {Config.FIXED_LOT_SIZE}")
        print("-" * 70)
        print("PERFORMANCE SUMMARY:")
        print(f"  Starting Balance: ${TestConfig.STARTING_BALANCE:,.2f}")
        print(f"  Final Balance: ${self.balance:,.2f}")
        print(f"  Total P&L: ${total_pnl:+,.2f} ({total_pnl/TestConfig.STARTING_BALANCE*100:+.2f}%)")
        print(f"  Max Drawdown: ${max_dd:,.2f} ({max_dd_percent:.2f}%)")
        print("-" * 70)
        print("TRADE STATISTICS:")
        print(f"  Total Trades: {total_trades}")
        print(f"  Wins: {win_count} ({win_rate:.2f}%)")
        print(f"  Losses: {loss_count}")
        print(f"  Profit Factor: {profit_factor:.2f}")
        print("-" * 70)
        print("P&L BREAKDOWN:")
        print(f"  Gross Profit: ${gross_profit:,.2f}")
        print(f"  Gross Loss: ${gross_loss:,.2f}")
        print(f"  Average Win: ${avg_win:,.2f}")
        print(f"  Average Loss: ${avg_loss:,.2f}")
        print(f"  Largest Win: ${largest_win:,.2f}")
        print(f"  Largest Loss: ${largest_loss:,.2f}")
        print("=" * 70)

        # Exit reasons breakdown
        exit_reasons = {}
        for trade in self.trades:
            reason = trade['exit_reason']
            if reason not in exit_reasons:
                exit_reasons[reason] = 0
            exit_reasons[reason] += 1

        print("EXIT REASONS:")
        for reason, count in exit_reasons.items():
            print(f"  {reason}: {count} ({count/total_trades*100:.1f}%)")
        print("=" * 70)

        # FTMO Challenge Assessment
        print("\n🎯 FTMO CHALLENGE ASSESSMENT:")
        if total_pnl >= 800:
            print(f"  ✅ PROFIT TARGET: ${total_pnl:.2f} >= $800 ✓")
        else:
            print(f"  ❌ PROFIT TARGET: ${total_pnl:.2f} < $800 ✗")

        if max_dd <= 500:
            print(f"  ✅ MAX DAILY LOSS: ${max_dd:.2f} <= $500 ✓")
        else:
            print(f"  ❌ MAX DAILY LOSS: ${max_dd:.2f} > $500 ✗")

        if total_pnl >= 800 and max_dd <= 500:
            print("\n  🏆 RESULT: WOULD PASS FTMO PHASE 1! 🏆")
        else:
            print("\n  ❌ RESULT: Would not pass FTMO Phase 1")

        print("=" * 70)

        # Save detailed report
        report_data = {
            "test_period": {
                "start": str(TestConfig.START_DATE),
                "end": str(TestConfig.END_DATE)
            },
            "summary": {
                "starting_balance": TestConfig.STARTING_BALANCE,
                "final_balance": self.balance,
                "total_pnl": total_pnl,
                "max_drawdown": max_dd,
                "max_drawdown_percent": max_dd_percent
            },
            "statistics": {
                "total_trades": total_trades,
                "wins": win_count,
                "losses": loss_count,
                "win_rate": win_rate,
                "profit_factor": profit_factor,
                "avg_win": avg_win,
                "avg_loss": avg_loss,
                "largest_win": largest_win,
                "largest_loss": largest_loss
            },
            "exit_reasons": exit_reasons,
            "trades": self.trades
        }

        # Save JSON report
        with open(TestConfig.REPORT_FILE, 'w') as f:
            json.dump(report_data, f, indent=2, default=str)

        print(f"\n📄 Detailed report saved to: {TestConfig.REPORT_FILE}")

        # Save trades to CSV
        trades_df = pd.DataFrame(self.trades)
        trades_df.to_csv(TestConfig.TRADE_CSV, index=False)
        print(f"📄 Trade list saved to: {TestConfig.TRADE_CSV}")

        return report_data


# ============================================================
# MAIN
# ============================================================

def main():
    """Run strategy tester"""

    print("=" * 70)
    print("🧪 MT5 STRATEGY TESTER - Sniper Bot Analysis")
    print("=" * 70)
    print()

    tester = StrategyTester()
    report = tester.run_backtest()

    if report:
        print("\n✅ Backtest completed successfully!")
    else:
        print("\n❌ Backtest failed or no trades executed")


if __name__ == "__main__":
    main()
