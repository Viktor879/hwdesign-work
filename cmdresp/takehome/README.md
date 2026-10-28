# QGEMV-8 (prompt.md specification version 2)

Run from this project directory on the NYU server:

```bash
/home/cp4523/hwdesign/.venv/bin/python golden.py > evidence/python.log
QGEMV_STAGE=csim vitis-run --mode hls --tcl run.tcl > evidence/csim_unsandboxed.log 2>&1
# Only continue if the C simulation exit code is zero:
QGEMV_STAGE=rtl vitis-run --mode hls --tcl run.tcl > evidence/synth_cosim.log 2>&1
/eda/xilinx/2026.1/Vivado/bin/vivado -mode batch -source export_wave.tcl -log evidence/wave_export.log -journal evidence/wave_export.jou > evidence/wave_export_console.log 2>&1
python3 analyze.py > evidence/analysis.log 2>&1
```

Vitis requires access to the NYU license service; execute the tool commands outside the Codex sandbox. The commands reuse the existing project without deleting it. The RTL stage synthesizes and performs exactly one co-simulation invocation, whose C++ testbench invokes the kernel separately for every activation, with fresh streams.

`golden.py` contains the untimed, pure integer golden model, hand checks, separate NumPy int64 reference, and deterministic fixture generation. `data/cases.json` is the readable expected protocol trace; `data/cases.txt` is its decimal text serialization consumed by `tb.cpp`. Each case declares input/output word counts and expected status; each word is `unsigned_64bit_data TLAST`. `qgemv.cpp`/`qgemv.hpp` are the synthesizable implementation. All comparison CSV rows compare the complete output words and sidebands as well as status; the expected words are retained in the fixtures.

See `results.md` for the full protocol, measured results, per-scenario evidence, assumptions, and limitations. Keep `evidence/` and `qgemv_hls/solution1/{syn,sim}/` with the source when handing in; they contain actual tool reports and simulation traces. No Python timing model is used.

The local Waveflow example's generated wrapper drops header TLAST diagnostics and its evaluator emits results before checking payload framing. This implementation uses hand-written HLS to implement the course protocol. CONFIG parameters travel in-band rather than through the example's coefficient AXI-Lite registers. The example's `open_project`/`open_solution` Tcl batch flow works with Vitis 2026.1, with deprecation/IDE visibility warnings. Use `vitis-run --mode hls --tcl` rather than the older `vitis_hls -f` executable. The selected FPGA part matches the example; the requested clock is 8 ns. The Python SimPy timing/calibration and timing comparison build steps in the example are intentionally omitted as required by prompt.md.
