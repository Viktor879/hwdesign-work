#pragma once
#include <ap_int.h>
#include <ap_axi_sdata.h>
#include <hls_stream.h>
#include <hls_directio.h>
using Word=ap_axiu<64,0,0,0>;
void qgemv_core(hls::stream<Word>& in, hls::stream<Word>& out, unsigned &halted,unsigned &error,unsigned &tx_id, hls::ap_none<ap_uint<32>>& completed);
