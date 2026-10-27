# QGEMV-8: Programmable INT8 Neural-Network Inference Accelerator

**Assignment:** Command-Response Mini-Project, Part 3 — Take-home  
**Specification version:** 2

Build a Vitis HLS kernel following the Waveflow `stream_inband` example (https://sdrangan.github.io/waveflow/docs/examples/stream_inband/) and the course command-response pattern. Where they differ, the course command-response protocol takes precedence.

Implement an independently checked, bit-exact Python golden model, the HLS kernel, and a testbench. First run and pass Python verification and C simulation. Treat successful C simulation as the first verification checkpoint, then continue with RTL co-simulation and synthesis as explicitly required for the take-home project. Compare Python, C simulation, and RTL co-simulation bit for bit. Do not build a Python timing model.

## Operation

Implement programmable 8×8 signed INT8 matrix-vector multiplication:

`a[i] = b[i] + Σ(W[i][j] × x[j]), j = 0..7`, for `i = 0..7`.

`x` is eight signed INT8 activations, `W` is an 8×8 signed INT8 weight matrix, and `b` is eight signed INT16 biases. Use mathematically exact signed INT32 accumulation; the legal operand ranges cannot overflow INT32.

Compute:

`y[i] = sat_int8(round_away_from_zero(a[i] / 2^shift))`

`shift` is an integer from 0 through 15 inclusive. Round to the nearest integer; exact halfway ties round away from zero. Shift zero leaves the accumulator unchanged before saturation. Saturate to [-128,127], never wrap. Do not use floating-point arithmetic in the hardware datapath.

Every PROCESS command computes independent vectors in input order. Weights, biases, and shift persist between commands within one activation. A successful second CONFIG atomically replaces all three; it affects subsequent PROCESS commands only. No state, configuration, or prior error persists across activations.

## Requirements

- Exactly eight signed INT8 inputs and eight signed INT8 outputs per vector.
- Exactly 64 signed multiplications per vector, with eight independent dot products and signed INT16 biases accumulated in INT32.
- Support 1–32 vectors per PROCESS command; the maximum is 256 input elements and 256 output elements.
- Parameters and data travel entirely in-band on AXI4-Stream; AXI-Lite is used only for activation control and error/status reporting.
- The agent chooses command codes, header layouts, transport widths, word packing, and output file formats, documents those choices, and keeps Python/HLS/testbenches consistent.
- **Throughput target:** No more than 32 clock cycles per completed eight-element output vector, averaged over a valid PROCESS batch of 32 vectors, measured from the first accepted input-payload transfer to the last accepted output-payload transfer, inclusive, with no externally inserted stalls. Eight elements constitute one vector regardless of transport packing.
- **Clock target:** Vitis synthesis-estimated clock period strictly below 10 ns. A warning concerning clock-uncertainty margin alone is not a failure. Record achieved II, latency, LUT, FF, DSP, and BRAM usage without inventing resource limits.
- A missed performance target must be recorded as FAIL, not used as permission for unlimited kernel restructuring.

## Commands and parameters

Use separately TLAST-terminated command-header and payload bursts. Likewise, separately terminate response headers and result payloads. Every successful response echoes the initiating transaction ID.

**CONFIG:** The header carries `tx_id` and unsigned integer `shift`. The payload contains exactly 64 INT8 weights in row-major order followed by eight INT16 biases. Validate `shift` in [0,15] before reading the payload. Buffer and validate the entire payload before atomically replacing the existing configuration. On success, emit one acknowledgement response header with matching `tx_id`; no result payload.

**PROCESS:** The header carries `tx_id` and integer `nvec`, where 1 ≤ `nvec` ≤ 32. Validate this range and require an existing successful CONFIG before reading payload data. The payload contains exactly `8*nvec` signed INT8 elements. Validate the entire payload before generating results. On success, emit one response header with matching `tx_id` followed by exactly `8*nvec` INT8 results in input-vector order.

**END:** A header-only command with `tx_id`, no input payload, and no response. It terminates the activation successfully.

For transport packing, the number of elements, not padding bytes, determines the declared payload length. Any padding bits must have deterministic documented values. Invalid parameters must be detected before reading their associated payloads.

## Errors

Expose AXI-Lite status registers `halted`, `error`, and `tx_id`; use a 32-bit unsigned transaction-ID/status field. Reserve `0xFFFFFFFF` as an invalid or unavailable transaction-ID sentinel; legal command transaction IDs are `0x00000000` through `0xFFFFFFFE`. Using the reserved ID in an otherwise well-formed header is an invalid-parameter error.

At the start of every activation, clear `halted`, `error`, `tx_id`, and configuration validity. On successful END, return with `halted=0` and `error=0`.

Detect and assign distinct, documented error codes for:

1. Malformed or incorrectly TLAST-terminated command header.
2. Unknown command code.
3. Invalid CONFIG shift or reserved transaction ID.
4. Invalid PROCESS vector count (0 or greater than 32).
5. PROCESS before successful CONFIG.
6. Premature TLAST before the expected last payload word.
7. Missing TLAST at the expected last payload word.

For malformed headers, record the decoded offending `tx_id` if its field was received completely and unambiguously. Otherwise record `0xFFFFFFFF`. An undecodable or incomplete `tx_id` must never inherit a transaction ID from an earlier command. Test both cases.

If multiple errors could apply, use this priority: header framing; unknown command; invalid header parameters; missing configuration; payload framing. During payload reception, early TLAST takes precedence when observed; missing final TLAST is detected at the expected last word. Do not consume extra words attempting to find TLAST.

On every error, set `halted=1`, record the error code and offending `tx_id`, close any already-started output burst using TLAST, and immediately return without reading further input. Do not acknowledge or return results for the failing command; earlier completed responses remain valid. The host must reset the stream path before another activation. An invalid CONFIG must not partially modify configuration. Buffer valid PROCESS input completely before producing a response, so a malformed PROCESS cannot produce partial results.

## Verification

First verify the Python golden model independently against hand calculations and a separate NumPy reference using sufficiently wide integer arithmetic. Do not treat agreement between two copies of the same implementation as independent verification.

Required hand-checkable examples:

1. Identity W, zero bias, shift 0; input `[10,-5,20,3,8,0,-12,7]` returns the identical vector.
2. Row weights `[1,-1,2,0,0,0,0,0]`, input `[1,2,3,0,0,0,0,0]`, bias 3, shift 0: output element is `1-2+6+3=8`.
3. All-zero W and bias produce all-zero output.
4. Accumulator +3, shift 1 produces +2; accumulator -3, shift 1 produces -2. Include exact ties, non-ties, positive/negative values, and shift 15.
5. Eight +127 weights times eight +127 inputs, bias zero, shift 0 saturates to +127. Eight +127 weights times eight -128 inputs, bias zero, shift 0 saturates to -128.
6. Confirm a negative accumulator with magnitude below half the quantization divisor rounds to zero.

Required scenarios:

- Valid batches of sizes 1 and 32, mixed signs, zero, INT8 extrema, nonzero biases, shifts 0 and 15, rounding boundaries, and positive/negative saturation.
- Multiple PROCESS commands after one CONFIG, confirming state persistence.
- CONFIG A → PROCESS → CONFIG B → PROCESS → END in one activation, confirming atomic replacement and that each PROCESS uses the appropriate configuration.
- Every listed error category, including both decodable and undecodable malformed headers, reserved `tx_id`, illegal sizes, early TLAST, and missing TLAST.
- For each error, verify `halted`, exact error code, `tx_id`, response count, absence of failing-command results, and correct output-burst termination.
- Immediately after **each error activation**, run a completely fresh activation with new streams and CONFIG → PROCESS → END; it must pass, demonstrating no stale state.
- Verify transaction-ID echo, element order, output count, TLAST placement, absence of extra responses, and success status after END.

Execution order: pass independent Python checks, then bit-exact HLS C simulation. Only after C simulation passes, run HLS synthesis and a single RTL co-simulation testbench run covering every scenario in sequence, invoking the kernel once per activation with fresh streams. Compare all successful outputs bit for bit. Do not stop the take-home implementation after C simulation.

Measure throughput and latency using RTL co-simulation, and clock, II, and resources using synthesis. Preserve raw evidence. If a tool fails or a check is not completed, mark it as not run or FAIL as appropriate; never claim success without execution.

## results.md

Write `results.md` with exactly these seven named sections:

1. **Interface:** Full host-visible command/response encodings, transport packing and padding, header fields, burst/TLAST rules, AXI-Lite registers, error codes, and malformed-header `tx_id` handling.
2. **Design:** Kernel architecture, loops, buffers, state, arithmetic widths, and how the throughput target is reached or why it is missed.
3. **Targets:** Required and measured performance, PASS/FAIL, and the evidence filename for each. Include co-simulation latency and throughput, synthesis estimated clock and II, LUT/FF/DSP/BRAM usage, and "no target" where none was specified.
4. **Verification:** Independent golden-model checks, followed by one row per scenario recording expected/observed results, Python/C simulation/co-simulation agreement, error status, recovery outcome, PASS/FAIL, and evidence filename.
5. **Assumptions:** **An exhaustive numbered ambiguity/decision register.** Identify every place this prompt was silent, incomplete, underspecified, or reasonably interpretable in multiple ways, even if the agent successfully implemented it. For EACH item record: (a) the affected prompt section or quoted requirement, (b) the missing or ambiguous decision, (c) the exact resolution chosen, (d) why, and (e) whether it affects numerical output, errors, protocol, hardware size, throughput, or only naming/formatting. Include unrequested defaults and interface choices; cross-reference Interface where details are already documented. Do not replace this with generic assumptions or silently omit a decision because tests passed.
6. **Open Items:** Every unresolved ambiguity, failed test, missing evidence, tool limitation, or unfinished task, with "None" only when justified.
7. **Run History:** One row per implementation run recording specification version, changes, commands/tests actually executed, outcomes, and evidence. Separate the C-simulation checkpoint from subsequent synthesis and RTL co-simulation.

Every reported measurement and PASS/FAIL must cite an actual retained log, comparison output, or synthesis report committed with the project. A reviewer must be able to reproduce or inspect the evidence.

## Revision history

| Version | Change | Why |
| --- | --- | --- |
| 1 | Initial QGEMV-8 specification | Define bounded, bit-exact INT8 matrix-vector inference with command-response error handling and independent verification. |
| 2 | Explicit malformed-header transaction-ID sentinel, exhaustive ambiguity register, and staged verification checkpoint | Address Part 3 grader feedback while retaining the take-home requirement to complete co-simulation and synthesis. |
