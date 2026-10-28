#!/usr/bin/env bash
set -euo pipefail
root=$(pwd)
mkdir -p build/run2_original_checker
cd build/run2_original_checker
/eda/xilinx/2026.1/Vivado/bin/xvlog "$root"/build_run2/solution1/syn/verilog/*.v
/eda/xilinx/2026.1/Vivado/bin/xvlog -sv "$root/src/qgemv.sv" "$root/src/rtl_stress.sv"
/eda/xilinx/2026.1/Vivado/bin/xelab rtl_stress -L unisims_ver -s original_checker -debug typical
/eda/xilinx/2026.1/Vivado/bin/xsim original_checker -tclbatch "$root/scripts/stress_capture.tcl"
cp stress.vcd "$root/evidence/run2/rtl/original-checker.vcd"
if rg -q 'Fatal:|ERROR:' xsim.log; then exit 1; fi
rg 'PASS RTL stress completed' xsim.log
