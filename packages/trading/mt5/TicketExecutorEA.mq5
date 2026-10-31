//+------------------------------------------------------------------+
//| TicketExecutorEA.mq5                                              |
//|                                                                    |
//| Executes order tickets written by the fx-futures-trader skills     |
//| (apps/fx-futures-trader, fx-broker/ticket.py) into the terminal's  |
//| COMMON Files folder:                                               |
//|   <TicketFolder>\pending\*.json   tickets to execute               |
//|   <TicketFolder>\done\<id>.json    tickets handled (kept for state)|
//|   <TicketFolder>\results\<id>.json what happened (read by sync)    |
//|                                                                    |
//| One ticket = one trade split into 1-3 legs (one per take-profit),  |
//| all with the same stop. Before anything is sent it:                |
//|   - drops tickets older than their expiry (default 120 s)          |
//|   - refuses live accounts unless RequireDemo=false AND the ticket  |
//|     itself allows it                                               |
//|   - recomputes the loss at the stop with THIS broker's contract    |
//|     (OrderCalcProfit) and refuses if it is over the ticket's max   |
//|     loss, so a wrong lot/tick spec on the Python side cannot size  |
//|     a trade bigger than you approved                               |
//|   - asks you on screen (Yes / No) when ConfirmEachTicket=true      |
//| After the entry: moves the other legs' stop to the entry price     |
//| once TP1 fills, and closes everything at the ticket's flat-by time.|
//| Attach to ONE chart; it trades any symbol named in a ticket.       |
//+------------------------------------------------------------------+
#property copyright "rajesh-hub"
#property version   "1.00"

#include <RajeshHub\TradeUtils.mqh>
#include <RajeshHub\FlatJson.mqh>

input string TicketFolder      = "RajeshHub\\tickets"; // under ...\MetaQuotes\Terminal\Common\Files -- must match brokers.mt5.folder
input int    PollSeconds       = 1;
input bool   EnableTrading     = false; // false = dry run: check and log every ticket, never trade
input bool   RequireDemo       = true;  // refuse every ticket on a real-money account
input bool   ConfirmEachTicket = true;  // Yes/No box on screen before each ticket
input double LossTolerancePct  = 10.0;  // broker loss at stop may exceed ticket max_loss by this much (spread/rounding)
input int    MaxSpreadPoints   = 0;     // 0 = off
input bool   EnforceFlatBy     = true;

// ---- tracked legs (rebuilt from open positions + done\ files on restart)
string   g_id[];
ulong    g_pos[];
int      g_leg[];
double   g_vol[];
double   g_open[];
bool     g_be[];
datetime g_flat[];
bool     g_beDone[];

string Pending()  { return TicketFolder+"\\pending"; }
string DoneDir()  { return TicketFolder+"\\done"; }
string Results()  { return TicketFolder+"\\results"; }

//+------------------------------------------------------------------+
int OnInit()
  {
   EventSetTimer(MathMax(PollSeconds,1));
   RebuildTracking();
   PrintFormat("[TicketExecutor] started. Trading=%s RequireDemo=%s Confirm=%s Folder=%s Account=%s",
               EnableTrading?"ON":"OFF (dry run)",RequireDemo?"yes":"no",ConfirmEachTicket?"yes":"no",TicketFolder,
               IsDemo()?"DEMO":"REAL");
   return(INIT_SUCCEEDED);
  }

void OnDeinit(const int reason) { EventKillTimer(); }

void OnTimer()
  {
   ScanPending();
   ManageLegs();
  }

bool IsDemo()
  {
   return AccountInfoInteger(ACCOUNT_TRADE_MODE)==ACCOUNT_TRADE_MODE_DEMO;
  }

