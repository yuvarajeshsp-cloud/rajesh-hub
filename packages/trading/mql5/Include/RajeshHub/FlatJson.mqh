#ifndef __RAJESHHUB_FLATJSON_MQH__
#define __RAJESHHUB_FLATJSON_MQH__

// Minimal readers for ONE flat JSON object with string or number values
// (no nesting, no arrays) -- the format the hub's Python bridges write.
// Same logic as the readers in SignalReceiverEA.mq5, shared here.

string JGetStr(const string json,const string key)
  {
   string pattern="\""+key+"\":\"";
   int p=StringFind(json,pattern);
   if(p<0) return "";
   p+=StringLen(pattern);
   int q=StringFind(json,"\"",p);
   if(q<0) return "";
   return StringSubstr(json,p,q-p);
  }

bool JHas(const string json,const string key)
  {
   return StringFind(json,"\""+key+"\":")>=0;
  }

double JGetNum(const string json,const string key)
  {
   string pattern="\""+key+"\":";
   int p=StringFind(json,pattern);
   if(p<0) return 0.0;
   p+=StringLen(pattern);
   int q=p;
   int len=StringLen(json);
   while(q<len)
     {
      ushort c=StringGetCharacter(json,q);
      if(c==',' || c=='}') break;
      q++;
     }
   string s=StringSubstr(json,p,q-p);
   StringTrimLeft(s);
   StringTrimRight(s);
   return StringToDouble(s);
  }

// Escape a value for writing back out as a JSON string.
string JEsc(const string v)
  {
   string s=v;
   StringReplace(s,"\\","\\\\");
   StringReplace(s,"\"","'");
   return s;
  }

string ReadCommonText(const string relPath)
  {
   int h=FileOpen(relPath,FILE_COMMON|FILE_READ|FILE_TXT|FILE_ANSI|FILE_SHARE_READ);
   if(h==INVALID_HANDLE) return "";
   string content="";
   while(!FileIsEnding(h))
      content+=FileReadString(h);
   FileClose(h);
   return content;
  }

bool WriteCommonText(const string relPath,const string text)
  {
   string tmp=relPath+".tmp";
   int h=FileOpen(tmp,FILE_COMMON|FILE_WRITE|FILE_TXT|FILE_ANSI);
   if(h==INVALID_HANDLE) return false;
   FileWriteString(h,text);
   FileClose(h);
   return FileMove(tmp,FILE_COMMON,relPath,FILE_COMMON|FILE_REWRITE);
  }

#endif
