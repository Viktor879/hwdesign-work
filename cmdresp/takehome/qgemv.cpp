#include "qgemv.hpp"
static Word word(ap_uint<64> data, bool last) {
#pragma HLS INLINE
    Word w; w.data=data; w.keep=255; w.strb=255; w.last=last; return w;
}
void qgemv(hls::stream<Word>& in, hls::stream<Word>& out,
           unsigned &halted, unsigned &error, unsigned &tx_id) {
#pragma HLS INTERFACE axis port=in
#pragma HLS INTERFACE axis port=out
#pragma HLS INTERFACE s_axilite port=halted bundle=control
#pragma HLS INTERFACE s_axilite port=error bundle=control
#pragma HLS INTERFACE s_axilite port=tx_id bundle=control
#pragma HLS INTERFACE s_axilite port=return bundle=control
    ap_int<8> weights[8][8];
    ap_int<16> bias[8];
#pragma HLS ARRAY_PARTITION variable=weights complete
#pragma HLS ARRAY_PARTITION variable=bias complete
    ap_uint<64> payload[32];
    unsigned shift=0; bool valid=false;
    halted=0; error=0; tx_id=0;
commands: while(true) {
        unsigned hdr[3]={0,0,0};
        unsigned id=0xffffffffU, err=0;
header: for(int k=0;k<3;k++) {
            Word w=in.read();
            hdr[k]=w.data.range(31,0);
            if(k==1 && w.data.range(63,32)==0 && w.keep==255 && w.strb==255) id=hdr[1];
            if(w.data.range(63,32)!=0 || w.keep!=255 || w.strb!=255 || bool(w.last)!=(k==2)) {err=1;break;}
        }
        if(!err) {
            if(hdr[0]<1 || hdr[0]>3) err=2;
            else if(id==0xffffffffU || (hdr[0]==1 && hdr[2]>15) || (hdr[0]==3 && hdr[2]!=0)) err=3;
            else if(hdr[0]==2 && (hdr[2]<1 || hdr[2]>32)) err=4;
            else if(hdr[0]==2 && !valid) err=5;
        }
        if(err) {halted=1;error=err;tx_id=id;return;}
        if(hdr[0]==3) return;
        int count=hdr[0]==1 ? 10 : int(hdr[2]);
receive: for(int k=0;k<count;k++) {
#pragma HLS PIPELINE II=1
            Word w=in.read(); payload[k]=w.data;
            if(w.last && k!=count-1) {err=6;break;}
            if(!w.last && k==count-1) {err=7;break;}
        }
        if(err) {halted=1;error=err;tx_id=id;return;}
        if(hdr[0]==1) {
load_rows: for(int i=0;i<8;i++) {
#pragma HLS PIPELINE II=1
                for(int j=0;j<8;j++) {
#pragma HLS UNROLL
                    weights[i][j]=payload[i].range(8*j+7,8*j);
                }
            }
            for(int i=0;i<8;i++) {
#pragma HLS UNROLL
                bias[i]=payload[8+i/4].range(16*(i%4)+15,16*(i%4));
            }
            shift=hdr[2]; valid=true;
            out.write(word(id,true));
        } else {
            out.write(word(id,true));
compute: for(int v=0;v<count;v++) {
#pragma HLS PIPELINE II=1
                ap_uint<64> result=0;
rows: for(int i=0;i<8;i++) {
#pragma HLS UNROLL
                    ap_int<32> acc=bias[i];
cols: for(int j=0;j<8;j++) {
#pragma HLS UNROLL
                        ap_int<8> x=payload[v].range(8*j+7,8*j);
                        ap_int<16> prod=weights[i][j]*x;
                        acc+=prod;
                    }
                    ap_int<32> mag=acc<0 ? ap_int<32>(-acc) : acc;
                    ap_int<32> q=shift ? ap_int<32>((mag+(ap_int<32>(1)<<(shift-1)))>>shift) : mag;
                    if(acc<0) q=-q;
                    ap_int<8> y=q>127 ? 127 : (q< -128 ? -128 : q.to_int());
                    result.range(8*i+7,8*i)=ap_uint<8>(y);
                }
                out.write(word(result,v==count-1));
            }
        }
    }
}
