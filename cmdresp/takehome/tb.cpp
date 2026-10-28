#include "qgemv.hpp"
#include <fstream>
#include <iostream>
#include <string>
int main(int argc,char**argv) {
 bool v3=argc>3 && std::string(argv[3])=="v3";
 if(argc<3) return 2;
 std::ifstream f(argv[1]); std::ofstream log(argv[2]);
 log<<"scenario,halted,error,tx_id,words,status\n";
 int cases; f>>cases;
 for(int c=0;c<cases;c++) {
  std::string name; unsigned ni,no,eh,ee,et; f>>name>>ni>>no>>eh>>ee>>et;
  hls::stream<Word> in,out;
  for(unsigned k=0;k<ni;k++) { unsigned long long d; int last; f>>d>>last; Word w;w.data=d;w.last=last;unsigned keep=255,strb=255;if(v3) f>>keep>>strb;w.keep=keep;w.strb=strb;in.write(w); }
  unsigned h=99,e=99,t=99;
  qgemv(in,out,h,e,t);
  bool ok=h==eh&&e==ee&&t==et;
  for(unsigned k=0;k<no;k++) {
   unsigned long long d;int last;f>>d>>last;
   if(out.empty()) {ok=false;continue;}
   Word w=out.read();
   if(w.data!=d || w.last!=last || w.keep!=255 || w.strb!=255) ok=false;
  }
  if(!out.empty() || !in.empty()) ok=false;
  log<<name<<","<<h<<","<<e<<","<<t<<","<<no<<","<<(ok?"PASS":"FAIL")<<"\n";
  std::cout<<name<<" "<<(ok?"PASS":"FAIL")<<std::endl;
  if(!ok || !f) return 1;
 }
 return 0;
}
