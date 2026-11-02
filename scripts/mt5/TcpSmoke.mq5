#property service
#property version "1.00"

input string ReceiverHost = "mdg-tcp-smoke.test";
input uint ReceiverPort = 9001;

bool SendLine(int socket, string line)
{
   uchar bytes[];
   int size = StringToCharArray(line + "\n", bytes, 0, WHOLE_ARRAY, CP_UTF8) - 1;
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

string Rates()
{
   MqlRates bars[];
   ResetLastError();
   int count = CopyRates("XAUUSD", PERIOD_M1, 1, 3, bars);
   int error = GetLastError();
   string result = StringFormat("{\"type\":\"rates\",\"error\":%d,\"bars\":[", error);
   int digits = (int)SymbolInfoInteger("XAUUSD", SYMBOL_DIGITS);
   for(int i = 0; i < count; i++)
   {
      if(i > 0) result += ",";
      result += StringFormat(
         "{\"timeRaw\":%I64d,\"o\":\"%s\",\"h\":\"%s\",\"l\":\"%s\",\"c\":\"%s\"}",
         (long)bars[i].time, DoubleToString(bars[i].open, digits),
         DoubleToString(bars[i].high, digits), DoubleToString(bars[i].low, digits),
         DoubleToString(bars[i].close, digits));
   }
   return result + "]}";
}

void OnStart()
{
   int file = FileOpen("TcpSmokeToken.txt", FILE_READ | FILE_TXT | FILE_ANSI, 0, CP_UTF8);
   if(file == INVALID_HANDLE) { Print("TcpSmoke: token file missing"); return; }
   string token = FileReadString(file);
   FileClose(file);
   if(StringLen(token) < 32 || AccountInfoString(ACCOUNT_SERVER) != "VantageMarkets-Demo")
   { Print("TcpSmoke: invalid token or unexpected broker"); return; }
   if(!SymbolSelect("XAUUSD", true)) { Print("TcpSmoke: symbol unavailable"); return; }
   ulong deadline = GetTickCount64() + 180000;
   bool stop = false;
   int session = 0;
   while(!IsStopped() && !stop && GetTickCount64() < deadline)
   {
      int socket = SocketCreate();
      if(socket == INVALID_HANDLE) { PrintFormat("TcpSmoke: SocketCreate error %d", GetLastError()); return; }
      if(!SocketConnect(socket, ReceiverHost, ReceiverPort, 2000))
      {
         PrintFormat("TcpSmoke: connect error %d", GetLastError());
         SocketClose(socket);
         Sleep(1000);
         continue;
      }
      SocketTimeouts(socket, 1000, 1000);
      session++;
      PrintFormat("TcpSmoke: connected session %d", session);
      string hello = StringFormat(
         "{\"type\":\"hello\",\"server\":\"VantageMarkets-Demo\",\"build\":%d,\"service\":%s,\"algoTrading\":%s}",
         (int)TerminalInfoInteger(TERMINAL_BUILD),
         MQLInfoInteger(MQL_PROGRAM_TYPE) == PROGRAM_SERVICE ? "true" : "false",
         TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) ? "true" : "false");
      bool connected = SendLine(socket, "HELLO " + token) && SendLine(socket, hello);
      string buffer = "";
      ulong next_tick = 0;
      while(connected && !stop && !IsStopped() && GetTickCount64() < deadline)
      {
         uint available = SocketIsReadable(socket);
         if(available > 0)
         {
            if(available > 8192) break;
            uchar bytes[];
            int size = SocketRead(socket, bytes, available, 1000);
            if(size <= 0) break;
            buffer += CharArrayToString(bytes, 0, size, CP_UTF8);
            if(StringLen(buffer) > 8192) break;
            int newline = StringFind(buffer, "\n");
            while(newline >= 0 && connected)
            {
               string command = StringSubstr(buffer, 0, newline);
               buffer = StringSubstr(buffer, newline + 1);
               if(command == "PING") connected = SendLine(socket, "{\"type\":\"pong\"}");
               else if(command == "RATES") connected = SendLine(socket, Rates());
               else if(command == "RECONNECT") connected = false;
               else if(command == "STOP") { stop = true; connected = false; }
               else { Print("TcpSmoke: rejected unknown command"); connected = false; }
               newline = StringFind(buffer, "\n");
            }
         }
         if(connected && GetTickCount64() >= next_tick)
         {
            // shortcut: latest samples only; use a cursor before promising tick delivery.
            MqlTick ticks[];
            if(CopyTicks("XAUUSD", ticks, COPY_TICKS_ALL, 0, 1) == 1)
            {
               int digits = (int)SymbolInfoInteger("XAUUSD", SYMBOL_DIGITS);
               string tick = StringFormat(
                  "{\"type\":\"tick\",\"symbol\":\"XAUUSD\",\"connected\":%s,\"timeMscRaw\":%I64d,\"bid\":\"%s\",\"ask\":\"%s\"}",
                  TerminalInfoInteger(TERMINAL_CONNECTED) ? "true" : "false",
                  ticks[0].time_msc, DoubleToString(ticks[0].bid, digits), DoubleToString(ticks[0].ask, digits));
               connected = SendLine(socket, tick);
            }
            next_tick = GetTickCount64() + 250;
         }
         if(!SocketIsConnected(socket)) break;
         Sleep(20);
      }
      SocketClose(socket);
      if(!stop) Sleep(500);
   }
   PrintFormat("TcpSmoke: finished sessions=%d stop=%s", session, stop ? "true" : "false");
}
