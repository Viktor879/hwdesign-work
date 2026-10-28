#include <hls_directio.h>
#include <ap_int.h>
#include <iostream>
void manual(hls::ap_vld<ap_uint<81>>&,hls::ap_none<bool>&,hls::ap_none<bool>&);
int main(){hls::ap_vld<ap_uint<81>> d;hls::ap_none<bool> v,r;for(int i=0;i<4;i++)r.write(true);manual(d,v,r);for(int i=0;i<4;i++){if(d.read()!=i)return 1;}std::cout<<"PASS manual probe\n";return 0;}
