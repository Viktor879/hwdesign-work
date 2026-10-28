#!/usr/bin/env bash
set -euo pipefail
python_bin=${PYTHON:-/home/cp4523/hwdesign/.venv/bin/python}
"$python_bin" scripts/fixtures.py > evidence/run2/python/checks.log
cp evidence/python/checks.json evidence/run2/python/checks.json
python3 scripts/stress_fixtures.py
vitis-run --mode hls --tcl scripts/run2_synth.tcl > evidence/run2/synthesis.log 2>&1
vitis-run --mode hls --tcl scripts/run2_cosim.tcl > evidence/run2/rtl/cosim.log 2>&1
bash scripts/run2_stress.sh > evidence/run2/rtl/stress-build.log 2>&1
bash scripts/run2_original_checker.sh > evidence/run2/rtl/original-checker.log 2>&1
/eda/xilinx/2026.1/Vivado/bin/vivado -mode batch -source scripts/run2_integrated.tcl -notrace > evidence/run2/integrated-synthesis.log 2>&1
python3 scripts/retain_run2.py
python3 scripts/analyze_rtl.py evidence/run2/rtl/stress-4.vcd evidence/run2/rtl > evidence/run2/rtl/analysis.log
