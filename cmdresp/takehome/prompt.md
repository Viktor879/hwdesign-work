# QGEMV-8: Programmable Signed-INT8 Matrix-Vector Accelerator

**Assignment:** NYU Command-Response Mini-Project, Part 3 (specification for the Part 4 take-home implementation)  
**Specification version:** 1

Build a Vitis HLS accelerator based on the Waveflow `stream_inband` example (https://sdrangan.github.io/waveflow/docs/examples/stream_inband/) and the course command-response design pattern. Where the example and the course protocol differ, follow the course protocol. Implement a bit-exact Python golden model independently checked against hand calculations and NumPy, a synthesizable HLS kernel, and a testbench. Run Python checks, HLS C simulation, HLS synthesis, and RTL co-simulation, and compare successful numerical outputs bit for bit. Do **not** create a Python timing model.

## Operation and arithmetic

For each eight-element signed INT8 input vector `x`, compute eight outputs independently:

`acc[i] = bias[i] + sum(W[i][j] * x[j] for j=0..7)` for `i=0..7`.

`W` has exactly 8x8 signed INT8 weights (row-major); `bias` has exactly eight signed INT16 entries. Multiplications are signed and accumulation is mathematically exact in signed INT32. The legal ranges do not overflow INT32. For a configured unsigned `shift` from 0 to 15, calculate:

`y[i] = saturate_int8(round_nearest_ties_away_from_zero(acc[i] / 2**shift))`.

Round to nearest with exact ties **away from zero**, for both positive and negative values; `shift=0` means no division/rounding. Saturate to [-128,127], never wrap. Use integer arithmetic only in the hardware datapath. An acceptable implementation uses a nonnegative INT32 magnitude, adds `2**(shift-1)` when `shift>0`, right-shifts, restores the sign, then saturates. Equivalent exact arithmetic is permitted.

Configuration (weights, biases, shift) persists between PROCESS commands **within one activation**. A later successful CONFIG atomically replaces the complete configuration; subsequent PROCESS commands use the replacement. An invalid CONFIG never partially modifies configuration. Every activation starts with invalid configuration and cleared error/status; no usable state survives between activations.

## Interfaces, encoding, and framing

All command parameters, weights, biases, inputs, and results travel **in-band** over AXI4-Stream. AXI-Lite is only for `ap_ctrl_hs` activation control and the three status outputs `halted`, `error`, and `tx_id`. Do not create AXI-Lite coefficient or command-parameter registers.

Both input and output streams use **64-bit TDATA**, **8-bit TKEEP and TSTRB**, TLAST, and the standard TVALID/TREADY handshake; no TUSER, TID, or TDEST. Legal host transfers and every output transfer have TKEEP=TSTRB=0xFF. For payload words, ignore received TKEEP/TSTRB and treat all data lanes as valid; these payload sidebands introduce no separate error category. For command-header words, however, either sideband differing from 0xFF is **malformed-header error 1**. Use two's-complement signed values, with the earliest array element in the least-significant lane. There are no length-prefix words or payload padding words.

A command header always contains **three distinct 64-bit words** in this order:

1. Opcode in bits [31:0], with bits [63:32]=0 and TLAST=0.
2. Unsigned 32-bit transaction ID in bits [31:0], upper bits zero and TLAST=0.
3. Unsigned 32-bit parameter in bits [31:0], upper bits zero and TLAST=1.

Nonzero upper header bits, incorrect header TLAST, or incorrect header TKEEP/TSTRB cause error 1 immediately at the first malformed word. Parse the complete 32-bit parameter without truncation; negative values encoded in two's complement are invalid if outside its unsigned range. Do not consume later header words after detecting an error. Successful response headers are **one 64-bit word** with the initiating transaction ID in bits [31:0], zero upper bits, TKEEP=TSTRB=0xFF and TLAST=1. Header bursts and data bursts are separately TLAST-terminated.

Commands (the only legal opcodes):

| Opcode | Command | Parameter | Input payload | Successful output |
| --- | --- | --- | --- | --- |
| 1 | CONFIG | `shift` in [0,15] | Exactly 10 words: 8 words of row-major INT8 weights (one row per word), followed by 2 words of INT16 biases (four biases per word) | One response header; no result payload |
| 2 | PROCESS | `nvec` in [1,32] | Exactly `nvec` words, each containing eight signed INT8 inputs | One response header followed by exactly `nvec` output words, eight INT8 results each |
| 3 | END | Must be zero | No payload | No response; successful activation ends |

All data payloads have TLAST=0 except on their expected final word, where TLAST=1. A single-word payload has TLAST=1. PROCESS results follow the separately terminated response header in input-vector order; only the final result word has TLAST=1. The declared element count, not padding, determines payload size. No extra command response or data is allowed.

Legal transaction IDs are `0x00000000` through `0xFFFFFFFE`, including zero. IDs **may be reused** on successive commands; they need not be unique. `0xFFFFFFFF` is reserved as the invalid/unavailable ID sentinel. CONFIG and PROCESS response headers echo their own command's ID. The AXI-Lite `tx_id` status is exclusively the **offending ID on error**; it is zero throughout any successful activation, including after a valid END regardless of END's ID.

## Command order, buffering, and state

Receive commands in strict arrival order. **Do not accept the next command header at the external input handshake until validation and all successful output transfers for the current command are complete**, including the last TLAST transfer. Do not overlap a later CONFIG with an earlier PROCESS or emit results before validating its full input. Account for HLS AXI interface register slices/prefetch: disable or otherwise configure them when necessary so external TVALID/TREADY acceptance also obeys this contract, and verify it from actual RTL waveforms.

Buffer and validate the **entire** CONFIG payload before installing weights/biases/shift; mark config valid and acknowledge only after installation. Buffer and validate the **entire** PROCESS payload before issuing its response header or any results; support 1–32 vectors. Physical register/memory clearing is unnecessary if a validity flag prevents use before CONFIG and if PROCESS always overwrites its required input buffer. At activation entry set shift=0, configuration validity=false, and `(halted,error,tx_id)=(0,0,0)`; successful END returns exactly `(0,0,0)`.

Input reads block awaiting data; missing words alone do not cause a timeout. Missing final TLAST is detected **only upon accepting the expected final payload word without TLAST**. Output writes honor backpressure and may block without constituting an error. The no-stall performance target is measured without externally injected stalls.

## Errors, precedence, and recovery

Expose exact 32-bit AXI-Lite status values `halted`, `error`, and `tx_id`. The error code definitions are:

| Code | Condition |
| --- | --- |
| 0 | Success |
| 1 | Malformed header: bad header TLAST, upper bits, TKEEP, or TSTRB |
| 2 | Unknown opcode |
| 3 | Reserved transaction ID, invalid CONFIG shift, or nonzero END parameter |
| 4 | PROCESS count 0 or >32 |
| 5 | PROCESS before a successful CONFIG |
| 6 | Payload TLAST asserted before the expected last word |
| 7 | Payload lacks TLAST at the expected last word |

**Priority:** detect malformed header framing at the first bad header word; otherwise check unknown opcode, then reserved transaction ID, then opcode-specific parameter validity, then missing CONFIG, then payload framing. In particular, an otherwise valid PROCESS header with both ID=`0xFFFFFFFF` and illegal `nvec` reports **code 3**, not 4. Check invalid header parameters **before reading payload**. During payload reception, early TLAST (6) is detected as observed; a missing final TLAST (7) is detected at the expected final word. Never drain extra input looking for TLAST.

Decode a new transaction ID for each header. Preserve the offending decoded ID if word 1 arrived completely with zero upper bits and TKEEP=TSTRB=0xFF, **even when its TLAST is wrong**. If word 1 has not arrived, or its upper bits/byte enables are invalid, report sentinel `0xFFFFFFFF`. A malformed later header word retains the valid decoded ID. Never inherit an ID from a previous command.

On every error set `halted=1`, `error` to the specified code and `tx_id` to the offending decoded ID or sentinel; return immediately without reading additional input or generating a response/result for the failing command. Every prior successful output burst has already finished with TLAST; no extra closing/error word is needed. The host discards/resets the stream path, then starts a wholly **fresh activation with fresh streams** for recovery. Do not resume the aborted command.

Use the generated `ap_ctrl_hs` AXI-Lite register map: control at 0x00, normal interrupt control at 0x04/0x08/0x0C, read-only `halted`, `error`, `tx_id` at 0x10, 0x20, 0x30 and corresponding `ap_vld` at 0x14, 0x24, 0x34. The generated RTL register map is authoritative; the host waits for activation completion before interpreting final status. Interrupts and auto-restart need not be enabled.

## Architecture and targets

Compute the eight independent dot products with completely partitioned weights and biases and fully unrolled row/column arithmetic, implementing **64 signed products per vector**. Use signed INT8 operands, signed INT16 product storage and biases, and mathematically exact signed INT32 sums. Target compute-loop II=1 and input-receive-loop II=1, while reporting measured results honestly. HLS may choose DSP versus fabric multipliers and buffer-memory implementation. No top-level II=1 requirement or hard LUT/FF/DSP/BRAM resource limit is imposed.

Use the course example's FPGA part **`xc7z020clg484-1`** and request an **8 ns clock** with installed Vitis HLS 2026.1; report the version actually used. The **estimated synthesis clock target** is strictly **less than 10 ns**. A clock-uncertainty-margin warning alone does not fail that target. Report achieved compute II/depth, synthesis-estimated clock, and LUT, FF, DSP and BRAM usage; mark genuinely unavailable values as unavailable rather than inventing them.

The **external throughput target** is at most **32 clock cycles per completed eight-element vector**, averaged across a valid 32-vector PROCESS batch without external stalls. Measure inclusive cycles from the first accepted PROCESS input-payload transfer at the **external DUT AXI stream interface** through the final accepted result-payload transfer; divide by 32. Report first-result latency, full-batch latency, and any tool activation latency separately. Convert measured cycles to time using the actual RTL simulation clock, not the synthesis-estimated period. Missing the target must be recorded **FAIL**, never used as permission for unlimited redesign.

## Verification and execution

Verify the Python model against **independent** hand calculations and a separately written NumPy INT64 reference (at least 3,200 randomized comparisons, with deterministic seed). Do not simply compare two copies of one implementation. Include hand checks:

1. Identity weights, zero bias, shift 0: `[10,-5,20,3,8,0,-12,7]` returns itself.
2. One row `[1,-1,2,0,0,0,0,0]`, `x=[1,2,3,0,0,0,0,0]`, bias 3, shift 0 gives `8`.
3. All-zero weights and bias give zero.
4. Accumulator +3/−3 at shift 1 produces +2/−2; cover positive/negative ties, non-ties, shift 15, and a small negative magnitude rounding to zero.
5. Eight +127 weights with eight +127 inputs at shift 0 saturate to +127; eight +127 weights with eight −128 inputs saturate to −128.

Required integration tests: nvec=1 and 32, at least four independently measured 32-vector batches, INT8 extremes, mixed signs, shifts 0 and 15, bias, rounding and saturation, repeated PROCESS after one CONFIG, CONFIG A → PROCESS → CONFIG B → PROCESS → END, legal repeated IDs including zero, malformed header TKEEP/TSTRB and upper padding, decodable/undecodable bad headers, unknown opcode, reserved ID, nonzero END parameter, invalid shift/count, PROCESS before CONFIG, both payload TLAST errors, simultaneous reserved-ID and invalid count, and strict no-prefetch command sequencing at the external AXI port. Test error precedence. Validate all response headers, counts, TLAST/sidebands, statuses and absence of results for failing commands. **Immediately after each error activation, run a fresh-stream CONFIG → PROCESS → END activation and require PASS.** Include blocking/backpressure behavior where feasible, without inserting external stalls into throughput measurement.

**Execution sequence:** first independent Python tests; next complete HLS C simulation. Only after C simulation passes, run HLS synthesis and **one full RTL co-simulation testbench run** containing the required activations (new input/output streams per activation). Compare outputs/status bit for bit; preserve actual logs, CSV comparisons, synthesis XML/reports, and externally measured RTL timing and command-order evidence. Do not substitute a Python timing model, report a tool as PASS without running it, or conceal failures. If an environment or license issue prevents a stage, describe it as not run or FAIL with evidence.

## results.md and evidence

Write `results.md` with **exactly seven top-level sections**, titled:

1. **Interface** — complete transport, command/response encodings, sidebands, TLAST, parameters, registers and error-code priority needed by a host.
2. **Design** — datapath, loops, buffers, state, arithmetic widths, sequencing, and throughput rationale.
3. **Targets** — every required target and measured clock, II, latency, throughput and resources, PASS/FAIL and an exact retained evidence filename; use “no target” for unconstrained quantities.
4. **Verification** — independent hand/NumPy checks followed by one row per scenario with expected/observed outputs, Python/C/RTL comparisons, status/error/recovery result and evidence file.
5. **Assumptions** — exhaustive numbered register of *remaining* ambiguous/silent choices, with specification clause, exact decision, reason and whether it affects numerical values, errors, protocol, size, throughput, or merely packaging. Mark any consequential unresolved choice clearly as an Open Item, not a silently accepted assumption.
6. **Open Items** — unresolved questions, failures, missing evidence or tool limitations; “None” only when justified.
7. **Run History** — one row per **real** agent implementation/verification run: active spec version, observed problem/decision, code change, actual commands and outcomes, and specific evidence. Distinguish the C-simulation checkpoint from synthesis and RTL co-simulation, and do not invent runs. If a later prompt revision is needed, its reason must refer to the precise preceding run finding and assumption number; commit that revision **before** rerunning the agent.

Every numerical claim and PASS/FAIL in Targets or Verification must cite an **actual committed file**, consistent with the report. Preserve raw evidence but **do not commit entire generated Vitis projects or simulation trees** (`sim/tv`, generated `autotb`, compiled objects, temporary waveforms, caches or uncited logs). Copy only necessary native synthesis/co-simulation reports, the cited AXI-Lite register-map RTL, and cited waveforms or derived handshake timing traces into a deliberately organized `evidence/` directory. Make `.gitignore` exclude generated directories; check all cited evidence paths exist and are staged. Keep a reproducible README and scripts; do not expose credentials. Preserve revision and run histories truthfully.

## Revision history

| Version | Change | Why |
| --- | --- | --- |
| 1 | Initial QGEMV-8 application and interface specification | Specify the mathematical operation, bit-exact fixed-point behavior, complete command-response protocol, host-visible errors, recovery, state, architecture, independent verification, performance criteria, and auditable deliverables before the first implementation run. |
