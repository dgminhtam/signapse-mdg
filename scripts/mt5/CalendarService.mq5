#property service
#property version "1.00"
// Dedicated economic-calendar Service; no trading or database writes.
input string ReceiverHost="mdg-tcp-smoke.test";
input uint ReceiverPort=9002;
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

string JsonString(string value)
{
   string result="\"";
   for(int i=0;i<StringLen(value);i++)
   {
      ushort code=StringGetCharacter(value,i);
      if(code==34) result+="\\\"";
      else if(code==92) result+="\\\\";
      else if(code<32) result+=StringFormat("\\u%04X",code);
      else result+=StringSubstr(value,i,1);
   }
   return result+"\"";
}

bool CalendarRequest(string &parts[],long &from,long &to)
{
   if(ArraySize(parts)!=5 || parts[0]!="CALENDAR" || StringLen(parts[1])!=32) return false;
   for(int i=0;i<32;i++)
      if(StringFind("0123456789abcdef",StringSubstr(parts[1],i,1))<0) return false;
   for(int n=2;n<=3;n++)
   {
      if(StringLen(parts[n])<1 || StringLen(parts[n])>12) return false;
      for(int i=0;i<StringLen(parts[n]);i++)
         if(StringFind("0123456789",StringSubstr(parts[n],i,1))<0) return false;
   }
   if(StringLen(parts[4])<1 || StringLen(parts[4])>8) return false;
   for(int i=0;i<StringLen(parts[4]);i++)
      if(StringFind("ABCDEFGHIJKLMNOPQRSTUVWXYZ",StringSubstr(parts[4],i,1))<0) return false;
   from=StringToInteger(parts[2]);
   to=StringToInteger(parts[3]);
   return from>0 && to>from && to-from<=8*86400;
}

string CalendarRaw(long value,bool present)
{
   return present ? JsonString((string)value) : "null";
}

bool Calendar(int socket,string &parts[])
{
   long from=0,to=0;
   if(!CalendarRequest(parts,from,to)) return false;
   string id=parts[1],currency=parts[4]=="ALL" ? "" : parts[4];
   ulong started=GetTickCount64();
   long server_before=(long)TimeTradeServer(),utc_before=(long)TimeGMT();
   MqlCalendarValue values[];
   ResetLastError();
   int native_count=CalendarValueHistory(values,(datetime)from,(datetime)to,NULL,currency);
   int error=GetLastError();
   long fetch_ms=(long)(GetTickCount64()-started);
   long server_after=(long)TimeTradeServer(),utc_after=(long)TimeGMT();
   string begin=StringFormat("{\"type\":\"calendar_begin\",\"id\":\"%s\",\"fromRaw\":%I64d,\"toRaw\":%I64d,\"currency\":%s,\"nativeCount\":%d,\"arrayCount\":%d,\"error\":%d,\"fetchMs\":%I64d,\"serverTimeBefore\":%I64d,\"utcTimeBefore\":%I64d,\"serverTimeAfter\":%I64d,\"utcTimeAfter\":%I64d}",
      id,from,to,JsonString(parts[4]),native_count,ArraySize(values),error,fetch_ms,server_before,utc_before,server_after,utc_after);
   if(!SendLine(socket,begin)) return false;
   string phase="complete";
   int written=0,metadata_failures=0,out_of_range=0;
   if(native_count<0 || error!=0)
   {
      phase="fetch";
      if(error==0) error=-1;
   }
   else if(native_count!=ArraySize(values) || native_count>10000)
   { phase="limit"; error=-1; }
   else for(int i=0;i<native_count && !IsStopped();i++)
   {
      if((long)values[i].time<from || (long)values[i].time>=to)
      { out_of_range++; continue; }
      MqlCalendarEvent event;
      MqlCalendarCountry country;
      ResetLastError();
      if(!CalendarEventById(values[i].event_id,event))
      { error=GetLastError(); phase="event_metadata"; }
      else
      {
         ResetLastError();
         if(!CalendarCountryById(event.country_id,country))
         { error=GetLastError(); phase="country_metadata"; }
      }
      if(phase!="complete")
      {
         metadata_failures++;
         if(error==0) error=-1;
         if(!SendLine(socket,StringFormat("{\"type\":\"calendar_error\",\"id\":\"%s\",\"eventId\":%s,\"valueId\":%s,\"error\":%d,\"phase\":%s}",
            id,JsonString((string)values[i].event_id),JsonString((string)values[i].id),error,JsonString(phase)))) return false;
         break;
      }
      string row=StringFormat("{\"type\":\"calendar_event\",\"id\":\"%s\",\"valueId\":%s,\"eventId\":%s,\"timeRaw\":%I64d,\"periodRaw\":%I64d,\"revision\":%d,\"actualRaw\":%s,\"forecastRaw\":%s,\"previousRaw\":%s,\"revisedPreviousRaw\":%s,\"impactType\":%d,",
         id,JsonString((string)values[i].id),JsonString((string)values[i].event_id),(long)values[i].time,(long)values[i].period,values[i].revision,
         CalendarRaw(values[i].actual_value,values[i].HasActualValue()),CalendarRaw(values[i].forecast_value,values[i].HasForecastValue()),
         CalendarRaw(values[i].prev_value,values[i].HasPreviousValue()),CalendarRaw(values[i].revised_prev_value,values[i].HasRevisedValue()),(int)values[i].impact_type);
      row+=StringFormat("\"name\":%s,\"eventCode\":%s,\"importance\":%d,\"timeMode\":%d,\"unit\":%d,\"multiplier\":%d,\"digits\":%d,\"sourceUrl\":%s,\"countryId\":%s,\"country\":%s,\"countryCode\":%s,\"currency\":%s}",
         JsonString(event.name),JsonString(event.event_code),(int)event.importance,(int)event.time_mode,(int)event.unit,(int)event.multiplier,(int)event.digits,
         JsonString(event.source_url),JsonString((string)event.country_id),JsonString(country.name),JsonString(country.code),JsonString(country.currency));
      if(!SendLine(socket,row)) return false;
      written++;
   }
   if(IsStopped()) return false;
   return SendLine(socket,StringFormat("{\"type\":\"calendar_end\",\"id\":\"%s\",\"count\":%d,\"error\":%d,\"phase\":%s,\"totalMs\":%I64d,\"metadataFailures\":%d,\"outOfRangeCount\":%d}",
      id,written,error,JsonString(phase),(long)(GetTickCount64()-started),metadata_failures,out_of_range));
}

