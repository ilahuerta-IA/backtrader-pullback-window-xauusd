# 🚀 MT5 Deployment Guide - Choose Your Path

You now have **TWO complete implementations** of the XAUUSD Sniper strategy:

1. **Python Bot** (Recommended for testing/analysis)
2. **MQL5 Expert Advisor** (Recommended for live MT5 trading)

---

## 📊 OPTION 1: Python Bot (mt5_xauusd_sniper.py)

### Advantages
✅ Easy to test and modify
✅ Built-in backtesting (`mt5_strategy_tester.py`)
✅ Detailed logging and JSON reports
✅ Can run on any computer with Python
✅ Great for learning and debugging

### Setup (5 minutes)
```bash
# 1. Install Python library
pip install MetaTrader5 pandas numpy

# 2. Run backtest first
python mt5_strategy_tester.py

# 3. Start live bot
python mt5_xauusd_sniper.py
```

### Best For
- Testing and validation
- Strategy development
- Detailed analysis and reporting
- Running on remote servers

---

## ⚡ OPTION 2: MQL5 Expert Advisor (XAUUSD_Sniper_EA.mq5)

### Advantages
✅ Native MT5 integration (faster execution)
✅ Works directly in MT5 terminal
✅ No external dependencies
✅ Standard EA features (MT5 strategy tester)
✅ VPS-ready

### Setup (10 minutes)

#### Step 1: Compile the EA

1. **Open MT5 Terminal**
2. Press **F4** (opens MetaEditor)
3. **File → Open** → Select `XAUUSD_Sniper_EA.mq5`
4. Press **F7** (Compile)
5. Check for "0 error(s), 0 warning(s)" at bottom

#### Step 2: Load on Chart

1. **Open XAUUSD M5 chart** in MT5
2. **Navigator panel (Ctrl+N)** → Expert Advisors
3. **Drag `XAUUSD_Sniper_EA`** onto the chart
4. **Enable AutoTrading** (button at top)

#### Step 3: Configure Settings

**Critical Settings to Verify:**
```
=== POSITION SIZING ===
FixedLotSize = 0.10          ← MUST be 0.10
MaxSlippage = 50

=== DAILY LIMITS ===
DailyProfitTarget = 100.0    ← $100/day
DailyLossLimit = 100.0       ← $100/day max loss
MaxTradesPerDay = 3

=== ATR & STOPS ===
SL_ATR_Multiplier = 1.0      ⚠️ CRITICAL: Changed from 2.5
TP_ATR_Multiplier = 1.5      ⚠️ CRITICAL: Changed from 3.5
MinStopPoints = 10
UseBreakeven = true

=== HTF BIAS FILTER ===
UseHTFBias = true
HTF_Timeframe = PERIOD_H1

=== SESSION FILTER ===
UseSessionFilter = true
LondonStartHour = 7          ← UTC time
NYStartHour = 13
```

### Best For
- Live trading on FTMO accounts
- VPS deployment
- Standard MT5 strategy testing
- Automatic execution

---

## 🎯 RECOMMENDED WORKFLOW

### Phase 1: Python Backtesting (Day 1)
```bash
# Test strategy on historical data
python mt5_strategy_tester.py
```

**What to Check:**
- Win rate >40%
- Profit factor >1.3
- Max drawdown <$500
- Total P&L positive

**If Passed:** Proceed to Phase 2
**If Failed:** Adjust parameters in both files

### Phase 2: Python Demo Testing (Week 1)
```bash
# Run live demo with Python bot
python mt5_xauusd_sniper.py
```

**What to Monitor:**
- First trade is 0.10 lots (NOT 0.96!)
- Daily limits trigger correctly
- Breakeven stops activate
- Session filter works
- HTF bias filtering

**After 3-5 days:** Review performance, adjust if needed

### Phase 3: MQL5 EA Testing (Week 2)
1. Load EA on demo account (M5 chart)
2. Run for 1 week
3. Compare results to Python bot
4. Should be very similar