//+------------------------------------------------------------------+
//| results                                                           |
//+------------------------------------------------------------------+
void WriteResult(const string id,const string status,const string reason,double filledQty,double avgPrice,
                 const string positions,double closedQty,double pnl)
  {
   string j="{\"ticket_id\":\""+JEsc(id)+"\",\"status\":\""+status+"\",\"reason\":\""+JEsc(reason)+"\""+
            ",\"filled_qty\":"+DoubleToString(filledQty,2)+",\"avg_price\":"+DoubleToString(avgPrice,8)+
            ",\"positions\":\""+positions+"\",\"closed_qty\":"+DoubleToString(closedQty,2)+
            ",\"pnl\":"+DoubleToString(pnl,2)+",\"account_ccy\":\""+AccountInfoString(ACCOUNT_CURRENCY)+"\""+
            ",\"demo\":"+(IsDemo()?"1":"0")+",\"updated_utc\":"+IntegerToString((long)TimeGMT())+"}";
   if(!WriteCommonText(Results()+"\\"+id+".json",j))
      PrintFormat("[TicketExecutor] could not write result for %s err=%d",id,GetLastError());
  }

bool AlreadyHandled(const string id)
  {
   return FileIsExist(Results()+"\\"+id+".json",FILE_COMMON);
  }

void Finish(const string fname,const string id,const string status,const string reason)
  {
   if(status!="placed")
      WriteResult(id,status,reason,0,0,"",0,0);
   string src=Pending()+"\\"+fname;
   if(!FileMove(src,FILE_COMMON,DoneDir()+"\\"+id+".json",FILE_COMMON|FILE_REWRITE))
      FileDelete(src,FILE_COMMON);
   PrintFormat("[TicketExecutor] %s %s %s",id,status,reason);
  }

//+------------------------------------------------------------------+
//| pending scan                                                      |
//+------------------------------------------------------------------+
void ScanPending()
  {
   string fname;
   long h=FileFindFirst(Pending()+"\\*.json",fname,FILE_COMMON);
   if(h==INVALID_HANDLE) return;
   string names[];
   do
     {
      int n=ArraySize(names);
      ArrayResize(names,n+1);
      names[n]=fname;
     }
   while(FileFindNext(h,fname));
   FileFindClose(h);
   for(int i=0;i<ArraySize(names);i++)
      ProcessTicket(names[i]);
  }

void ProcessTicket(const string fname)
  {
   string content=ReadCommonText(Pending()+"\\"+fname);
   if(content=="") return;
   string id=JGetStr(content,"ticket_id");
   string action=JGetStr(content,"action");
   if(id=="" || JGetStr(content,"fingerprint")=="")
     {
      FileDelete(Pending()+"\\"+fname,FILE_COMMON);
      Print("[TicketExecutor] dropped malformed ticket ",fname);
      return;
     }
   if(AlreadyHandled(id))
     {
      FileDelete(Pending()+"\\"+fname,FILE_COMMON);
      return;
     }
   if((long)TimeGMT()>(long)JGetNum(content,"expires_utc"))
     { Finish(fname,id,"expired","ticket expired before the EA read it"); return; }
   bool needDemo=RequireDemo || JGetNum(content,"require_demo")>0.5;
   if(needDemo && !IsDemo())
     { Finish(fname,id,"rejected","this is a real-money account and the ticket requires demo"); return; }
   if(action=="OPEN") HandleOpen(fname,id,content);
   else if(action=="CLOSE") HandleClose(fname,id,content);
   else Finish(fname,id,"rejected","unknown action "+action);
  }

//+------------------------------------------------------------------+
ENUM_ORDER_TYPE_FILLING FillingFor(const string sym)
  {
   int filling=(int)SymbolInfoInteger(sym,SYMBOL_FILLING_MODE);
   if((filling&SYMBOL_FILLING_FOK)!=0) return ORDER_FILLING_FOK;
   if((filling&SYMBOL_FILLING_IOC)!=0) return ORDER_FILLING_IOC;
   return ORDER_FILLING_RETURN;
  }