bool CalendarSelfCheck()
{
   string parts[]={"CALENDAR","0123456789abcdef0123456789abcdef","1000000000","1000604800","ALL"};
   long from=0,to=0;
   if(!CalendarRequest(parts,from,to) || to-from!=7*86400) return false;
   parts[3]="1000777600";
   if(CalendarRequest(parts,from,to)) return false;
   parts[3]="1000604800";
   parts[4]="USD\n";
   if(CalendarRequest(parts,from,to)) return false;
   return JsonString("\"\\\n")=="\"\\\"\\\\\\u000A\"" && CalendarRaw(LONG_MIN,false)=="null" && CalendarRaw(0,true)=="\"0\"";
}


void OnStart()
{
   if(!CalendarSelfCheck()) return;
   while(!IsStopped() && !TerminalInfoInteger(TERMINAL_CONNECTED)) Sleep(1000);
   if(AccountInfoString(ACCOUNT_SERVER)!="VantageMarkets-Demo" || TerminalInfoInteger(TERMINAL_TRADE_ALLOWED)) return;
   int f=FileOpen("MarketDataToken.txt",FILE_READ|FILE_TXT|FILE_ANSI,0,CP_UTF8);
   if(f==INVALID_HANDLE) return;
   string token=FileReadString(f); FileClose(f);
   if(StringLen(token)<32) return;
   while(!IsStopped())
   {
      if(AccountInfoString(ACCOUNT_SERVER)!="VantageMarkets-Demo" || TerminalInfoInteger(TERMINAL_TRADE_ALLOWED)) return;
      int socket=SocketCreate();
      if(socket==INVALID_HANDLE) { Sleep(1000); continue; }
      if(!SocketConnect(socket,ReceiverHost,ReceiverPort,2000)) { SocketClose(socket); Sleep(1000); continue; }
      SocketTimeouts(socket,1000,1000);
      string hello=StringFormat("{\"type\":\"hello\",\"version\":1,\"server\":\"VantageMarkets-Demo\",\"service\":true,\"role\":\"calendar\",\"algoTrading\":false,\"serverTime\":%I64d,\"utcTime\":%I64d}",(long)TimeTradeServer(),(long)TimeGMT());
      bool active=SendLine(socket,"HELLO "+token) && SendLine(socket,hello);
      string buffer=""; ulong next_status=0;
      while(active && !IsStopped() && SocketIsConnected(socket))
      {
         if(AccountInfoString(ACCOUNT_SERVER)!="VantageMarkets-Demo" || TerminalInfoInteger(TERMINAL_TRADE_ALLOWED)) return;
         uint available=SocketIsReadable(socket);
         if(available>4096) break;
         if(available>0)
         {
            uchar bytes[]; int size=SocketRead(socket,bytes,available,1000);
            if(size<=0) break;
            buffer+=CharArrayToString(bytes,0,size,CP_UTF8);
            if(StringLen(buffer)>4096) break;
         }
         int newline=StringFind(buffer,"\n");
         if(newline>=0)
         {
            string command=StringSubstr(buffer,0,newline); buffer=StringSubstr(buffer,newline+1);
            string parts[];
            StringSplit(command,'\t',parts);
            active=Calendar(socket,parts);
         }
         if(GetTickCount64()>=next_status)
         {
            active=active && SendLine(socket,TerminalInfoInteger(TERMINAL_CONNECTED) ? "{\"type\":\"status\",\"connected\":true}" : "{\"type\":\"status\",\"connected\":false}");
            next_status=GetTickCount64()+1000;
         }
         Sleep(20);
      }
      SocketClose(socket); Sleep(1000);
   }
}
