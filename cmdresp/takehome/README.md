# QGEMV-8 — Part 4, Run 2 / specification v1

Run 2 corrects Run 1's AXI output failure without changing `prompt.md`. Final Python, HLS C simulation, HLS synthesis, complete native RTL co-simulation, and integrated external AXI tests pass. [results.md](results.md) retains Run 1 as FAIL and records the actual corrective trials and final measurements.

The **production top is `src/qgemv.sv`**. It instantiates the unmodified HLS-generated `qgemv_core`, passes through the specified streams/AXI-Lite interface, and counts actual output TVALID && TREADY transfers. The HLS source enables the output register slice and guards the next header's first input read using this internal count. The feedback port is internal, with no new host-visible port/register. The wrapper does not override or manufacture TVALID. Building only the bare HLS core omits the required feedback and is not the delivered accelerator.

From this directory, with installed Vitis/Vivado 2026.1 and license access:

```bash
PYTHON=/home/cp4523/hwdesign/.venv/bin/python bash scripts/run2.sh
python3 scripts/report_run2.py
python3 scripts/audit_run2.py
```

`bash scripts/run.sh` is an alias for the current Run 2 flow. Override PYTHON with another Python environment containing NumPy. The flow uses `xc7z020clg484-1` and an 8 ns request. Single-level `build_run2/` avoids the source-path registration issue found in Run 1. All generated projects/simulator trees are ignored. The allowlisted native reports and actual external waveforms are copied to `evidence/run2/`; no simulator transaction-vector tree is retained for Git.

The flow runs independent hand/NumPy checks, then full C simulation before synthesis and one complete final native HLS RTL co-simulation. The core-only C/native testbench uses functional internal completion-count stimulus; it makes no external timing claim. The separate integrated RTL suite tests all fixtures at the actual production top with its real hardware feedback: no stalls, READY low before VALID, multi-cycle stalls after observing VALID, alternating readiness, and deterministic randomized readiness. It asserts held VALID, complete data/sideband stability, exact output order/count, complete-input-before-output, no command prefetch, error-stop consumption, statuses, fresh recovery and bounded completion. The exact unchanged Run 1 stress testbench is additionally rerun by `scripts/run2_original_checker.sh`. XSim `$fatal` is detected from raw logs even if the simulator returns shell success.

Only mode 4 supplies performance data. `scripts/analyze_rtl.py` samples **pre-edge** external signals and compares all accepted words/sidebands to the fixtures. Recompute measurements without rerunning RTL:

```bash
python3 scripts/analyze_rtl.py evidence/run2/rtl/stress-4.vcd evidence/run2/rtl
```

The signed arithmetic is unchanged in `src/kernel.cpp`; `scripts/model.py` remains an independently checked Python golden, and `scripts/fixtures.py` separately checks NumPy INT64 and hand cases. There is no Python timing model. `src/tb.cpp` checks all fixture activations with fresh streams. `src/rtl_suite.sv` and `fixtures/stress.txt` add external protocol gates and live assertions. `scripts/run2_integrated.tcl` synthesizes both the native core and production wrapper; its utilization is reported separately from the HLS estimate.

To reproduce the original defect with the *same strengthened checker*, without changing Run 2:

```bash
vitis-run --mode hls --tcl scripts/reproduce_run1_synth.tcl
bash scripts/reproduce_run1_suite.sh
```

Those diagnostic modes intentionally produce the retained initial-READY and post-VALID FAIL assertions. They compile the archived Run 1 kernel in isolated ignored build directories. Original Run 1 evidence remains at its original paths; `evidence/run1-source/` freezes its report/source context. Diagnostic prototypes are not production alternatives. The current report/audit scripts preserve history rather than overwriting it with a new Run 1.

References: [Waveflow stream_inband](https://sdrangan.github.io/waveflow/docs/examples/stream_inband/), the installed `examples/stream_inband/` reference, [official course protocol](https://sdrangan.github.io/hwdesign/docs/labs/cmdresp/pattern.html), [Vitis 2026.1 AXI register modes](https://docs.amd.com/r/en-US/ug1399-vitis-hls/Registered-AXI4-Stream-Interfaces), and [supported Direct I/O](https://docs.amd.com/r/en-US/ug1399-vitis-hls/Mapping-Direct-I/O-Streams-to-a-Wire-Interface). Waveflow example-RAG was unavailable in Run 1; its local example and official documentation were used. No implementation/results from the older project were imported.

No specification v2 is needed. The submission audit selectively stages an explicit reviewed allowlist; nothing is committed or pushed. The exact staged paths, byte sizes and purposes are in [the submission manifest](evidence/submission/staged-files.tsv), with [payload hashes](evidence/submission/SHA256SUMS) and [independent checks](evidence/submission/audit.json). Review these and submit the production wrapper, HLS source, testbench/model/fixtures/scripts, report and cited evidence; exclude all build/simulation trees. Board implementation/routing is outside this Part 4 verification scope.
