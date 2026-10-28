#include <hls_directio.h>
#include <ap_int.h>
#include <etc/ap_utils.h>
void manual(hls::ap_vld<ap_uint<81>>& data, hls::ap_none<bool>& valid, hls::ap_none<bool>& ready){
#pragma HLS INTERFACE ap_vld port=data
#pragma HLS INTERFACE ap_none port=valid register
#pragma HLS INTERFACE ap_none port=ready
#pragma HLS INTERFACE ap_ctrl_hs port=return
 valid.write(false);
 for(int i=0;i<4;i++){
  data.write(ap_uint<81>(i));valid.write(true);
  ap_wait();
  while(!ready.read()) {ap_wait();}
  valid.write(false);ap_wait();
 }
}
