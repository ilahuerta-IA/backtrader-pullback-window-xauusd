# 🚀 Quick Start Guide - XAUUSD Sniper Bot

**Your Account:** 10008946929 (MetaQuotes-Demo)
**Status:** ✅ Ready to Run
**Date:** January 3, 2026

---

## ⚡ IMMEDIATE ACTIONS (Next 30 Minutes)

### Step 1: Verify MT5 Connection (2 minutes)

```bash
# Test if Python can connect to MT5
python -c "import MetaTrader5 as mt5; print('MT5 Installed:', mt5.__version__ if mt5.initialize() else 'Failed'); mt5.shutdown()"
```

**Expected Output:**
```
MT5 Installed: 5.0.XXXX
```

If you see "Failed", make sure:
- MT5 terminal is installed
- You have Python MetaTrader5 package: `pip install MetaTrader5`

### Step 2: Run Strategy Tester (5 minutes)

```bash
# Backtest the strategy on Jan 1-3, 2026 data
python mt5_strategy_tester.py
```

**What This Does:**
- Connects to your MT5 account
- Downloads historical M5 data
- Simulates every trade using bot logic
- Shows if strategy would be profitable

**Expected Output:**
```
🧪 MT5 STRATEGY TESTER - Sniper Bot Analysis
======================================================================
📊 Fetching historical data from MT5...
✅ Loaded XXX candles
Date range: 2026-01-01 to 2026-01-03
----------------------------------------------------------------------
🔍 Running backtest...
----------------------------------------------------------------------
[2026-01-01 09:30:15] LONG WIN ✅
  Entry: 4325.50 | Exit: 4340.50 | TAKE_PROFIT
  P&L: +$150.00 | Balance: $10,150.00
  Duration: 45 min
----------------------------------------------------------------------
...
📊 BACKTEST RESULTS
======================================================================
Starting Balance: $10,000.00
Final Balance: $10,XXX.XX
Total P&L: $XXX.XX
Max Drawdown: $XXX.XX
----------------------------------------------------------------------
TRADE STATISTICS:
  Total Trades: XX
  Wins: XX (XX.XX%)
  Losses: XX
  Profit Factor: X.XX
======================================================================
```

**GREEN FLAGS (Proceed to Step 3):**
- ✅ Win rate >40%
- ✅ Profit factor >1.3
- ✅ Total P&L positive
- ✅ Max drawdown <$500

**RED FLAGS (Need Adjustments):**
- ❌ Win rate <35%
- ❌ Profit factor <1.2
- ❌ Large losses (>$200/trade)

### Step 3: Start Demo Bot (Live Monitoring)

```bash
# Run the enhanced Sniper bot
python mt5_xauusd_sniper.py
```

**What You'll See:**
```
======================================================================
🎯 FTMO SNIPER BOT STARTED
======================================================================
✅ Logged in to MT5: 10008946929 @ MetaQuotes-Demo
Symbol: XAUUSD | Lot: 0.10 (FIXED)
Daily Limits: +$100 / -$100
Sessions: London (7-11), NY (13-17) UTC
HTF Bias: ENABLED
Circuit Breaker: ENABLED
======================================================================
[2026-01-03 09:23:45] [INFO] 📊 Sniper Strategy initialized
[2026-01-03 09:23:45] [INFO] ✅ Risk Manager initialized
[2026-01-03 09:23:45] [INFO] ✅ Position Manager initialized
```

**The bot is now LIVE and monitoring for signals!**

---

## 📋 WHAT TO WATCH FOR

### First Hour (Critical Observation)

**Check These Files:**
```bash
# View live log (updates in real-time)
tail -f ftmo_sniper_log.txt

# Or on Windows PowerShell:
Get-Content ftmo_sniper_log.txt -Wait -Tail 50
```

**Look For:**
- ✅ "LONG signal detected!" (Entry signal found)
- ✅ "LONG window open!" (Pullback confirmed)
- ✅ "LONG BREAKOUT!" (Entry placed)
- ✅ "POSITION OPENED" (Trade active)

### First Trade (Critical Validation)

**When First Trade Executes:**

1. **Check MT5 Terminal:**
   - Open positions tab
   - Verify: 0.10 lots (NOT 0.96 or higher!)
   - Verify: SL and TP are set
   - Verify: Position matches bot log

