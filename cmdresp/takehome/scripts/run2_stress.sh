#!/usr/bin/env bash
set -euo pipefail
root=$(pwd)
mkdir -p build/run2_stress
cd build/run2_stress
/eda/xilinx/2026.1/Vivado/bin/xvlog "$root"/build_run2/solution1/syn/verilog/*.v
/eda/xilinx/2026.1/Vivado/bin/xvlog -sv "$root/src/qgemv.sv" "$root/src/rtl_suite.sv"
/eda/xilinx/2026.1/Vivado/bin/xelab rtl_suite -L unisims_ver -s suite -debug typical
for mode in 4 0 1 2 3; do
 /eda/xilinx/2026.1/Vivado/bin/xsim suite -tclbatch "$root/scripts/run2_stress_capture.tcl" -testplusarg "MODE=$mode" -testplusarg "FIXTURES=$root/fixtures/stress.txt" -testplusarg "CSV=$root/evidence/run2/rtl/stress-$mode.csv" > "$root/evidence/run2/rtl/stress-$mode.log" 2>&1
 cp suite.vcd "$root/evidence/run2/rtl/stress-$mode.vcd"
 if rg -q 'Fatal:|ERROR:' "$root/evidence/run2/rtl/stress-$mode.log"; then
  echo "FAIL mode=$mode; see evidence/run2/rtl/stress-$mode.log"
  exit 1
 fi
 rg 'PASS RTL suite' "$root/evidence/run2/rtl/stress-$mode.log"
done