### Phase 4: FTMO Deployment (Week 3)
**Choose ONE implementation:**
- Python bot (if you want detailed logs)
- MQL5 EA (if you want native MT5 execution)

---

## 🔧 KEY DIFFERENCES BETWEEN VERSIONS

| Feature | Python Bot | MQL5 EA |
|---------|-----------|---------|
| **Entry Logic** | 4-phase state machine | 4-phase state machine |
| **Fixed Lot Size** | ✅ 0.10 lots | ✅ 0.10 lots |
| **Daily Limits** | ✅ $100/$100 | ✅ $100/$100 |
| **Breakeven** | ✅ At 50% to TP | ✅ At 50% to TP |
| **HTF Bias** | ✅ H1 EMA filter | ✅ H1 EMA filter |
| **Session Filter** | ✅ London/NY | ✅ London/NY |
| **Circuit Breaker** | ✅ 2 losses | ✅ 2 losses |
| **Logging** | Detailed JSON files | MT5 journal |
| **Backtesting** | Custom Python script | MT5 strategy tester |
| **Speed** | Good (milliseconds) | Excellent (microseconds) |
| **Setup** | Requires Python | Just MT5 |

---

## ⚠️ CRITICAL PARAMETER CHANGE IN MQL5 EA

**IMPORTANT:** The MQL5 EA has DIFFERENT default ATR multipliers:

### Python Bot (mt5_xauusd_sniper.py):
```python
ATR_SL_MULTIPLIER = 2.5
ATR_TP_MULTIPLIER = 3.5
```

### MQL5 EA (XAUUSD_Sniper_EA.mq5):
```cpp
SL_ATR_Multiplier = 1.0    // ⚠️ DIFFERENT!
TP_ATR_Multiplier = 1.5    // ⚠️ DIFFERENT!
```

**Why the Difference?**
The MQL5 EA uses TIGHTER stops (1.0× ATR vs 2.5× ATR). This means:
- **Smaller losses** per trade
- **Higher win rate needed** to be profitable
- **May get stopped out more often**

**Recommendation:**
Test BOTH approaches:
1. **Conservative** (Python): 2.5× ATR SL, 3.5× TP
2. **Aggressive** (MQL5): 1.0× ATR SL, 1.5× TP

Or **standardize** them:
```cpp
// Make MQL5 match Python
SL_ATR_Multiplier = 2.5
TP_ATR_Multiplier = 3.5
```

---

## 🧪 TESTING THE MQL5 EA

### MT5 Strategy Tester (Built-in)

1. **Open MT5 → View → Strategy Tester** (Ctrl+R)
2. **Select Expert Advisor:** XAUUSD_Sniper_EA
3. **Symbol:** XAUUSD
4. **Period:** M5
5. **Date Range:** 2026.01.01 to 2026.01.03
6. **Execution:** Every tick (most accurate)
7. **Start**

**Expected Results:**
- Should match Python backtest results (if using same parameters)
- Win rate >40%
- Profit factor >1.3

### Visual Mode
Enable "Visual mode" checkbox to watch EA trade in real-time on chart.

---

## 📋 PRE-DEPLOYMENT CHECKLIST

### Both Versions
- [ ] Starting balance: $10,000 (demo)
- [ ] Fixed lot size: 0.10
- [ ] Daily profit target: $100
- [ ] Daily loss limit: $100
- [ ] Max trades/day: 3
- [ ] HTF bias: ENABLED
- [ ] Session filter: ENABLED
- [ ] Circuit breaker: ENABLED

### Python Bot Specific
- [ ] MT5 credentials configured
- [ ] Python packages installed
- [ ] Backtest completed successfully
- [ ] Log files being created

### MQL5 EA Specific
- [ ] EA compiled without errors
- [ ] Loaded on XAUUSD M5 chart
- [ ] AutoTrading enabled (button at top)
- [ ] Parameters configured correctly
- [ ] Tested in Strategy Tester