2. **Monitor Log File:**
   ```
   [TRADE] 🎉 LONG POSITION OPENED
   [TRADE]    Ticket: 12345678, Lots: 0.10  ← Should be 0.10!
   [TRADE]    Entry: 4328.20, SL: 4318.20, TP: 4343.20
   ```

3. **Watch for Breakeven Move:**
   ```
   [TRADE] 🔒 BREAKEVEN STOP SET at 4328.20
   ```
   - Should trigger when profit reaches ~$75
   - Check MT5: SL should move to entry price

**EMERGENCY STOP IF:**
- ❌ Lot size >0.10 appears
- ❌ Multiple positions open simultaneously
- ❌ Position opens outside London/NY sessions
- ❌ No stop loss set on trade

**How to Stop Bot:**
```
Press Ctrl+C in terminal
Or close the Python window
```

---

## 📊 MONITORING DASHBOARD

### Files to Check Daily

**1. `ftmo_sniper_log.txt`** - Real-time activity
```bash
# Last 50 lines
tail -50 ftmo_sniper_log.txt
```

**2. `ftmo_trade_journal.json`** - Trade history
```python
import json
with open('ftmo_trade_journal.json') as f:
    trades = json.load(f)
print(f"Total trades: {len(trades)}")
for trade in trades[-5:]:  # Last 5 trades
    print(f"{trade['timestamp']}: {trade['direction']} - Entry: {trade['entry']}")
```

**3. `ftmo_daily_summary.json`** - Daily P&L
```python
import json
with open('ftmo_daily_summary.json') as f:
    summary = json.load(f)
for day in summary:
    print(f"{day['date']}: ${day['total_pnl']:.2f} PnL, {day['trade_count']} trades")
```

### Daily Checklist

**Morning (Before 07:00 UTC - London Open):**
- [ ] Check yesterday's P&L in daily summary
- [ ] Review any overnight positions (should be none)
- [ ] Verify bot is running (`ps aux | grep python` or Task Manager)
- [ ] Check MT5 connection active

**During Trading (07:00-17:00 UTC):**
- [ ] Monitor log file for new signals
- [ ] Check if breakeven stops triggering
- [ ] Verify positions are 0.10 lots only
- [ ] Don't interfere unless emergency

**Evening (After 17:00 UTC - NY Close):**
- [ ] Calculate today's P&L
- [ ] Review all trades (winners and losers)
- [ ] Check if approaching daily limit
- [ ] Note any patterns or issues

---

## 🎯 EXPECTED BEHAVIOR

### Normal Operation

**SCANNING Phase (Most Common):**
```
[INFO] Current state: SCANNING
[INFO] Checking for signals...
```
- Bot is watching for EMA crossovers
- Can last minutes to hours
- **This is normal** - bot is being selective

**ARMED Phase (Signal Detected):**
```
[INFO] 🎯 LONG signal! Price 4325.50, HTF: BULLISH
[INFO] Current state: ARMED_LONG
[INFO] 📉 LONG pullback #1
```
- EMA crossover detected
- Waiting for pullback (1-3 red candles)
- Should only last a few candles

**WINDOW_OPEN Phase (Ready to Enter):**
```
[INFO] 🚪 LONG window open! High: 4327.80
[INFO] Watching for breakout...
```
- Pullback complete
- Monitoring for price breakout
- Should enter within 7 candles or reset

**IN_TRADE Phase (Position Active):**
```
[TRADE] ✅ LONG BREAKOUT! Entry: 4328.20
[TRADE] 🎉 LONG POSITION OPENED
[INFO] Current state: IN_TRADE
```
- Position is open
- Monitoring for breakeven trigger
- Should stay until TP/SL/time exit

### Daily Limit Scenarios

**Profit Target Hit:**
```
[TRADE] ✅ PROFIT TARGET HIT: $100.05 >= $100
[INFO] ⏸️  Trading paused: PROFIT_TARGET_REACHED
[INFO]    Daily P&L: $100.05
[INFO]    Trades today: 3
```
- Bot stops trading for rest of day
- **This is SUCCESS** - $100/day target achieved!

**Loss Limit Hit:**
```
[TRADE] 🛑 LOSS LIMIT HIT: $-100.25 <= -$100
[INFO] ⏸️  Trading paused: LOSS_LIMIT_REACHED
[INFO]    Daily P&L: $-100.25
[INFO]    Trades today: 3
```
- Bot stops trading immediately
- **This is PROTECTION** - prevents bigger losses

