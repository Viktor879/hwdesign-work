#!/usr/bin/env bash
set -euo pipefail
root=$(pwd)
mkdir -p build/run1_reproduction
cd build/run1_reproduction
/eda/xilinx/2026.1/Vivado/bin/xvlog "$root"/build_repro_run1/solution1/syn/verilog/*.v
/eda/xilinx/2026.1/Vivado/bin/xvlog -sv "$root/src/rtl_suite.sv"
/eda/xilinx/2026.1/Vivado/bin/xelab rtl_suite -L unisims_ver -s reproduction -debug typical
for mode in 0 1; do
 /eda/xilinx/2026.1/Vivado/bin/xsim reproduction -tclbatch "$root/scripts/reproduce_run1_suite.tcl" -testplusarg "MODE=$mode" -testplusarg "FIXTURES=$root/fixtures/stress.txt" -testplusarg "CSV=$root/evidence/run2/diagnosis/original-$mode.csv" > "$root/evidence/run2/diagnosis/original-$mode.log" 2>&1
 cp reproduction.vcd "$root/evidence/run2/diagnosis/original-$mode.vcd"
 rg 'Fatal:' "$root/evidence/run2/diagnosis/original-$mode.log"
done
