#include "qgemv.hpp"
#include <fstream>
#include <iostream>
#include <vector>
#include <string>
static Word readword(std::istream &f){unsigned long long d;unsigned l,k,s;f>>d>>l>>k>>s;Word w;w.data=d;w.last=l;w.keep=k;w.strb=s;return w;}
int main(int argc,char**argv){
 std::ifstream f(argc>1?argv[1]:"fixtures/cases.txt");if(!f)return 2;
 std::ofstream csv("comparison.csv");csv<<"scenario,outputs,status,consumption,result\n";
 int count;f>>count;for(int t=0;t<count;t++){
 std::string name;unsigned ni,no,eh,ee,et,consumed;f>>name>>ni>>no>>eh>>ee>>et>>consumed;
 hls::stream<Word> in("in"),out("out");for(unsigned i=0;i<ni;i++)in.write(readword(f));
 std::vector<Word> expected;for(unsigned i=0;i<no;i++)expected.push_back(readword(f));
 // Functional acknowledgement sequence; no clock or latency model.
 hls::ap_none<ap_uint<32>> completed("completed");
 completed.write(0); // Activation baseline.
 for(unsigned i=0;i<=no;i++)completed.write(i);
 unsigned h=99,e=99,id=99;qgemv_core(in,out,h,e,id,completed);
 bool ok=h==eh&&e==ee&&id==et;
 for(auto w:expected){if(out.empty()){ok=false;break;}auto a=out.read();ok &= a.data==w.data&&a.last==w.last&&a.keep==w.keep&&a.strb==w.strb;}
 ok &= out.empty();
#ifndef RTL_ONLY
 ok &= in.size()==ni-consumed;
#endif
 csv<<name<<","<<no<<","<<h<<":"<<e<<":"<<id<<","<<consumed<<","<<(ok?"PASS":"FAIL")<<"\n";
 if(!ok){std::cerr<<"FAIL "<<name<<"\n";return 1;}
 }
 std::cout<<"PASS "<<count<<" activations\n";return 0;
}
