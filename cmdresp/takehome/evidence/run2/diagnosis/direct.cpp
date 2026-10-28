#include <hls_directio.h>
#include <ap_int.h>
void direct(hls::ap_hs<ap_uint<81>>& out){
#pragma HLS INTERFACE ap_hs port=out
#pragma HLS INTERFACE ap_ctrl_hs port=return
 out.write(123);
}
