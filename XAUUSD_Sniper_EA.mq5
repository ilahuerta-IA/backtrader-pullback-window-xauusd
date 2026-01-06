//+------------------------------------------------------------------+
//|                                            XAUUSD_Sniper_EA.mq5 |
//|                              FTMO-Ready Sunrise OGLE Strategy EA |
//|                                       Based on 4-Phase Entry Logic |
//+------------------------------------------------------------------+
#property copyright "Andy Warui"
#property link      ""
#property version   "1.00"
#property strict

//--- Input Parameters
input group "=== POSITION SIZING ==="
input double   FixedLotSize = 0.10;           // Fixed Lot Size (NEVER changes)
input int      MaxSlippage = 50;              // Max Slippage (points)

input group "=== DAILY LIMITS ==="
input double   DailyProfitTarget = 100.0;     // Daily Profit Target ($)
input double   DailyLossLimit = 100.0;        // Daily Loss Limit ($)
input int      MaxTradesPerDay = 3;           // Max Trades Per Day

input group "=== EMA SETTINGS ==="
input int      EMA_Fast = 1;                  // Fast EMA Period
input int      EMA_Slow1 = 14;                // Slow EMA 1 Period
input int      EMA_Slow2 = 18;                // Slow EMA 2 Period
input int      EMA_Slow3 = 24;                // Slow EMA 3 Period
input int      EMA_Filter = 100;              // Price Filter EMA

input group "=== ATR & STOPS ==="
input int      ATR_Period = 10;               // ATR Period
input double   SL_ATR_Multiplier = 1.0;       // Stop Loss ATR Multiplier
input double   TP_ATR_Multiplier = 1.5;       // Take Profit ATR Multiplier
input int      MinStopPoints = 10;            // Minimum Stop Loss (points)
input bool     UseBreakeven = true;           // Enable Breakeven at 50% to TP
input double   Breakeven_Percent = 0.5;       // Breakeven at % to TP

input group "=== HTF BIAS FILTER ==="
input bool     UseHTFBias = true;             // Enable H1 Trend Filter
input ENUM_TIMEFRAMES HTF_Timeframe = PERIOD_H1; // HTF Timeframe
input int      HTF_EMA_Fast = 20;             // HTF Fast EMA
input int      HTF_EMA_Slow = 50;             // HTF Slow EMA

input group "=== SESSION FILTER ==="
input bool     UseSessionFilter = true;       // Enable Session Filter
input int      LondonStartHour = 7;           // London Start (UTC)
input int      LondonEndHour = 16;            // London End (UTC)
input int      NYStartHour = 13;              // New York Start (UTC)
input int      NYEndHour = 20;                // New York End (UTC)

input group "=== CIRCUIT BREAKER ==="
input bool     EnableCircuitBreaker = true;   // Enable Loss Circuit Breaker
input int      ConsecutiveLossLimit = 2;      // Stop After N Consecutive Losses

//--- Global Variables
datetime lastBarTime = 0;
double dayStartBalance = 0;
int todayTrades = 0;
int consecutiveLosses = 0;
datetime lastTradeDate = 0;

// EMA Handles
int emaFastHandle, emaSlow1Handle, emaSlow2Handle, emaSlow3Handle, emaFilterHandle;
int atrHandle;
int htfEmaFastHandle, htfEmaSlowHandle;

// Entry State Machine
enum EntryState {
   STATE_SCANNING,      // Looking for opportunity
   STATE_ARMED,         // Conditions met, waiting for window
   STATE_WINDOW_OPEN,   // Entry window is open
   STATE_ENTRY          // Trade entered
};