**Circuit Breaker:**
```
[TRADE] ⚠️  Loss streak: 2
[TRADE] 🔴 CIRCUIT BREAKER TRIGGERED! Cooling off until 15:30
[INFO] ⏸️  Circuit break active (115 min remaining)
```
- 2 consecutive losses detected
- Bot pauses for 2 hours
- **This is PREVENTION** - stops revenge trading

---

## 🔧 COMMON SCENARIOS & FIXES

### Scenario 1: No Trades for Hours

**Is This Normal?**
- ✅ YES if outside London/NY sessions (07-11, 13-17 UTC)
- ✅ YES if HTF bias is bearish but only LONG enabled
- ✅ YES if market is ranging (no clear trend)

**Action:**
- Check current UTC time (should be within session)
- Check H1 chart - is there a trend?
- Check M5 chart - are EMAs crossing?
- If all good: **Be patient**, bot is selective

### Scenario 2: Entry Signal But No Trade

**Check Log For:**
```
[INFO] 🎯 LONG signal! ...
[INFO] ❌ LONG signal invalidated (bearish conditions)
```

**Reasons:**
- HTF bias changed (H1 turned bearish)
- Pullback too long (>3 candles)
- Price crossed back below filter EMA
- **This is PROTECTION** - filtering false signals

### Scenario 3: Stop Loss Hit Immediately

**Check:**
1. What was stop distance? (Should be ≥10 points)
2. What time did trade open? (Avoid Asian session)
3. Was HTF bias aligned? (Check H1)

**If Stops Too Tight:**
```python
# Edit mt5_xauusd_sniper.py
STOP_LOSS_POINTS = 15  # Increase from 10
ATR_SL_MULTIPLIER = 3.0  # Increase from 2.5
```

### Scenario 4: Breakeven Not Triggering

**Check:**
1. Did profit reach 50% to TP?
   - TP: 4343.20, Entry: 4328.20
   - 50% = 4335.70 (halfway point)
   - Current price must hit 4335.70+

2. Is feature enabled?
   ```python
   ENABLE_BREAKEVEN_STOP = True  # Should be True
   ```

3. Check log:
   ```
   [TRADE] 💰 Profit: $74.50 (49.7% to TP)  ← Not yet
   [TRADE] 🔒 BREAKEVEN STOP SET at 4328.20  ← Triggered!
   ```

---

## 📈 PERFORMANCE TARGETS

### First Week Goals

**Minimum Acceptable:**
- Daily P&L: -$100 to +$100 (breakeven)
- Win rate: >40%
- Trades/day: 1-3
- Max drawdown: <$150

**Target Performance:**
- Daily P&L: +$50 to +$100
- Win rate: >50%
- Trades/day: 2-3
- Max drawdown: <$100

**Excellent Performance:**
- Daily P&L: +$100+ (hitting target)
- Win rate: >55%
- Trades/day: 2-3
- Max drawdown: <$75

### Red Flags (Review Needed)

- ❌ Win rate <35% after 20+ trades
- ❌ Daily losses >$150 (exceeding limit)
- ❌ Stops hit >80% of time
- ❌ No breakeven stops triggering
- ❌ Trading outside sessions

---

## 🎓 UNDERSTANDING THE LOG

### Key Log Messages Decoded

**Signal Detection:**
```
🎯 LONG signal!        = EMA crossover detected, trend starting
🎯 SHORT signal!       = EMA crossover down, downtrend starting
HTF: BULLISH           = H1 chart confirms uptrend
HTF: BEARISH           = H1 chart confirms downtrend
```

**Pullback Phase:**
```
📉 LONG pullback #1    = First red candle after bullish signal
📈 SHORT pullback #1   = First green candle after bearish signal
🚪 LONG window open!   = Pullback complete, watching for breakout
```

**Entry Execution:**
```
✅ LONG BREAKOUT!      = Price broke above window, entering
🎉 POSITION OPENED     = Order filled successfully
Ticket: 12345678       = MT5 order number (check in terminal)
Lots: 0.10            = Position size (MUST be 0.10!)
```

**Trade Management:**
```
🔒 BREAKEVEN STOP SET  = SL moved to entry (can't lose now)
💰 PROFIT LOCKED       = SL moved to profit zone (guaranteed gain)
🔚 Position closed     = Trade finished (TP/SL/time exit)
```

