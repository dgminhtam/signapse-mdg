#property service
#property strict

void OnStart()
{
   string name="MdgFileSharingCheck.txt";
   int f=FileOpen(name,FILE_WRITE|FILE_TXT|FILE_ANSI);
   if(f==INVALID_HANDLE) return;
   FileWriteString(f,"public test fixture"); FileClose(f);
   int first=FileOpen(name,FILE_READ|FILE_TXT|FILE_ANSI);
   int second=FileOpen(name,FILE_READ|FILE_TXT|FILE_ANSI);
   bool exclusive_blocks=(first!=INVALID_HANDLE && second==INVALID_HANDLE);
   if(second!=INVALID_HANDLE) FileClose(second);
   if(first!=INVALID_HANDLE) FileClose(first);
   first=FileOpen(name,FILE_READ|FILE_TXT|FILE_ANSI|FILE_SHARE_READ);
   second=FileOpen(name,FILE_READ|FILE_TXT|FILE_ANSI|FILE_SHARE_READ);
   bool shared_reads=(first!=INVALID_HANDLE && second!=INVALID_HANDLE);
   if(second!=INVALID_HANDLE) FileClose(second);
   if(first!=INVALID_HANDLE) FileClose(first);
   FileDelete(name);
   f=FileOpen("MdgFileSharingCheck.json",FILE_WRITE|FILE_TXT|FILE_ANSI,0,CP_UTF8);
   if(f==INVALID_HANDLE) return;
   FileWriteString(f,StringFormat("{\"exclusiveBlocksSecondReader\":%s,\"sharedAllowsBothReaders\":%s}",
      exclusive_blocks ? "true" : "false",shared_reads ? "true" : "false"));
   FileClose(f);
}
