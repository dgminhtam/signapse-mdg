#property service
#property version "1.00"

input string ReceiverHost = "mdg-tcp-smoke.test";
input uint ReceiverPort = 9001;
input uint PollMilliseconds = 250;

string symbols[];
long sequence = 0;

bool SendLine(int socket, string line)
{
   uchar bytes[];
   int size = StringToCharArray(line + "\n", bytes, 0, WHOLE_ARRAY, CP_UTF8) - 1;
   if(size > 65536) return false;
   int offset = 0;
   while(offset < size && !IsStopped())
   {
      uchar tail[];
      ArrayCopy(tail, bytes, 0, offset, size - offset);
      int sent = SocketSend(socket, tail, size - offset);
      if(sent <= 0) return false;
      offset += sent;
   }
   return offset == size;
}

ENUM_TIMEFRAMES Frame(string value)
{
   if(value == "1m") return PERIOD_M1;
   if(value == "5m") return PERIOD_M5;
   if(value == "15m") return PERIOD_M15;
   if(value == "30m") return PERIOD_M30;
   if(value == "1h") return PERIOD_H1;
   if(value == "4h") return PERIOD_H4;
   if(value == "1d") return PERIOD_D1;
   if(value == "1w") return PERIOD_W1;
   if(value == "1mo") return PERIOD_MN1;
   return PERIOD_CURRENT;
}

bool Allowed(string symbol)
{
   for(int i=0; i<ArraySize(symbols); i++) if(symbols[i] == symbol) return true;
   return false;
}