---

## 🎯 WHICH ONE SHOULD YOU USE?

### Use Python Bot If:
- You want detailed logging and analysis
- You're comfortable with Python
- You want to customize logic easily
- You need remote execution (VPS without MT5)
- You want JSON trade journals

### Use MQL5 EA If:
- You want native MT5 execution (faster)
- You prefer standard MT5 workflow
- You want to use MT5 strategy tester
- You plan to run on MT5 VPS
- You want "set it and forget it" execution

### Use BOTH If:
- You want to validate consistency
- One as primary, one as backup
- Compare performance
- Learn the differences

**Most traders choose:** MQL5 EA for live trading, Python for analysis

---

## 🚨 COMMON ISSUES & FIXES

### MQL5 EA Issues

**Issue: EA not trading**
```
Fixes:
1. Check AutoTrading button (must be green)
2. Check "Expert Advisors" allowed in Tools → Options → Expert Advisors
3. Check session time (must be 7-16 or 13-20 UTC)
4. Check HTF bias (H1 must confirm trend)
```

**Issue: "Not enough money" error**
```
Fixes:
1. Reduce lot size to 0.01 (for small accounts)
2. Check account balance vs margin requirements
3. Verify broker allows XAUUSD trading
```

**Issue: Stops too tight, always hit**
```
Fixes:
1. Increase SL_ATR_Multiplier to 2.5
2. Increase MinStopPoints to 20
3. Check broker's minimum stop level
```

### Python Bot Issues

**Issue: "MT5 initialization failed"**
```
Fixes:
1. Ensure MT5 terminal is running
2. Install: pip install MetaTrader5
3. Check MT5 terminal is logged in
```

**Issue: "Login failed"**
```
Fixes:
1. Verify credentials in Config section
2. Check server name spelling
3. Try leaving credentials blank (use logged-in terminal)
```

---

## 📊 MONITORING & LOGS

### Python Bot Logs
```
ftmo_sniper_log.txt        - Real-time activity
ftmo_trade_journal.json    - All trades (structured)
ftmo_daily_summary.json    - Daily P&L summary
```

### MQL5 EA Logs
```
MT5 → Tools → Options → Journal
- Check "Experts" tab for EA messages
- All Print() statements appear here
```

---

## 🎓 NEXT STEPS

### TODAY:
1. ✅ Compile MQL5 EA
2. ✅ Run Python backtest
3. ✅ Compare results (should be similar)

### THIS WEEK:
1. Choose primary implementation
2. Start demo testing
3. Monitor first 10 trades
4. Verify all safety features

### WEEK 2:
1. Analyze demo performance
2. Optimize if needed
3. Build confidence

### WEEK 3:
1. Deploy to FTMO challenge
2. Target $100/day
3. Pass Phase 1! 🏆

---

## 🔗 FILE REFERENCE

### Core Strategy Files
```
mt5_xauusd_sniper.py          - Python bot (enhanced)
mt5_xauusd_bot.py             - Python bot (basic)
mt5_strategy_tester.py        - Python backtester
XAUUSD_Sniper_EA.mq5          - MQL5 Expert Advisor
```

### Documentation
```
IMPLEMENTATION_GUIDE.md       - Complete how-to
MT5_STRATEGY_ANALYSIS.md      - Deep analysis
FTMO_SNIPER_STRATEGY.md       - Tactical plan
PROJECT_SUMMARY.md            - Overview
QUICK_START.md                - Quick reference
README_MT5_DEPLOYMENT.md      - This file
```

---

**You're now equipped with BOTH Python and MQL5 implementations!** 🎉

**Choose your weapon and start testing!** ⚡

**Good luck with FTMO!** 🎯💰

---

*MT5 Deployment Guide - January 3, 2026*
*Version 1.0 - Python + MQL5*