EntryState currentState = STATE_SCANNING;
datetime lastStateChange = 0;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   // Initialize indicators
   emaFastHandle = iMA(_Symbol, PERIOD_CURRENT, EMA_Fast, 0, MODE_EMA, PRICE_CLOSE);
   emaSlow1Handle = iMA(_Symbol, PERIOD_CURRENT, EMA_Slow1, 0, MODE_EMA, PRICE_CLOSE);
   emaSlow2Handle = iMA(_Symbol, PERIOD_CURRENT, EMA_Slow2, 0, MODE_EMA, PRICE_CLOSE);
   emaSlow3Handle = iMA(_Symbol, PERIOD_CURRENT, EMA_Slow3, 0, MODE_EMA, PRICE_CLOSE);
   emaFilterHandle = iMA(_Symbol, PERIOD_CURRENT, EMA_Filter, 0, MODE_EMA, PRICE_CLOSE);
   atrHandle = iATR(_Symbol, PERIOD_CURRENT, ATR_Period);
   
   // HTF indicators
   htfEmaFastHandle = iMA(_Symbol, HTF_Timeframe, HTF_EMA_Fast, 0, MODE_EMA, PRICE_CLOSE);
   htfEmaSlowHandle = iMA(_Symbol, HTF_Timeframe, HTF_EMA_Slow, 0, MODE_EMA, PRICE_CLOSE);
   
   if(emaFastHandle == INVALID_HANDLE || emaSlow1Handle == INVALID_HANDLE ||
      emaSlow2Handle == INVALID_HANDLE || emaSlow3Handle == INVALID_HANDLE ||
      emaFilterHandle == INVALID_HANDLE || atrHandle == INVALID_HANDLE)
   {
      Print("ERROR: Failed to create indicator handles");
      return(INIT_FAILED);
   }
   
   dayStartBalance = AccountInfoDouble(ACCOUNT_BALANCE);
   lastTradeDate = TimeCurrent();
   
   Print("═══════════════════════════════════════════════════");
   Print("🎯 XAUUSD SNIPER EA INITIALIZED");
   Print("═══════════════════════════════════════════════════");
   Print("Lot Size: ", FixedLotSize, " (FIXED)");
   Print("Daily Limits: +$", DailyProfitTarget, " / -$", DailyLossLimit);
   Print("HTF Bias: ", UseHTFBias ? "ENABLED" : "DISABLED");
   Print("Session Filter: ", UseSessionFilter ? "ENABLED" : "DISABLED");
   Print("Circuit Breaker: ", EnableCircuitBreaker ? "ENABLED" : "DISABLED");
   Print("═══════════════════════════════════════════════════");
   
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   IndicatorRelease(emaFastHandle);
   IndicatorRelease(emaSlow1Handle);
   IndicatorRelease(emaSlow2Handle);
   IndicatorRelease(emaSlow3Handle);
   IndicatorRelease(emaFilterHandle);
   IndicatorRelease(atrHandle);
   IndicatorRelease(htfEmaFastHandle);
   IndicatorRelease(htfEmaSlowHandle);
   
   Print("EA stopped. Reason: ", reason);
}

//+------------------------------------------------------------------+
//| Expert tick function                                              |
//+------------------------------------------------------------------+
void OnTick()
{
   // Check if new bar
   datetime currentBarTime = iTime(_Symbol, PERIOD_CURRENT, 0);
   if(currentBarTime == lastBarTime)
      return;
   lastBarTime = currentBarTime;
   
   // Reset daily counters at start of new day
   MqlDateTime timeStruct;
   TimeToStruct(TimeCurrent(), timeStruct);
   MqlDateTime lastTradeStruct;
   TimeToStruct(lastTradeDate, lastTradeStruct);
   
   if(timeStruct.day != lastTradeStruct.day)
   {
      dayStartBalance = AccountInfoDouble(ACCOUNT_BALANCE);
      todayTrades = 0;
      consecutiveLosses = 0;
      lastTradeDate = TimeCurrent();
      Print("🔄 New trading day - Counters reset");
   }
   
   // Check daily limits
   double todayPnL = AccountInfoDouble(ACCOUNT_BALANCE) - dayStartBalance;
   
   if(todayPnL >= DailyProfitTarget)
   {
      Print("✅ Daily profit target reached: $", DoubleToString(todayPnL, 2));
      return;
   }
   
   if(todayPnL <= -DailyLossLimit)
   {
      Print("🛑 Daily loss limit hit: $", DoubleToString(todayPnL, 2));
      CloseAllPositions();
      return;
   }
   
   if(todayTrades >= MaxTradesPerDay)
   {
      Print("📊 Max trades per day reached: ", todayTrades);
      return;
   }
   
   // Circuit breaker check
   if(EnableCircuitBreaker && consecutiveLosses >= ConsecutiveLossLimit)
   {
      Print("⚡ Circuit breaker activated: ", consecutiveLosses, " consecutive losses");
      return;
   }
   
   // Check session filter
   if(UseSessionFilter && !IsSessionActive())
      return;
   
   // Manage existing positions
   if(PositionsTotal() > 0)
   {
      ManageOpenPositions();
      return;
   }
   
   // Look for entry signals
   CheckEntrySignals();
}