void HandleOpen(const string fname,const string id,const string content)
  {
   string sym=JGetStr(content,"symbol");
   if(!SymbolSelect(sym,true))
     { Finish(fname,id,"rejected","symbol "+sym+" not found at this broker"); return; }
   bool buy=(JGetStr(content,"dir")=="BUY");
   int digits=(int)SymbolInfoInteger(sym,SYMBOL_DIGITS);
   double sl=NormalizeDouble(JGetNum(content,"stop"),digits);
   int legs=(int)JGetNum(content,"legs_total");
   if(legs<1 || legs>3)
     { Finish(fname,id,"rejected","legs_total must be 1-3"); return; }
   double ask=SymbolInfoDouble(sym,SYMBOL_ASK), bid=SymbolInfoDouble(sym,SYMBOL_BID);
   if(ask<=0 || bid<=0)
     { Finish(fname,id,"rejected","no price for "+sym+" (market closed?)"); return; }
   double px=buy?ask:bid;
   if((buy && sl>=bid) || (!buy && sl<=ask))
     { Finish(fname,id,"rejected","stop is on the wrong side of the market"); return; }
   if(MaxSpreadPoints>0 && SymbolInfoInteger(sym,SYMBOL_SPREAD)>MaxSpreadPoints)
     { Finish(fname,id,"rejected","spread "+IntegerToString(SymbolInfoInteger(sym,SYMBOL_SPREAD))+" points over limit"); return; }

   double vol[3]; double tp[3];
   double step=SymbolInfoDouble(sym,SYMBOL_VOLUME_STEP);
   double total=0, loss=0;
   for(int i=0;i<legs;i++)
     {
      double want=JGetNum(content,"leg"+IntegerToString(i+1)+"_qty");
      vol[i]=NormalizeVolume(sym,want);
      tp[i]=NormalizeDouble(JGetNum(content,"leg"+IntegerToString(i+1)+"_tp"),digits);
      if(MathAbs(vol[i]-want)>step/2.0)
        { Finish(fname,id,"rejected","leg "+IntegerToString(i+1)+" volume "+DoubleToString(want,2)+" is not valid here (min/step/max)"); return; }
      if((buy && tp[i]<=px) || (!buy && tp[i]>=px))
        { Finish(fname,id,"rejected","take-profit "+IntegerToString(i+1)+" is already passed"); return; }
      double profit=0;
      if(!OrderCalcProfit(buy?ORDER_TYPE_BUY:ORDER_TYPE_SELL,sym,vol[i],px,sl,profit))
        { Finish(fname,id,"rejected","could not compute the loss at the stop"); return; }
      loss+=-profit;
      total+=vol[i];
     }
   double maxLoss=JGetNum(content,"max_loss");
   if(JGetStr(content,"account_ccy")!="" && JGetStr(content,"account_ccy")!=AccountInfoString(ACCOUNT_CURRENCY))
     { Finish(fname,id,"rejected","ticket is in "+JGetStr(content,"account_ccy")+", account is "+AccountInfoString(ACCOUNT_CURRENCY)); return; }
   if(maxLoss<=0 || loss>maxLoss*(1.0+LossTolerancePct/100.0))
     {
      Finish(fname,id,"rejected",StringFormat("broker loss at stop %.2f is over the approved %.2f: check the contract spec",loss,maxLoss));
      return;
     }

   string text=StringFormat("%s %s %.2f lots (%d legs)\nnow %s, stop %s\nTP %s%s%s\nloss at stop about %.2f %s\n%s account\n\nPlace ticket %s?",
                            buy?"BUY":"SELL",sym,total,legs,DoubleToString(px,digits),DoubleToString(sl,digits),
                            DoubleToString(tp[0],digits),legs>1?" / "+DoubleToString(tp[1],digits):"",legs>2?" / "+DoubleToString(tp[2],digits):"",
                            loss,AccountInfoString(ACCOUNT_CURRENCY),IsDemo()?"DEMO":"REAL MONEY",id);
   if(ConfirmEachTicket && MessageBox(text,"TicketExecutor: confirm",MB_YESNO|MB_ICONQUESTION)!=IDYES)
     { Finish(fname,id,"denied","you pressed No"); return; }
   if(!EnableTrading)
     { Finish(fname,id,"dryrun","EnableTrading is off: checked, not traded"); return; }

   long magic=(long)JGetNum(content,"magic");
   int slip=(int)JGetNum(content,"slippage");
   bool be=JGetNum(content,"be_after_tp1")>0.5;
   datetime flat=(datetime)(long)JGetNum(content,"flat_by_utc");
   string posList="";
   double filled=0, wsum=0;
   for(int i=0;i<legs;i++)
     {
      MqlTradeRequest rq; MqlTradeResult rs;
      ZeroMemory(rq); ZeroMemory(rs);
      rq.action=TRADE_ACTION_DEAL;
      rq.symbol=sym;
      rq.volume=vol[i];
      rq.type=buy?ORDER_TYPE_BUY:ORDER_TYPE_SELL;
      rq.price=buy?SymbolInfoDouble(sym,SYMBOL_ASK):SymbolInfoDouble(sym,SYMBOL_BID);
      rq.sl=sl;
      rq.tp=tp[i];
      rq.deviation=slip;
      rq.magic=magic;
      rq.comment=id+"#"+IntegerToString(i+1);
      rq.type_filling=FillingFor(sym);
      if(!OrderSend(rq,rs) || (rs.retcode!=TRADE_RETCODE_DONE && rs.retcode!=TRADE_RETCODE_DONE_PARTIAL))
        {
         PrintFormat("[TicketExecutor] %s leg %d failed retcode=%d err=%d",id,i+1,rs.retcode,GetLastError());
         continue;
        }
      ulong posId=0;
      if(HistoryDealSelect(rs.deal)) posId=(ulong)HistoryDealGetInteger(rs.deal,DEAL_POSITION_ID);
      if(posId==0) posId=rs.order;
      Track(id,posId,i+1,rs.volume,rs.price,be,flat);
      posList+=(posList==""?"":",")+IntegerToString((long)posId);
      filled+=rs.volume;
      wsum+=rs.volume*rs.price;
     }
   if(filled<=0)
     { Finish(fname,id,"rejected","no leg was filled (see Experts log)"); return; }
   WriteResult(id,"placed",filled<total?"partly filled":"",filled,wsum/filled,posList,0,0);
   Finish(fname,id,"placed","");
  }

