# QGEMV-8: Programmable INT8 Neural-Network Inference Accelerator

**Assignment:** Command-Response Mini-Project, Part 3 — Take-home  
**Specification version:** 3

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
- Command codes, header layouts, transport widths, and word packing are fixed by the v3 clarifications below. The agent chooses output file formats, documents those choices, and keeps Python/HLS/testbenches consistent.
- **Throughput target:** No more than 32 clock cycles per completed eight-element output vector, averaged over a valid PROCESS batch of 32 vectors, measured from the first accepted input-payload transfer to the last accepted output-payload transfer, inclusive, with no externally inserted stalls. Eight elements constitute one vector regardless of transport packing.
- **Clock target:** Vitis synthesis-estimated clock period strictly below 10 ns. A warning concerning clock-uncertainty margin alone is not a failure. Record achieved II, latency, LUT, FF, DSP, and BRAM usage without inventing resource limits.
- A missed performance target must be recorded as FAIL, not used as permission for unlimited kernel restructuring.

## Commands and parameters

Use separately TLAST-terminated command-header and payload bursts. Likewise, separately terminate response headers and result payloads. Every successful response echoes the initiating transaction ID.

**CONFIG:** The header carries `tx_id` and unsigned integer `shift`. The payload contains exactly 64 INT8 weights in row-major order followed by eight INT16 biases. Validate `shift` in [0,15] before reading the payload. Buffer and validate the entire payload before atomically replacing the existing configuration. On success, emit one acknowledgement response header with matching `tx_id`; no result payload.

**PROCESS:** The header carries `tx_id` and integer `nvec`, where 1 ≤ `nvec` ≤ 32. Validate this range and require an existing successful CONFIG before reading payload data. The payload contains exactly `8*nvec` signed INT8 elements. Validate the entire payload before generating results. On success, emit one response header with matching `tx_id` followed by exactly `8*nvec` INT8 results in input-vector order.

**END:** A header-only command with `tx_id` and parameter zero, no input payload, and no response. A valid END terminates the activation successfully; a nonzero parameter is error code 3.

For transport packing, the number of elements, not padding bytes, determines the declared payload length. Any padding bits must have deterministic documented values. Invalid parameters must be detected before reading their associated payloads.

## Errors

Expose AXI-Lite status registers `halted`, `error`, and `tx_id`; use a 32-bit unsigned transaction-ID/status field. Reserve `0xFFFFFFFF` as an invalid or unavailable transaction-ID sentinel; legal command transaction IDs are `0x00000000` through `0xFFFFFFFE`. Using the reserved ID in an otherwise well-formed header is an invalid-parameter error.

At the start of every activation, clear `halted`, `error`, `tx_id`, and configuration validity. On successful END, return with `halted=0`, `error=0`, and `tx_id=0`.

Detect and assign distinct, documented error codes for:

1. Malformed or incorrectly TLAST-terminated command header.
2. Unknown command code.
3. Invalid CONFIG shift, reserved transaction ID, or nonzero END parameter.
4. Invalid PROCESS vector count (0 or greater than 32).
5. PROCESS before successful CONFIG.
6. Premature TLAST before the expected last payload word.
7. Missing TLAST at the expected last payload word.

For malformed headers, record the decoded offending `tx_id` if its field was received completely and unambiguously. Otherwise record `0xFFFFFFFF`. An undecodable or incomplete `tx_id` must never inherit a transaction ID from an earlier command. Test both cases.

If multiple errors could apply, use this priority: header framing; unknown command; invalid header parameters; missing configuration; payload framing. During payload reception, early TLAST takes precedence when observed; missing final TLAST is detected at the expected last word. Do not consume extra words attempting to find TLAST.

On every error, set `halted=1`, record the error code and offending `tx_id`, close any already-started output burst using TLAST, and immediately return without reading further input. Do not acknowledge or return results for the failing command; earlier completed responses remain valid. The host must reset the stream path before another activation. An invalid CONFIG must not partially modify configuration. Buffer valid PROCESS input completely before producing a response, so a malformed PROCESS cannot produce partial results.

## Post-implementation behavioral clarifications (v3)

These are binding requirements for subsequent runs, resolving the consequential choices recorded in the v2 `results.md` Assumptions register. Part 4 Run 1 selected these behaviors; the retained verification and Run 5 synthesis/co-simulation support preserving them. The assumption numbers below refer to that historical register. This revision changes the specification, not the historical run versions or evidence, and does not claim a new implementation or verification run.

