#property strict
#property description "Replays causal Python signals inside local MT5 Strategy Tester only"
#include <Trade/Trade.mqh>
input string SignalFile="ta_signals.csv";
input double RiskPercent=1.0;
input double StopATR=2.0;
input double TakeATR=4.0;
input double MaxLots=1.0;
input long Magic=902601;
CTrade trade;
datetime times[];
int targets[];
double atrs[];
int cursor=0;
datetime previousBar=0;

int OnInit() {
   if(!MQLInfoInteger(MQL_TESTER)) {
      Print("This EA runs only in Strategy Tester."); return INIT_FAILED;
   }
   if(RiskPercent<=0 || RiskPercent>10 || StopATR<=0 || TakeATR<=0 || MaxLots<=0)
      return INIT_PARAMETERS_INCORRECT;
   int f=FileOpen(SignalFile,FILE_READ|FILE_CSV|FILE_ANSI|FILE_COMMON,',');
   if(f==INVALID_HANDLE) { Print("Missing Common/Files/",SignalFile); return INIT_FAILED; }
   for(int j=0;j<5;j++) FileReadString(f);
   while(!FileIsEnding(f)) {
      string raw=FileReadString(f);
      if(raw=="" && FileIsEnding(f)) break;
      datetime t=(datetime)StringToInteger(raw);
      int target=(int)StringToInteger(FileReadString(f));
      double atr=StringToDouble(FileReadString(f));
      string symbol=FileReadString(f);
      int seconds=(int)StringToInteger(FileReadString(f));
      int n=ArraySize(times);
      if(t<=0 || (n>0 && t<=times[n-1]) || (target!=0 && target!=1) || atr<=0 ||
         symbol!=_Symbol || seconds!=PeriodSeconds(_Period)) {
         Print("Invalid row, symbol, or timeframe at row ",n+2); FileClose(f); return INIT_FAILED;
      }
      ArrayResize(times,n+1); ArrayResize(targets,n+1); ArrayResize(atrs,n+1);
      times[n]=t; targets[n]=target; atrs[n]=atr;
   }
   FileClose(f);
   if(ArraySize(times)==0) return INIT_FAILED;
   trade.SetExpertMagicNumber(Magic);
   trade.SetTypeFillingBySymbol(_Symbol);
   trade.SetDeviationInPoints(20);
   return INIT_SUCCEEDED;
}

bool OwnPosition() {
   return PositionSelect(_Symbol) && PositionGetInteger(POSITION_MAGIC)==Magic;
}
void CloseOwn() {
   if(OwnPosition()) {
      bool sent=trade.PositionClose(_Symbol);
      if(!sent || trade.ResultRetcode()!=TRADE_RETCODE_DONE)
         Print("Close failed: ",trade.ResultRetcodeDescription());
   }
}

void OnTick() {
   datetime now=iTime(_Symbol,_Period,0);
   if(now==previousBar) return;
   previousBar=now;
   while(cursor<ArraySize(times) && times[cursor]<now) cursor++;
   // Missing row or end of replay: flatten; never carry stale signals forward.
   if(cursor>=ArraySize(times) || times[cursor]!=now) { CloseOwn(); return; }
   int target=targets[cursor]; double atr=atrs[cursor]; cursor++;
   if(target==0) { CloseOwn(); return; }
   if(PositionSelect(_Symbol)) return; // one position per symbol, including foreign positions
   MqlTick tick;
   if(!SymbolInfoTick(_Symbol,tick)) return;
   double tickSize=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);
   if(tickSize<=0) return;
   double sl=NormalizeDouble(MathFloor((tick.ask-StopATR*atr)/tickSize)*tickSize,_Digits);
   double tp=NormalizeDouble(MathCeil((tick.ask+TakeATR*atr)/tickSize)*tickSize,_Digits);
   double minStop=SymbolInfoInteger(_Symbol,SYMBOL_TRADE_STOPS_LEVEL)*_Point;
   if(sl<=0 || tick.bid-sl<minStop || tp-tick.bid<minStop) { Print("Stops invalid for broker"); return; }
   double pnl=0;
   if(!OrderCalcProfit(ORDER_TYPE_BUY,_Symbol,1.0,tick.ask,sl,pnl) || pnl>=0) return;
   double volume=AccountInfoDouble(ACCOUNT_EQUITY)*RiskPercent/100.0/MathAbs(pnl);
   double step=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP);
   double minVol=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN);
   double maxVol=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX);
   if(step<=0) return;
   volume=MathMin(volume,MathMin(maxVol,MaxLots));
   double margin=0;
   if(!OrderCalcMargin(ORDER_TYPE_BUY,_Symbol,volume,tick.ask,margin)) return;
   if(margin>AccountInfoDouble(ACCOUNT_MARGIN_FREE) && margin>0)
      volume*=AccountInfoDouble(ACCOUNT_MARGIN_FREE)*0.95/margin;
   volume=NormalizeDouble(MathFloor(volume/step)*step,8);
   if(volume<minVol) { Print("Risk budget below minimum volume"); return; }
   bool sent=trade.Buy(volume,_Symbol,0,sl,tp,"MCP deterministic replay");
   if(!sent || (trade.ResultRetcode()!=TRADE_RETCODE_DONE && trade.ResultRetcode()!=TRADE_RETCODE_DONE_PARTIAL))
      Print("Buy failed: ",trade.ResultRetcodeDescription());
}