void HandleClose(const string fname,const string id,const string content)
  {
   string of=JGetStr(content,"close_of");
   int n=0;
   for(int i=0;i<ArraySize(g_id);i++)
      if(g_id[i]==of && PositionSelectByTicket(g_pos[i])) n++;
   if(n==0)
     { Finish(fname,id,"rejected","no open legs for "+of); return; }
   if(ConfirmEachTicket && MessageBox(StringFormat("Close %d open leg(s) of %s at market?",n,of),"TicketExecutor: confirm",MB_YESNO|MB_ICONQUESTION)!=IDYES)
     { Finish(fname,id,"denied","you pressed No"); return; }
   if(!EnableTrading)
     { Finish(fname,id,"dryrun","EnableTrading is off"); return; }
   CloseGroup(of,"close ticket "+id);
   WriteResult(id,"placed","closed "+of,0,0,"",0,0);
   Finish(fname,id,"placed","");
  }

//+------------------------------------------------------------------+
//| leg tracking                                                      |
//+------------------------------------------------------------------+
void Track(const string id,ulong pos,int leg,double vol,double open,bool be,datetime flat)
  {
   int n=ArraySize(g_id);
   ArrayResize(g_id,n+1); ArrayResize(g_pos,n+1); ArrayResize(g_leg,n+1); ArrayResize(g_vol,n+1);
   ArrayResize(g_open,n+1); ArrayResize(g_be,n+1); ArrayResize(g_flat,n+1); ArrayResize(g_beDone,n+1);
   g_id[n]=id; g_pos[n]=pos; g_leg[n]=leg; g_vol[n]=vol; g_open[n]=open; g_be[n]=be; g_flat[n]=flat; g_beDone[n]=false;
  }