//+------------------------------------------------------------------+
//| Check for entry signals using 4-phase state machine              |
//+------------------------------------------------------------------+
void CheckEntrySignals()
{
   // Get indicator values
   double emaFast[], emaSlow1[], emaSlow2[], emaSlow3[], emaFilter[];
   double atr[];
   
   ArraySetAsSeries(emaFast, true);
   ArraySetAsSeries(emaSlow1, true);
   ArraySetAsSeries(emaSlow2, true);
   ArraySetAsSeries(emaSlow3, true);
   ArraySetAsSeries(emaFilter, true);
   ArraySetAsSeries(atr, true);
   
   if(CopyBuffer(emaFastHandle, 0, 0, 3, emaFast) < 3 ||
      CopyBuffer(emaSlow1Handle, 0, 0, 3, emaSlow1) < 3 ||
      CopyBuffer(emaSlow2Handle, 0, 0, 3, emaSlow2) < 3 ||
      CopyBuffer(emaSlow3Handle, 0, 0, 3, emaSlow3) < 3 ||
      CopyBuffer(emaFilterHandle, 0, 0, 3, emaFilter) < 3 ||
      CopyBuffer(atrHandle, 0, 0, 3, atr) < 3)
      return;
   
   double currentPrice = iClose(_Symbol, PERIOD_CURRENT, 0);
   double currentATR = atr[0];
   
   // HTF Bias check
   if(UseHTFBias)
   {
      string htfBias = GetHTFBias();
      if(htfBias == "NEUTRAL")
      {
         if(currentState != STATE_SCANNING)
         {
            currentState = STATE_SCANNING;
            Print("⏸️ State: SCANNING (HTF neutral)");
         }
         return;
      }
   }
   
   // --- LONG ENTRY LOGIC ---
   bool longSetup = false;
   bool longArmed = false;
   bool longWindowOpen = false;
   
   // Setup: Price above filter EMA
   if(currentPrice > emaFilter[0])
   {
      longSetup = true;
      
      // Armed: Fast EMA pulled back below all slow EMAs
      if(emaFast[0] < emaSlow1[0] && emaFast[0] < emaSlow2[0] && emaFast[0] < emaSlow3[0])
      {
         longArmed = true;
         
         // Window Open: Fast EMA crosses back above first slow EMA
         if(emaFast[0] > emaSlow1[0] && emaFast[1] <= emaSlow1[1])
         {
            longWindowOpen = true;
         }
      }
   }
   
   // --- SHORT ENTRY LOGIC ---
   bool shortSetup = false;
   bool shortArmed = false;
   bool shortWindowOpen = false;
   
   // Setup: Price below filter EMA
   if(currentPrice < emaFilter[0])
   {
      shortSetup = true;
      
      // Armed: Fast EMA rallied above all slow EMAs
      if(emaFast[0] > emaSlow1[0] && emaFast[0] > emaSlow2[0] && emaFast[0] > emaSlow3[0])
      {
         shortArmed = true;
         
         // Window Open: Fast EMA crosses back below first slow EMA
         if(emaFast[0] < emaSlow1[0] && emaFast[1] >= emaSlow1[1])
         {
            shortWindowOpen = true;
         }
      }
   }
   
   // --- STATE MACHINE LOGIC ---
   if(longWindowOpen || shortWindowOpen)
   {
      if(currentState != STATE_WINDOW_OPEN)
      {
         currentState = STATE_WINDOW_OPEN;
         Print("🟢 State: WINDOW_OPEN");
      }
      
      // HTF confirmation
      if(UseHTFBias)
      {
         string htfBias = GetHTFBias();
         if(longWindowOpen && htfBias != "BULLISH")
            return;
         if(shortWindowOpen && htfBias != "BEARISH")
            return;
      }
      
      // Execute trade
      if(longWindowOpen)
         OpenTrade(ORDER_TYPE_BUY, currentATR);
      else if(shortWindowOpen)
         OpenTrade(ORDER_TYPE_SELL, currentATR);
   }
   else if(longArmed || shortArmed)
   {
      if(currentState != STATE_ARMED)
      {
         currentState = STATE_ARMED;
         Print("🟡 State: ARMED");
      }
   }
   else if(longSetup || shortSetup)
   {
      if(currentState != STATE_SCANNING)
      {
         currentState = STATE_SCANNING;
         Print("🔍 State: SCANNING");
      }
   }
}