string Rates(string &parts[])
{
   string id=parts[1], symbol=parts[2];
   ENUM_TIMEFRAMES frame=Frame(parts[3]);
   long from=StringToInteger(parts[4]), to=StringToInteger(parts[5]);
   int limit=(int)StringToInteger(parts[6]);
   if(!Allowed(symbol) || frame==PERIOD_CURRENT || from<=0 || to<=from || limit<1 || limit>128 || StringLen(id)!=32)
      return "";
   MqlRates bars[];
   // Position is resolved from the exclusive end. Read a bounded prefix from the requested start.
   ResetLastError();
   int start_index=iBarShift(symbol, frame, (datetime)from, false);
   if(start_index >= 0)
   {
      datetime candidate=iTime(symbol, frame, start_index);
      if(candidate < from) start_index--;
   }
   int error=GetLastError();
   int count=0;
   if(start_index >= 0)
   {
      int requested=MathMin(limit, start_index+1);
      ResetLastError();
      count=CopyRates(symbol, frame, start_index-requested+1, requested, bars);
      error=GetLastError();
   }
   bool ready=(bool)SeriesInfoInteger(symbol, frame, SERIES_SYNCHRONIZED);
   string status=(error==0 && ready && count>=0) ? "OK" : "LOADING";
   string result=StringFormat("{\"type\":\"rates\",\"id\":\"%s\",\"status\":\"%s\",\"error\":%d,\"bars\":[", id,status,error);
   int digits=(int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
   int written=0;
   for(int i=0; i<count; i++)
   {
      if((long)bars[i].time < from || (long)bars[i].time >= to) continue;
      if(written++ > 0) result+=",";
      result+=StringFormat("{\"timeRaw\":%I64d,\"o\":\"%s\",\"h\":\"%s\",\"l\":\"%s\",\"c\":\"%s\",\"volume\":\"%I64d\"}",
         (long)bars[i].time,DoubleToString(bars[i].open,digits),DoubleToString(bars[i].high,digits),
         DoubleToString(bars[i].low,digits),DoubleToString(bars[i].close,digits),bars[i].real_volume);
   }
   return result+"]}";
}

void OnStart()
{
   while(!IsStopped() && !TerminalInfoInteger(TERMINAL_CONNECTED)) Sleep(1000);
   if(AccountInfoString(ACCOUNT_SERVER)!="VantageMarkets-Demo" || TerminalInfoInteger(TERMINAL_TRADE_ALLOWED))
   { Print("MarketDataService: unexpected broker or Algo Trading enabled"); return; }
   int file=FileOpen("MarketDataToken.txt",FILE_READ|FILE_TXT|FILE_ANSI,0,CP_UTF8);
   if(file==INVALID_HANDLE) { Print("MarketDataService: token missing"); return; }
   string token=FileReadString(file);
   FileClose(file);
   if(StringLen(token)<32) return;
   file=FileOpen("MarketDataSymbols.txt",FILE_READ|FILE_TXT|FILE_ANSI,0,CP_UTF8);
   if(file==INVALID_HANDLE) { Print("MarketDataService: symbol config missing"); return; }
   string csv=FileReadString(file);
   FileClose(file);
   int total=StringSplit(csv,',',symbols);
   if(total<1 || total>22) return;
   for(int i=0;i<total;i++) if(!SymbolSelect(symbols[i],true)) { Print("MarketDataService: unknown symbol"); return; }
   while(!IsStopped())
   {
      if(AccountInfoString(ACCOUNT_SERVER)!="VantageMarkets-Demo" || TerminalInfoInteger(TERMINAL_TRADE_ALLOWED)) break;
      if(!TerminalInfoInteger(TERMINAL_CONNECTED)) { Sleep(1000); continue; }
      int socket=SocketCreate();
      if(socket==INVALID_HANDLE) { Sleep(1000); continue; }
      if(!SocketConnect(socket,ReceiverHost,ReceiverPort,2000))
      { PrintFormat("MarketDataService: SocketConnect error %d",GetLastError()); SocketClose(socket); Sleep(1000); continue; }
      SocketTimeouts(socket,1000,1000);
      string names="";
      for(int i=0;i<total;i++) { if(i>0) names+=","; names+="\""+symbols[i]+"\""; }
      string hello=StringFormat("{\"type\":\"hello\",\"version\":1,\"server\":\"VantageMarkets-Demo\",\"service\":true,\"algoTrading\":false,\"serverTime\":%I64d,\"utcTime\":%I64d,\"symbols\":[%s]}",
         (long)TimeTradeServer(),(long)TimeGMT(),names);
      bool active=SendLine(socket,"HELLO "+token) && SendLine(socket,hello);
      Print("MarketDataService: TCP connected");
      sequence=0;
      string buffer="";
      ulong next_poll=0, next_status=0;
      while(active && !IsStopped() && SocketIsConnected(socket))
      {
         if(AccountInfoString(ACCOUNT_SERVER)!="VantageMarkets-Demo" || TerminalInfoInteger(TERMINAL_TRADE_ALLOWED)) break;
         uint available=SocketIsReadable(socket);
         if(available>0)
         {
            if(available>4096) break;
            uchar bytes[];
            int size=SocketRead(socket,bytes,available,1000);
            if(size<=0) break;
            buffer+=CharArrayToString(bytes,0,size,CP_UTF8);
            if(StringLen(buffer)>4096) break;
         }
         int newline=StringFind(buffer,"\n");
         if(newline>=0)
         {
            string command=StringSubstr(buffer,0,newline);
            buffer=StringSubstr(buffer,newline+1);
            string parts[];
            int count=StringSplit(command,'\t',parts);
            if(count!=7 || parts[0]!="RATES") break;
            string result=Rates(parts);
            if(result=="" || !SendLine(socket,result)) break;
         }
         if(GetTickCount64()>=next_status)
         {
            active=SendLine(socket,TerminalInfoInteger(TERMINAL_CONNECTED) ? "{\"type\":\"status\",\"connected\":true}" : "{\"type\":\"status\",\"connected\":false}");
            next_status=GetTickCount64()+1000;
         }
         if(active && TerminalInfoInteger(TERMINAL_CONNECTED) && GetTickCount64()>=next_poll)
         {
            // shortcut: latest quote snapshots; add durable cursors only for a raw-tick delivery requirement.
            for(int i=0;i<total && active;i++)
            {
               MqlTick ticks[];
               if(CopyTicks(symbols[i],ticks,COPY_TICKS_ALL,0,1)!=1) continue;
               int digits=(int)SymbolInfoInteger(symbols[i],SYMBOL_DIGITS);
               string tick=StringFormat("{\"type\":\"tick\",\"seq\":%I64d,\"symbol\":\"%s\",\"connected\":true,\"timeMscRaw\":%I64d,\"bid\":\"%s\",\"ask\":\"%s\"}",
                  ++sequence,symbols[i],ticks[0].time_msc,DoubleToString(ticks[0].bid,digits),DoubleToString(ticks[0].ask,digits));
               active=SendLine(socket,tick);
            }
            next_poll=GetTickCount64()+MathMax(PollMilliseconds,100);
         }
         Sleep(20);
      }
      SocketClose(socket);
      Print("MarketDataService: reconnecting");
      Sleep(1000);
   }
}