void RebuildTracking()
  {
   for(int i=PositionsTotal()-1;i>=0;i--)
     {
      ulong t=PositionGetTicket(i);
      if(t==0 || !PositionSelectByTicket(t)) continue;
      string c=PositionGetString(POSITION_COMMENT);
      int hash=StringFind(c,"#");
      if(hash<=0 || StringGetCharacter(c,0)!='T') continue;
      string id=StringSubstr(c,0,hash);
      string done=ReadCommonText(DoneDir()+"\\"+id+".json");
      if(done=="") continue;
      Track(id,(ulong)PositionGetInteger(POSITION_IDENTIFIER),(int)StringToInteger(StringSubstr(c,hash+1)),
            PositionGetDouble(POSITION_VOLUME),PositionGetDouble(POSITION_PRICE_OPEN),
            JGetNum(done,"be_after_tp1")>0.5,(datetime)(long)JGetNum(done,"flat_by_utc"));
     }
   PrintFormat("[TicketExecutor] tracking %d open leg(s)",ArraySize(g_id));
  }

// Closed volume and money (profit+swap+commission+fee) of one position so far.
void PositionHistory(ulong posId,double &closedVol,double &money,bool &byTP)
  {
   closedVol=0; money=0; byTP=false;
   if(!HistorySelectByPosition(posId)) return;
   for(int k=0;k<HistoryDealsTotal();k++)
     {
      ulong d=HistoryDealGetTicket(k);
      money+=HistoryDealGetDouble(d,DEAL_PROFIT)+HistoryDealGetDouble(d,DEAL_SWAP)+
             HistoryDealGetDouble(d,DEAL_COMMISSION)+HistoryDealGetDouble(d,DEAL_FEE);
      long entry=HistoryDealGetInteger(d,DEAL_ENTRY);
      if(entry==DEAL_ENTRY_OUT || entry==DEAL_ENTRY_OUT_BY)
        {
         closedVol+=HistoryDealGetDouble(d,DEAL_VOLUME);
         if(HistoryDealGetInteger(d,DEAL_REASON)==DEAL_REASON_TP) byTP=true;
        }
     }
  }

void CloseGroup(const string id,const string why)
  {
   for(int i=0;i<ArraySize(g_id);i++)
     {
      if(g_id[i]!=id || !PositionSelectByTicket(g_pos[i])) continue;
      string sym=PositionGetString(POSITION_SYMBOL);
      bool isBuy=(PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY);
      MqlTradeRequest rq; MqlTradeResult rs;
      ZeroMemory(rq); ZeroMemory(rs);
      rq.action=TRADE_ACTION_DEAL;
      rq.position=g_pos[i];
      rq.symbol=sym;
      rq.volume=PositionGetDouble(POSITION_VOLUME);
      rq.type=isBuy?ORDER_TYPE_SELL:ORDER_TYPE_BUY;
      rq.price=isBuy?SymbolInfoDouble(sym,SYMBOL_BID):SymbolInfoDouble(sym,SYMBOL_ASK);
      rq.deviation=50;
      rq.magic=PositionGetInteger(POSITION_MAGIC);
      rq.type_filling=FillingFor(sym);
      if(!OrderSend(rq,rs))
         PrintFormat("[TicketExecutor] close %s leg %d failed err=%d",id,g_leg[i],GetLastError());
      else
         PrintFormat("[TicketExecutor] closed %s leg %d (%s)",id,g_leg[i],why);
     }
  }

