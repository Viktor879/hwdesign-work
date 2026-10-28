#pragma once
#include <ap_axi_sdata.h>
#include <hls_stream.h>
using Word = ap_axiu<64,0,0,0>;
void qgemv(hls::stream<Word>& in, hls::stream<Word>& out,
           unsigned &halted, unsigned &error, unsigned &tx_id);