### V3.1 Transport and encodings (Assumptions 2–9, 11–12, 18)

Use CONFIG=1, PROCESS=2, END=3, with no other legal opcodes. Both AXI4-Streams have 64-bit TDATA, 8-bit TKEEP/TSTRB, TLAST, TVALID/TREADY, and no TID/TDEST/TUSER. Legal host transfers and all output transfers use TKEEP=TSTRB=0xFF. Payload byte enables are ignored by the receiver; they do not create another error category. All payload bit patterns are legal signed data; payload validation checks TLAST.

Every command, including END, has three header words: opcode, transaction ID, then parameter, each unsigned 32-bit in bits [31:0], with bits [63:32] zero. Header TLAST is respectively 0, 0, 1. Check upper padding and both byte enables on every header word; nonzero padding or a byte enable other than 0xFF is malformed-header error 1. Parameters use the full unsigned 32 bits without truncation: CONFIG shift must be 0–15 and PROCESS nvec must be 1–32. Two's-complement encodings of negative parameters consequently fail those ranges.

Pack signed values in two's complement, earliest element in the least significant lane. CONFIG contains ten payload words: eight row-major weight words (eight INT8 weights each), then two bias words (four INT16 biases each, in output-row order). PROCESS contains nvec payload words, each holding one eight-element INT8 vector. There are no payload padding words or length-prefix elements. Each successful CONFIG or PROCESS response header is one word with its command ID in bits [31:0], zero above, and TLAST=1. CONFIG has no result payload. PROCESS follows its separately terminated response header with nvec result words in vector order, eight INT8 results per word. Each input or result payload has TLAST only on its final word, including a one-word payload.

### V3.2 END, transaction IDs, and error precedence (Assumptions 10, 13–17)

END must carry parameter zero. A nonzero END parameter causes code 3, immediate halt with the offending transaction ID in status, and no response. Legal IDs may be reused across successive commands, including ID zero; only 0xFFFFFFFF is reserved. Uniqueness is not required. Each successful CONFIG or PROCESS response echoes its own command's ID. Status tx_id is an offending-ID field: it stays zero throughout a successful activation, including successful END regardless of END's ID. Successful END emits no response and returns status (halted,error,tx_id)=(0,0,0).

Error codes are exactly the numbers 1–7 listed above. Stop at the first malformed header word before checking opcode, parameters, or configuration; do not read subsequent words to recover an ID. Decode the ID afresh for each command. It is available only after header word 1 has arrived with zero upper padding and TKEEP=TSTRB=0xFF. Incorrect TLAST on that otherwise valid word still leaves its ID decodable. Errors before word 1, or in its padding/byte enables, report 0xFFFFFFFF; a malformed later word retains the decoded ID.

For a correctly framed header, check unknown opcode first (code 2), then reserved ID (code 3), then opcode-specific parameter validity (code 3 for CONFIG/END, code 4 for PROCESS), then missing configuration (code 5). In particular, PROCESS with both reserved ID 0xFFFFFFFF and invalid nvec reports code 3, not 4. This fixes precedence within the original invalid-header-parameter priority class. All these checks precede payload reads; payload framing codes 6/7 follow the original rules.

### V3.3 Sequencing, blocking, and burst completion (Assumptions 19–20, 23)

Process commands strictly in arrival order. Complete the current command's validation and any successful response, including its final payload write with TLAST, before accepting the next command header. Do not overlap reception of a new command with result generation. A later CONFIG cannot overlap an earlier PROCESS or change its results. Validate the complete CONFIG or PROCESS payload before starting any response for that command.

Thus every earlier successful burst is already TLAST-closed when an error is detected, and the failing command has not started a response. This satisfies the output-closure requirement without an extra synthetic closing word or error response. Return immediately on error without draining input or searching for TLAST. The host must reset/discard the stream path and use fresh streams for recovery.

Input reads block until data arrive; absent header or payload words cause waiting, not a timeout error. Code 7 applies only when the expected final payload word is actually received without TLAST. Output writes honor AXI backpressure and may block; a stall alone is not a protocol error. The performance target remains measured without externally inserted stalls.