void ManageLegs()
  {
   // unique ticket ids currently tracked
   string ids[];
   for(int i=0;i<ArraySize(g_id);i++)
     {
      bool seen=false;
      for(int k=0;k<ArraySize(ids);k++) if(ids[k]==g_id[i]) { seen=true; break; }
      if(!seen) { int n=ArraySize(ids); ArrayResize(ids,n+1); ids[n]=g_id[i]; }
     }
   for(int k=0;k<ArraySize(ids);k++)
     {
      string id=ids[k];
      double closedQty=0, money=0, filled=0, wsum=0;
      bool tp1Hit=false, anyOpen=false, be=false;
      datetime flat=0;
      string posList="";
      for(int i=0;i<ArraySize(g_id);i++)
        {
         if(g_id[i]!=id) continue;
         double cv,m; bool byTP;
         PositionHistory(g_pos[i],cv,m,byTP);
         closedQty+=cv; money+=m; filled+=g_vol[i]; wsum+=g_vol[i]*g_open[i];
         if(g_leg[i]==1 && byTP) tp1Hit=true;
         if(PositionSelectByTicket(g_pos[i])) anyOpen=true;
         be=be||g_be[i]; flat=g_flat[i];
         posList+=(posList==""?"":",")+IntegerToString((long)g_pos[i]);
        }
      // breakeven after TP1
      if(tp1Hit && be && EnableTrading)
         for(int i=0;i<ArraySize(g_id);i++)
           {
            if(g_id[i]!=id || g_beDone[i] || g_leg[i]==1 || !PositionSelectByTicket(g_pos[i])) continue;
            string sym=PositionGetString(POSITION_SYMBOL);
            double open=PositionGetDouble(POSITION_PRICE_OPEN);
            double cur=PositionGetDouble(POSITION_SL);
            bool isBuy=(PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY);
            if((isBuy && cur>=open) || (!isBuy && cur>0 && cur<=open)) { g_beDone[i]=true; continue; }
            MqlTradeRequest rq; MqlTradeResult rs;
            ZeroMemory(rq); ZeroMemory(rs);
            rq.action=TRADE_ACTION_SLTP;
            rq.position=g_pos[i];
            rq.symbol=sym;
            rq.sl=NormalizeDouble(open,(int)SymbolInfoInteger(sym,SYMBOL_DIGITS));
            rq.tp=PositionGetDouble(POSITION_TP);
            if(OrderSend(rq,rs) && rs.retcode==TRADE_RETCODE_DONE)
              { g_beDone[i]=true; PrintFormat("[TicketExecutor] %s leg %d stop to breakeven %.5f",id,g_leg[i],open); }
           }
      // flat-by
      if(EnforceFlatBy && EnableTrading && anyOpen && flat>0 && TimeGMT()>=flat)
         CloseGroup(id,"flat-by time");
      WriteResult(id,"placed","",filled,filled>0?wsum/filled:0,posList,closedQty,money);
      if(!anyOpen)
        {
         // all legs closed: stop tracking
         for(int i=ArraySize(g_id)-1;i>=0;i--)
            if(g_id[i]==id) RemoveAt(i);
        }
     }
  }

void RemoveAt(int i)
  {
   int n=ArraySize(g_id);
   for(int k=i;k<n-1;k++)
     {
      g_id[k]=g_id[k+1]; g_pos[k]=g_pos[k+1]; g_leg[k]=g_leg[k+1]; g_vol[k]=g_vol[k+1];
      g_open[k]=g_open[k+1]; g_be[k]=g_be[k+1]; g_flat[k]=g_flat[k+1]; g_beDone[k]=g_beDone[k+1];
     }
   ArrayResize(g_id,n-1); ArrayResize(g_pos,n-1); ArrayResize(g_leg,n-1); ArrayResize(g_vol,n-1);
   ArrayResize(g_open,n-1); ArrayResize(g_be,n-1); ArrayResize(g_flat,n-1); ArrayResize(g_beDone,n-1);
  }
//+------------------------------------------------------------------+
