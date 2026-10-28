#include "qgemv.hpp"
#include <etc/ap_utils.h>
static Word word(ap_uint<64> d,bool last){
#pragma HLS INLINE
 Word w; w.data=d; w.keep=255; w.strb=255; w.last=last; return w;
}
void qgemv_core(hls::stream<Word>& in,hls::stream<Word>& out,unsigned &halted,unsigned &error,unsigned &tx_id, hls::ap_none<ap_uint<32>>& completed){
#pragma HLS INTERFACE axis port=in register_mode=off
#pragma HLS INTERFACE axis port=out register_mode=both
#pragma HLS INTERFACE ap_none port=completed
#pragma HLS INTERFACE s_axilite port=return bundle=control
#pragma HLS INTERFACE s_axilite port=halted bundle=control offset=0x10
#pragma HLS INTERFACE s_axilite port=error bundle=control offset=0x20
#pragma HLS INTERFACE s_axilite port=tx_id bundle=control offset=0x30
 ap_int<8> weights[8][8]; ap_int<16> bias[8];
#pragma HLS ARRAY_PARTITION variable=weights complete dim=0
#pragma HLS ARRAY_PARTITION variable=bias complete
 ap_uint<64> buffer[32];
 // completed is internal feedback from the wrapper's actual AXI handshake counter.
 // Equality is modulo 2^32; each command has at most 33 outstanding beats.
 ap_uint<32> expected_completed=completed.read();
 bool valid=false; unsigned shift=0; halted=0; error=0; tx_id=0;
 commands: while(true){
 unsigned hdr[3]; unsigned id=0xffffffffu; unsigned err=0;
 header: for(int k=0;k<3;k++){
 Word w=in.read(); bool bytes=w.keep==255 && w.strb==255 && w.data.range(63,32)==0;
 if(k==1 && bytes) id=w.data.range(31,0);
 if(!bytes || w.last!=(k==2)){err=1;break;}
 hdr[k]=w.data.range(31,0);
 }
 if(!err){
 if(hdr[0]<1 || hdr[0]>3) err=2;
 else if(id==0xffffffffu) err=3;
 else if((hdr[0]==1 && hdr[2]>15)||(hdr[0]==3 && hdr[2]!=0)) err=3;
 else if(hdr[0]==2 && (hdr[2]<1 || hdr[2]>32)) err=4;
 else if(hdr[0]==2 && !valid) err=5;
 }
 if(err){halted=1;error=err;tx_id=id;return;}
 if(hdr[0]==3) return;
 unsigned n=hdr[0]==1?10:hdr[2];
 receive: for(unsigned k=0;k<n;k++){
#pragma HLS PIPELINE II=1
 Word w=in.read(); buffer[k]=w.data;
 if(w.last!=(k==n-1)){err=w.last?6:7;break;}
 }
 if(err){halted=1;error=err;tx_id=id;return;}
 if(hdr[0]==1){
 install_rows: for(int i=0;i<8;i++){
 install_cols: for(int j=0;j<8;j++){
#pragma HLS UNROLL
 weights[i][j]=buffer[i].range(j*8+7,j*8);
 }}
 install_bias: for(int i=0;i<8;i++) bias[i]=buffer[8+i/4].range((i%4)*16+15,(i%4)*16);
 shift=hdr[2];valid=true;out.write(word(id,true));
 ap_wait(); // Scheduling barrier: issue the write before polling its acknowledgement.
 ++expected_completed;
 config_complete: while(completed.read()!=expected_completed) {}
 }else{
 out.write(word(id,true));
 compute: for(unsigned k=0;k<n;k++){
#pragma HLS PIPELINE II=1
 ap_uint<64> result=0;
 rows: for(int i=0;i<8;i++){
#pragma HLS UNROLL
 ap_int<32> sum=bias[i];
 cols: for(int j=0;j<8;j++){
#pragma HLS UNROLL
 ap_int<8> x=buffer[k].range(j*8+7,j*8); ap_int<16> product=weights[i][j]*x;sum+=ap_int<32>(product);
 }
 ap_int<32> magnitude=sum<0?ap_int<32>(-sum):sum;
 if(shift) magnitude=(magnitude+(ap_int<32>(1)<<(shift-1)))>>shift;
 ap_int<32> rounded=sum<0?ap_int<32>(-magnitude):magnitude;
 ap_int<8> y=rounded>127?127:rounded< -128?-128:(int)rounded;
 result.range(i*8+7,i*8)=y;
 }
 out.write(word(result,k==n-1));
 }
 ap_wait(); // All compute-loop writes must be issued before acknowledgement polling.
 expected_completed+=n+1;
 process_complete: while(completed.read()!=expected_completed) {}

 }
 }
}