//+------------------------------------------------------------------+
//| Open a trade                                                      |
//+------------------------------------------------------------------+
void OpenTrade(ENUM_ORDER_TYPE orderType, double atrValue)
{
   double price = (orderType == ORDER_TYPE_BUY) ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   
   // Calculate SL/TP
   double stopLoss, takeProfit;
   double slDistance = MathMax(atrValue * SL_ATR_Multiplier, MinStopPoints * _Point);
   double tpDistance = atrValue * TP_ATR_Multiplier;
   
   if(orderType == ORDER_TYPE_BUY)
   {
      stopLoss = price - slDistance;
      takeProfit = price + tpDistance;
   }
   else
   {
      stopLoss = price + slDistance;
      takeProfit = price - tpDistance;
   }
   
   // Normalize prices
   stopLoss = NormalizeDouble(stopLoss, _Digits);
   takeProfit = NormalizeDouble(takeProfit, _Digits);
   
   MqlTradeRequest request = {};
   MqlTradeResult result = {};
   
   request.action = TRADE_ACTION_DEAL;
   request.symbol = _Symbol;
   request.volume = FixedLotSize;
   request.type = orderType;
   request.price = price;
   request.sl = stopLoss;
   request.tp = takeProfit;
   request.deviation = MaxSlippage;
   request.magic = 123456;
   request.comment = "Sniper EA";
   
   if(OrderSend(request, result))
   {
      if(result.retcode == TRADE_RETCODE_DONE)
      {
         todayTrades++;
         currentState = STATE_ENTRY;
         Print("✅ ", (orderType == ORDER_TYPE_BUY ? "BUY" : "SELL"), " order opened");
         Print("   Entry: ", DoubleToString(price, _Digits));
         Print("   SL: ", DoubleToString(stopLoss, _Digits), " (", DoubleToString(slDistance/_Point, 1), " pts)");
         Print("   TP: ", DoubleToString(takeProfit, _Digits), " (", DoubleToString(tpDistance/_Point, 1), " pts)");
         Print("   Trades today: ", todayTrades);
      }
      else
      {
         Print("❌ Order failed: ", result.retcode, " - ", result.comment);
      }
   }
   else
   {
      Print("❌ OrderSend error: ", GetLastError());
   }
}