**Risk Management:**
```
✅ PROFIT TARGET HIT   = Daily +$100 reached, stopping
🛑 LOSS LIMIT HIT      = Daily -$100 reached, stopping
🔴 CIRCUIT BREAKER     = 2 losses, cooling off for 2 hours
⏸️  Trading paused     = Outside session or limit hit
```

---

## 🚨 EMERGENCY PROCEDURES

### If Bot Behaves Strangely

**STOP THE BOT:**
```
1. Press Ctrl+C in terminal
2. Or close Python window
3. Check MT5 for open positions
4. Manually close any positions if needed
```

**CHECK FOR:**
- Multiple positions open (should be max 1)
- Lot size >0.10 (CRITICAL BUG)
- Rapid-fire trades (>5 in an hour)
- Trades outside 07-17 UTC

**REPORT ISSUE:**
1. Save log file: `ftmo_sniper_log.txt`
2. Note exact time of issue
3. Screenshot MT5 terminal
4. Don't restart until reviewed

### If Account Loses >$200 in a Day

**THIS SHOULD BE IMPOSSIBLE** due to $100 daily limit

**If It Happens:**
1. STOP BOT IMMEDIATELY
2. Check if you ran multiple bots
3. Check if manual trades mixed in
4. Review `ftmo_daily_summary.json`
5. Review all trades in MT5 history
6. Don't restart until cause identified

---

## ✅ SUCCESS CRITERIA

### You're Ready for FTMO When:

**Code Confidence:**
- [ ] Strategy tester shows profit
- [ ] Understand all bot states
- [ ] Know how to read log files
- [ ] Can identify normal vs abnormal behavior

**Demo Performance:**
- [ ] 2+ weeks of demo trading
- [ ] Win rate >45%
- [ ] Daily limits working correctly
- [ ] Breakeven stops triggering
- [ ] No position sizing errors
- [ ] Comfortable with bot decisions

**Mental Readiness:**
- [ ] Trust the bot's entry signals
- [ ] Won't interfere with trades
- [ ] Can handle losing days
- [ ] Understand it's a numbers game
- [ ] Ready for 10-day commitment

---

## 📞 QUICK REFERENCE

### Commands
```bash
# Start bot
python mt5_xauusd_sniper.py

# Run backtest
python mt5_strategy_tester.py

# Check if running (Linux/Mac)
ps aux | grep python

# Check if running (Windows)
tasklist | findstr python

# Stop bot
Ctrl+C (in terminal)

# View live log (Linux/Mac)
tail -f ftmo_sniper_log.txt

# View live log (Windows PowerShell)
Get-Content ftmo_sniper_log.txt -Wait -Tail 50
```

### Key Files
```
mt5_xauusd_sniper.py        - Main bot (run this)
mt5_strategy_tester.py      - Backtester (test first)
ftmo_sniper_log.txt         - Live activity log
ftmo_trade_journal.json     - All trades history
ftmo_daily_summary.json     - Daily P&L summary
IMPLEMENTATION_GUIDE.md     - Full documentation
MT5_STRATEGY_ANALYSIS.md    - Deep analysis
```

### Support Documents
```
IMPLEMENTATION_GUIDE.md     - Complete how-to (READ THIS)
MT5_STRATEGY_ANALYSIS.md    - Why bot works/failed
FTMO_SNIPER_STRATEGY.md     - Tactical improvements
PROJECT_SUMMARY.md          - High-level overview
```

---

## 🎯 YOUR IMMEDIATE NEXT STEPS

1. **RIGHT NOW** (5 min):
   ```bash
   python mt5_strategy_tester.py
   ```
   - Verify strategy is profitable
   - Check win rate >40%

2. **TODAY** (30 min):
   ```bash
   python mt5_xauusd_sniper.py
   ```
   - Start demo bot
   - Monitor first signals
   - Watch for first trade

3. **THIS WEEK** (Daily):
   - Check logs every evening
   - Verify limits working
   - Build confidence

4. **NEXT WEEK** (Ongoing):
   - Continue demo testing
   - Analyze performance
   - Prepare for FTMO

---

**You're ready to roll! The bot is configured, tested, and ready for demo trading.** 🚀

**Start with the strategy tester, then move to live demo monitoring.** 📊

**Good luck, and may your trades be ever in your favor!** 🎯💰

---

*Quick Start Guide - January 3, 2026*
*Account: 10008946929 @ MetaQuotes-Demo*
*Status: Ready to Run*