### V3.4 Configuration and activation state (Assumptions 21–22, 29)

Stage and validate the entire CONFIG payload before installing weights, biases, and shift. Accept no command during installation; mark configuration valid and acknowledge only after installation completes. Atomic replacement means externally indivisible replacement relative to sequential PROCESS commands, not simultaneous switching of all physical storage bits. An invalid CONFIG does not install partial data.

At each activation entry initialize shift to zero, configuration validity to false, and all three status values to zero. No usable configuration or prior error survives activation boundaries. Physical weight, bias, and payload storage need not be erased: validity must prevent its use before a successful CONFIG, and a PROCESS payload must be completely received before use. Recovery uses a fresh activation and fresh streams as already required; it does not resume an aborted command.

### V3.5 Accepted compute architecture and arithmetic (Assumptions 24–25)

Independently compute the eight dot products using completely partitioned weights and biases and fully unrolled row and column dot-product arithmetic, implementing exactly 64 signed products per vector. Target compute-loop II=1 and input-receive-loop II=1. Use signed INT8 operands, signed INT16 products/biases, and exact signed INT32 accumulation. Quantize using nonnegative INT32 magnitude, adding 2^(shift-1) before shifting when shift>0, restoring sign, then saturating before narrowing to INT8; shift zero bypasses rounding. Mathematically equivalent HLS internal operator narrowing is permitted.

Leave DSP/fabric binding and buffer-memory implementation to HLS. Run 5 reported compute II=1, depth 11 and estimated period 6.913 ns; retained RTL timing extraction from that run measured 86 inclusive cycles for a 32-vector batch. These support the accepted architecture, not a requirement to reproduce identical resources or latency. The external target remains at most 32 cycles/vector for nvec=32. Report achieved II and any missed target honestly as already required. There is no mandatory synthesis resource limit or top-level II=1 requirement; the sequential command loop may have unknown activation-level latency/II in synthesis.

### V3.6 Control interface and measurement basis (Assumptions 26–28, 33–34)

Retain target xc7z020clg484-1 and an 8 ns requested clock. Use the tool's default clock uncertainty (2.16 ns in the retained run); judge the strict estimated-period <10 ns target independently of uncertainty-margin warnings. Convert measured cycles to time using the actual simulation clock, not estimated Fmax. Measure accepted transfers at the external DUT stream interface; report inclusive batch cycles from first PROCESS payload transfer through last result payload transfer, divide by nvec for cycles/vector, and distinguish inclusive first-result latency from edge-to-edge periods and activation-level tool latency.

Use generated 32-bit AXI-Lite ap_ctrl_hs control/status, with no coefficient or command-parameter registers. The control register is at 0x00 and standard GIE/IER/ISR at 0x04/0x08/0x0C. Read-only halted, error, tx_id values are at 0x10, 0x20, 0x30; their generated ap_vld flags are at 0x14, 0x24, 0x34 (bit 0, clear on read). The generated control map defines standard control/interrupt semantics. The host waits for activation completion before interpreting final status; interrupts and auto-restart need not be enabled.

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
| 2 | Explicit malformed-header transaction-ID sentinel, exhaustive ambiguity register, and staged verification checkpoint | Address pre-implementation Part 3 grader feedback, before the first Codex implementation run, while retaining the take-home requirement to complete co-simulation and synthesis. This revision was not caused by an implementation run. |
| 3 | Make post-implementation behavioral clarifications binding: fix protocol/packing, END validation and success status, ID reuse and error precedence, sequential validation/response completion, blocking/recovery, initialization/atomic configuration, accepted unrolled architecture/arithmetic, and control/measurement basis | Actual Part 4 grader feedback was 27/30, with 3 points lost in the Iteration criterion. Initial Part 4 implementation Run 1 in results.md selected the behaviors now recorded in Assumptions 10, 13, 16, 23, 24 and additional consequential Assumptions 2–9, 11–12, 14–15, 17–22, 25–29, 33–34. Run 5 synthesis/co-simulation supports the chosen architecture; later extraction of its retained waveform supports external throughput. The implementation and ambiguity register exposed decisions that v2 had left discretionary. We now adopt those decisions as normative requirements for subsequent runs to preserve verified behavior and remove consequential ambiguity. Historical Runs 1–10 remain v2 evidence; no v3 tool run is claimed. |