//+------------------------------------------------------------------+
//| Manage open positions (breakeven, monitoring)                    |
//+------------------------------------------------------------------+
void ManageOpenPositions()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket <= 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      
      double positionOpenPrice = PositionGetDouble(POSITION_PRICE_OPEN);
      double positionSL = PositionGetDouble(POSITION_SL);
      double positionTP = PositionGetDouble(POSITION_TP);
      ENUM_POSITION_TYPE positionType = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
      
      if(!UseBreakeven || positionSL == positionOpenPrice)
         continue;
      
      double currentPrice = (positionType == POSITION_TYPE_BUY) ? 
                           SymbolInfoDouble(_Symbol, SYMBOL_BID) : 
                           SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      
      // Move to breakeven at 50% to TP
      if(positionType == POSITION_TYPE_BUY)
      {
         double targetDistance = positionTP - positionOpenPrice;
         double currentDistance = currentPrice - positionOpenPrice;
         
         if(currentDistance >= targetDistance * Breakeven_Percent && positionSL < positionOpenPrice)
         {
            ModifyPosition(ticket, positionOpenPrice, positionTP);
            Print("🔒 Breakeven activated for position ", ticket);
         }
      }
      else // SHORT
      {
         double targetDistance = positionOpenPrice - positionTP;
         double currentDistance = positionOpenPrice - currentPrice;
         
         if(currentDistance >= targetDistance * Breakeven_Percent && positionSL > positionOpenPrice)
         {
            ModifyPosition(ticket, positionOpenPrice, positionTP);
            Print("🔒 Breakeven activated for position ", ticket);
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Modify position SL/TP                                             |
//+------------------------------------------------------------------+
bool ModifyPosition(ulong ticket, double newSL, double newTP)
{
   MqlTradeRequest request = {};
   MqlTradeResult result = {};
   
   request.action = TRADE_ACTION_SLTP;
   request.position = ticket;
   request.sl = NormalizeDouble(newSL, _Digits);
   request.tp = NormalizeDouble(newTP, _Digits);
   
   return OrderSend(request, result);
}

//+------------------------------------------------------------------+
//| Close all positions                                               |
//+------------------------------------------------------------------+
void CloseAllPositions()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket <= 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      
      MqlTradeRequest request = {};
      MqlTradeResult result = {};
      
      request.action = TRADE_ACTION_DEAL;
      request.position = ticket;
      request.symbol = _Symbol;
      request.volume = PositionGetDouble(POSITION_VOLUME);
      request.type = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? ORDER_TYPE_SELL : ORDER_TYPE_BUY;
      request.price = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? 
                     SymbolInfoDouble(_Symbol, SYMBOL_BID) : 
                     SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      request.deviation = MaxSlippage;
      
      OrderSend(request, result);
   }
}

//+------------------------------------------------------------------+
//| Check if current time is within trading session                  |
//+------------------------------------------------------------------+
bool IsSessionActive()
{
   MqlDateTime timeStruct;
   TimeToStruct(TimeCurrent(), timeStruct);
   int currentHour = timeStruct.hour;
   
   // London session
   bool londonActive = (currentHour >= LondonStartHour && currentHour < LondonEndHour);
   
   // New York session
   bool nyActive = (currentHour >= NYStartHour && currentHour < NYEndHour);
   
   return (londonActive || nyActive);
}

//+------------------------------------------------------------------+
//| Get HTF trend bias                                                |
//+------------------------------------------------------------------+
string GetHTFBias()
{
   double htfFast[], htfSlow[];
   ArraySetAsSeries(htfFast, true);
   ArraySetAsSeries(htfSlow, true);
   
   if(CopyBuffer(htfEmaFastHandle, 0, 0, 2, htfFast) < 2 ||
      CopyBuffer(htfEmaSlowHandle, 0, 0, 2, htfSlow) < 2)
      return "NEUTRAL";
   
   if(htfFast[0] > htfSlow[0])
      return "BULLISH";
   else if(htfFast[0] < htfSlow[0])
      return "BEARISH";
   else
      return "NEUTRAL";
}

//+------------------------------------------------------------------+
//| Track trade results for circuit breaker                          |
//+------------------------------------------------------------------+
void OnTrade()
{
   // Check if position was closed
   if(HistorySelect(TimeCurrent() - 60, TimeCurrent()))
   {
      int total = HistoryDealsTotal();
      if(total > 0)
      {
         ulong ticket = HistoryDealGetTicket(total - 1);
         if(ticket > 0)
         {
            long dealEntry = HistoryDealGetInteger(ticket, DEAL_ENTRY);
            if(dealEntry == DEAL_ENTRY_OUT) // Position closed
            {
               double profit = HistoryDealGetDouble(ticket, DEAL_PROFIT);
               
               if(profit < 0)
                  consecutiveLosses++;
               else
                  consecutiveLosses = 0; // Reset on win
               
               Print("📊 Trade closed: ", (profit > 0 ? "WIN ✅" : "LOSS ❌"), 
                     " P&L: $", DoubleToString(profit, 2),
                     " | Consecutive losses: ", consecutiveLosses);
            }
         }
      }
   }
}
//+------------------------------------------------------------------+
