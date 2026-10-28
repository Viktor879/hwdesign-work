# QGEMV-8 (prompt.md specification version 3)

Run from this project directory on the NYU server:

```bash
export QGEMV_VERSION=v3
/home/cp4523/hwdesign/.venv/bin/python golden.py > evidence/v3/python.log 2>&1
QGEMV_STAGE=csim vitis-run --mode hls --tcl run.tcl > evidence/v3/csim.log 2>&1
# Continue only after C simulation succeeds:
QGEMV_STAGE=rtl vitis-run --mode hls --tcl run.tcl > evidence/v3/synth_cosim.log 2>&1
vivado -mode batch -source export_wave.tcl -log evidence/v3/wave_export.log -journal evidence/v3/wave_export.jou > evidence/v3/wave_export_console.log 2>&1
python3 analyze.py > evidence/v3/analysis.log 2>&1
python3 audit_v3.py > evidence/v3/final_audit.log 2>&1
```

Vitis requires access to the NYU license service; execute the tool commands outside the Codex sandbox. The commands reuse the existing project without deleting it. The RTL stage synthesizes and performs exactly one co-simulation invocation, whose C++ testbench invokes the kernel separately for every activation, with fresh streams.

`golden.py` contains the untimed, pure integer golden model, hand checks, separate NumPy int64 reference, and deterministic fixture generation. `data/cases.json` is the readable expected protocol trace; `data/cases.txt` is its decimal text serialization consumed by `tb.cpp`. Each case declares input/output word counts and expected status. V3 input words are `unsigned_64bit_data TLAST TKEEP TSTRB`; output expectations remain `unsigned_64bit_data TLAST`, with both enables checked as 255. With `QGEMV_VERSION=v3`, fixture paths are `data/v3/` and evidence paths are `evidence/v3/`; the original `data/` fixtures remain unchanged. `qgemv.cpp`/`qgemv.hpp` are the synthesizable implementation. All comparison CSV rows compare the complete output words and sidebands as well as status; the expected words are retained in the fixtures.

See `results.md` for the full protocol, measured results, per-scenario evidence, assumptions, and limitations. Keep `evidence/`, `data/`, and the selectively retained `qgemv_hls{,_v3}/solution1/{syn,sim}/` with the source when handing in; they contain actual tool reports and simulation traces. No Python timing model is used.

The local Waveflow example's generated wrapper drops header TLAST diagnostics and its evaluator emits results before checking payload framing. This implementation uses hand-written HLS to implement the course protocol. CONFIG parameters travel in-band rather than through the example's coefficient AXI-Lite registers. The example's `open_project`/`open_solution` Tcl batch flow works with Vitis 2026.1, with deprecation/IDE visibility warnings. Use `vitis-run --mode hls --tcl` rather than the older `vitis_hls -f` executable. The selected FPGA part matches the example; the requested clock is 8 ns. The Python SimPy timing/calibration and timing comparison build steps in the example are intentionally omitted as required by prompt.md.

V3 is the specification at commit `e380d18`, following the Part 4 **27/30** feedback (three Iteration points lost). Runs 1–10 and their evidence remain v2. The v3 project is `qgemv_hls_v3`; `.gitignore` retains reports, control-map RTL and native waveform databases while excluding compiler/simulator binaries and scratch builds. Do not add ignored files with `git add -f`.

The v3 iteration adds repeated-ID regressions (zero, ordinary and maximum legal ID), partial header TKEEP/TSTRB at every position, ignored payload enables, and combined error-precedence cases. It also disables AXI stream interface register slices: the historical external trace demonstrated prefetch of subsequent header words before the prior response completed. The sequential source loop alone did not prevent that external acceptance. New waveform checks cover validation-before-response and response-before-next-header, as well as data, TLAST, both enables, counts and no-stall performance. This changes interface buffering while retaining all 64 unrolled products and the compute pipeline.

`evidence/v3/spec.sha256` is the authoritative current specification hash; `evidence/spec.sha256` remains the historical v2 hash. `evidence/v3/baseline_manifest.json` binds all original tracked files before this iteration, and `executed_sources.sha256` identifies the sources/fixtures used for the corrected-kernel tool run. `results_before_v3.md` preserves the prior report, including the original Runs 1–10 text. Re-running commands overwrites **v3** results; archive them first if another iteration is needed. Default tool paths without `QGEMV_VERSION=v3` are retained for historical compatibility and should not be used for new verification.

Packaging correction: see `evidence/v3/packaging_correction.md` for provenance, retained artifacts, historical manifest scope and the current read-only audit. Use `python3 audit_packaging.py` for the current submission audit; `audit_v3.py` and its logs describe the original implementation-time audit and assume its historical HEAD/specification. Generated simulator vectors and HDL wrappers remain local and ignored.
