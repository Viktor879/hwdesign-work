## Interface

`prompt.md` version 2 is authoritative (unchanged; `evidence/spec.sha256`). This implements the requested take-home work despite the document's Part 3 title. Both streams use AXI4-Stream TDATA[63:0], TKEEP[7:0], TSTRB[7:0], TLAST, TVALID and TREADY, with no TUSER/TID/TDEST. Lane 0 occupies the least significant bits. Signed values use two's complement. All transfers use TKEEP=TSTRB=0xFF; the receiver checks these on headers and treats payload data as eight valid bytes. There is no payload padding. Unused upper header bits are zero and checked. No parameters use AXI-Lite.

Every command header is **three 64-bit words**: opcode in word 0 bits [31:0], transaction ID in word 1 bits [31:0], and parameter in word 2 bits [31:0]; bits [63:32] of each are zero. TLAST is 0,0,1 respectively. Early TLAST, missing final TLAST, nonzero upper bits, or partial header byte enables are malformed-header error 1. Stop at the first malformed word. A transaction ID is available only after a complete, correctly padded/enabled word 1 has arrived; otherwise use 0xFFFFFFFF. A framing error in word 1 with valid ID bytes still records that ID. Initialize the decoded ID afresh for every header.

| Opcode | Parameter | Input payload | Successful response |
| --- | --- | --- | --- |
| 1 CONFIG | unsigned shift, 0–15 | 10 words: words 0–7 each contain one row's eight INT8 weights; words 8–9 contain four INT16 biases each, in row order | One header word: low 32 bits echoed tx_id, upper 32 zero, TLAST=1 |
| 2 PROCESS | unsigned nvec, 1–32 | nvec words, each one eight-element INT8 input vector | Same single-word header, followed by nvec result words, each one eight-element INT8 output vector |
| 3 END | zero | None | None; successful activation return |

Input payloads and result payloads each form a separate burst: TLAST=0 except the final word, where TLAST=1. A one-word payload has TLAST=1. A PROCESS response header and payload are separately terminated bursts. Repeated legal IDs are permitted; legal IDs span 0 through 0xFFFFFFFE. All successful response headers echo the command ID; successful END leaves status tx_id=0 rather than recording the END ID.

AXI-Lite is 32-bit, using Vitis `ap_ctrl_hs`. The generated register map is authoritative: `qgemv_hls/solution1/syn/verilog/qgemv_control_s_axi.v`.

| Offset | Register | Access/meaning |
| --- | --- | --- |
| 0x00 | activation control | bit 0 start, bit 1 done (clear on read), bit 2 idle, bit 3 ready (clear on read), bit 7 auto-restart, bit 9 interrupt |
| 0x04 / 0x08 / 0x0C | standard GIE / IER / ISR | Generated interrupt control; interrupts and auto-restart need not be enabled |
| 0x10 / 0x14 | halted / halted_ap_vld | Read-only 32-bit value (0 or 1); valid flag bit 0, clear on read |
| 0x20 / 0x24 | error / error_ap_vld | Read-only 32-bit error code; valid flag bit 0, clear on read |
| 0x30 / 0x34 | tx_id / tx_id_ap_vld | Read-only 32-bit offending transaction ID; valid flag bit 0, clear on read |

At activation entry the kernel writes zero to all three status values and invalidates configuration. The host waits for done before using final status. Values may be published during activation through the generated valid strobes. Physical configuration storage need not be zeroed because validity gates all access.

| Code | Meaning | Detection priority |
| --- | --- | --- |
| 0 | Success | No error |
| 1 | Malformed/header TLAST framing | First |
| 2 | Unknown opcode | Second |
| 3 | CONFIG shift outside 0–15, reserved ID, or nonzero END parameter | Third; reserved ID precedes PROCESS size |
| 4 | PROCESS nvec zero or above 32 | Third, after reserved ID |
| 5 | PROCESS before CONFIG | Fourth |
| 6 | Payload early TLAST | Fifth; return immediately when observed |
| 7 | Payload missing final TLAST | Fifth; detected exactly at expected final word |

Errors return immediately with halted=1, exact error code, and offending ID. No drain/search for another TLAST occurs. Invalid parameters are checked before reading payload. No response is emitted until the entire corresponding payload passes framing checks. Thus no failing command starts an output burst, and every previously emitted burst is already TLAST-closed; no synthetic error response or extra closing word is needed. CONFIG storage is updated only after full validation. PROCESS input is buffered before its header or results are emitted. The host must reset/discard the stream path after an error, then start with fresh streams; the testbench does this with fresh stream objects for each activation.

## Design

`qgemv.cpp` implements a persistent command loop inside one host activation. Weights are a completely partitioned 8×8 INT8 array; biases are eight completely partitioned INT16 entries. A 32×64-bit payload buffer holds either a complete CONFIG payload or up to 32 input vectors. CONFIG validates into this staging buffer, then installs weights, biases, and shift before acknowledging. No concurrent command executes during installation, giving atomic externally visible replacement. Configuration validity and status are explicitly initialized on each invocation.

PROCESS reads and validates the entire batch, writes the response header, then pipelines the vector loop at II=1. Both dot-product loops are completely unrolled: **exactly 64 signed INT8 products per vector**, eight independent sums with signed INT16 biases. Products have signed 16-bit storage; every accumulation is signed 32-bit. Legal sums are within [-162816,163839], so there is no mathematical overflow. HLS may use narrower equivalent internal wires and multiply-add operators; the arithmetic remains exact. The compute synthesis report contains exactly 64 multiplication-containing instances: 24 fabric multipliers and 40 DSP multiply-add instances (`evidence/synthesis_summary.json`, checked by `analyze.py`). Thus 40 DSPs does not imply only 40 products.

For quantization, hardware forms the nonnegative INT32 magnitude, adds 2^(shift-1) when shift>0, shifts right, restores the sign, and clamps to [-128,127] before INT8 conversion. Shift zero bypasses rounding. The magnitude and rounding offset fit INT32. No floating-point arithmetic is used in the hardware datapath. The Python model instead uses quotient/remainder rounding; the NumPy reference uses signed floor division and asymmetric remainder comparison, reducing common-mode rounding mistakes.

Synthesis reports compute II=1 and pipeline depth 11 (`qgemv_hls/solution1/syn/report/qgemv_Pipeline_compute_csynth.xml`). The top command loop is not pipelined, and its unbounded activation-level latency/II are reported as unknown, not II=1. Whole-batch validation adds input buffering and control overhead; it still achieves 86 inclusive cycles for 32 vectors. No optimization retry was needed. Results are estimates for the example's xc7z020clg484-1 target, not post-route measurements.

## Targets

All numerical entries below come from retained actual Vitis 2026.1 runs. The RTL clock is 8 ns. Throughput is measured at the **external DUT AXI stream interface**, including registered interfaces, from the first accepted PROCESS payload word to the last accepted result payload word, inclusive. One payload word equals one eight-element vector.

| Quantity | Required target | Observed | Assessment | Evidence |
| --- | --- | --- | --- | --- |
| Estimated clock period | Strictly <10 ns | 6.913 ns | PASS | `qgemv_hls/solution1/syn/report/qgemv_csynth.rpt`, `evidence/synthesis_summary.json` |
| Average cycles/vector, nvec=32 | ≤32 | 86/32 = **2.6875** | PASS in all four measured batches | `evidence/rtl_process_timing.csv`, `evidence/rtl_cycles.csv` |
| Batch interval, nvec=32 | ≤1024 cycles | 86 cycles = 688 ns at 8 ns | PASS | `evidence/rtl_process_timing.csv` |
| Batch throughput at simulated clock | Derived from cycle target | 46.512 million vectors/s (372.093 million output elements/s) | PASS relative to cycle target | `evidence/rtl_process_timing.csv`; eight elements/vector |
| First output latency for nvec=32 | no target | 55 inclusive cycles (54 edge-to-edge periods) | Measured, no target | `evidence/rtl_process_timing.csv` |
| Activation latency, all 49 cases | no target | min 19 / average 78 / max 252 cycles | Measured, no target | `qgemv_hls/solution1/sim/report/qgemv_cosim.rpt`; per-case `sim/report/verilog/result.transaction.rpt` |
| Activation interval | no target | min 33 / average 92 / max 266 cycles | Measured, no target | `qgemv_hls/solution1/sim/report/qgemv_cosim.rpt` |
| Compute loop II / depth | no target | 1 / 11 cycles | Measured, no target | `qgemv_hls/solution1/syn/report/qgemv_Pipeline_compute_csynth.xml` |
| Top latency / II from synthesis | no target | Unknown (command loop exits on END/error) | Tool reports unknown, no target | `qgemv_hls/solution1/syn/report/qgemv_csynth.rpt` |
| LUT | no target | 7365 | Measured, no target | `evidence/synthesis_summary.json`, top synthesis report |
| FF | no target | 5199 | Measured, no target | same |
| DSP | no target | 40 | Measured, no target | same |
| BRAM_18K | no target | 4 | Measured, no target | same |

The synthesis clock request is 8 ns with tool-selected uncertainty 2.16 ns. Estimated period 6.913 ns can exceed the uncertainty-adjusted budget without violating the prompt's <10 ns estimated-clock target. No resource limits were invented. Co-simulation does not establish physical timing closure. The stimulus sets both stream delays to zero (`qgemv_hls/solution1/sim/qgemv_cosim_random_stall.json`); `analyze.py` additionally verifies no input-availability gaps while payload input is ready and no output backpressure during each measured PROCESS. Transfer timestamps come from the saved WDB via `export_wave.tcl`, sampled 1 ps before the rising clock edge; `evidence/wave_export_console.log` confirms clock polarity.

## Verification

First, `golden.py` passed all six required hand-calculation categories, including +3/2→+2, -3/2→-2, positive/negative non-ties, sub-half negative values→0, shift-15 boundaries, identity, zero, biased dot product 8, and both saturation directions. It then passed **3200 independently computed NumPy INT64 comparisons**, 200 vectors at each shift 0–15, with fixed seed 20261028. Evidence: `evidence/python.log`, `evidence/python_checks.json`. NumPy uses matrix multiplication and signed floor/remainder quantization rather than the Python model's scalar dot products and magnitude quotient/remainder rounding. Python is untimed.

Next, actual HLS C simulation passed all 49 activations (`evidence/csim_unsandboxed.log`, `evidence/csim_comparison.csv`). Only after that checkpoint did synthesis and one RTL co-simulation run execute. RTL post-check passed all 49 activations (`evidence/synth_cosim.log`, `evidence/rtl_comparison.csv`, `qgemv_hls/solution1/sim/report/qgemv_cosim.rpt`). The C pre-check printed during co-simulation is not treated as evidence of RTL success; the post-check and final co-simulation PASS are both retained.

For every scenario below, expected output words are in `data/cases.json` / `data/cases.txt`. `tb.cpp` checks full 64-bit output data, echoed IDs, order, exact count, TLAST, TKEEP, TSTRB, all three status fields, and absence of extra outputs. `analyze.py` independently checks every accepted RTL input/output transfer against those fixtures, including exact counts, with no transfers left over. Invalid-header/parameter cases provide no associated payload; a payload read would fail C simulation or hang RTL instead of passing. Early/missing TLAST cases end exactly at the offending word; any attempted drain similarly cannot pass. This tests immediate abort without relying on a speculative model of stream timing. Required recovery cases immediately follow each error in the single C++ testbench sequence.

In the table, status is `(halted,error,tx_id)` in decimal; success always expects `(0,0,0)`. “Equal” means Python expected output words equal C simulation and RTL output words bit for bit, plus exact expected status. “None failing” means only earlier successful responses were retained, with no header/results for the offending command. `C` = `evidence/csim_comparison.csv`; `R` = `evidence/rtl_comparison.csv`; `T` = `evidence/rtl_protocol_checks.csv`; locate each by scenario name.

| Scenario | Expected status / response behavior | Observed Python/C/RTL | Recovery | Assessment / evidence |
| --- | --- | --- | --- | --- |
| `identity_n1` | (0,0,0); 3 output words | Equal; exact status/count/framing | N/A | PASS; C, R, T |
| `dot_bias` | (0,0,0); 3 output words | Equal; exact status/count/framing | N/A | PASS; C, R, T |
| `zero_n32` | (0,0,0); 34 output words | Equal; exact status/count/framing | N/A | PASS; C, R, T |
| `saturation` | (0,0,0); 4 output words | Equal; exact status/count/framing | N/A | PASS; C, R, T |
| `ties_shift1` | (0,0,0); 3 output words | Equal; exact status/count/framing | N/A | PASS; C, R, T |
| `nonties_shift2` | (0,0,0); 3 output words | Equal; exact status/count/framing | N/A | PASS; C, R, T |
| `shift15` | (0,0,0); 3 output words | Equal; exact status/count/framing | N/A | PASS; C, R, T |
| `mixed_n32_shift0` | (0,0,0); 34 output words | Equal; exact status/count/framing | N/A | PASS; C, R, T |
| `mixed_n32_shift15` | (0,0,0); 34 output words | Equal; exact status/count/framing | N/A | PASS; C, R, T |
| `persistence_replacement` | (0,0,0); 40 output words | Equal; exact status/count/framing | N/A | PASS; C, R, T |
| `end_only` | (0,0,0); 0 output words | Equal; exact status/count/framing | N/A | PASS; C, R, T |
| `header_undecodable` | (1,1,4294967295); None failing; 3 earlier words | Equal; exact status/count/framing | PASS: next `recovery_header_undecodable` | PASS; C, R, T |
| `recovery_header_undecodable` | (0,0,0); 3 output words | Equal; exact status/count/framing | Fresh CONFIG→PROCESS→END PASS | PASS; C, R, T |
| `header_decodable` | (1,1,123); None failing; 3 earlier words | Equal; exact status/count/framing | PASS: next `recovery_header_decodable` | PASS; C, R, T |
| `recovery_header_decodable` | (0,0,0); 3 output words | Equal; exact status/count/framing | Fresh CONFIG→PROCESS→END PASS | PASS; C, R, T |
| `header_missing_last` | (1,1,124); None failing; 0 earlier words | Equal; exact status/count/framing | PASS: next `recovery_header_missing_last` | PASS; C, R, T |
| `recovery_header_missing_last` | (0,0,0); 3 output words | Equal; exact status/count/framing | Fresh CONFIG→PROCESS→END PASS | PASS; C, R, T |
| `header_padding` | (1,1,125); None failing; 0 earlier words | Equal; exact status/count/framing | PASS: next `recovery_header_padding` | PASS; C, R, T |
| `recovery_header_padding` | (0,0,0); 3 output words | Equal; exact status/count/framing | Fresh CONFIG→PROCESS→END PASS | PASS; C, R, T |
| `header_bad_tx_padding` | (1,1,4294967295); None failing; 3 earlier words | Equal; exact status/count/framing | PASS: next `recovery_header_bad_tx_padding` | PASS; C, R, T |
| `recovery_header_bad_tx_padding` | (0,0,0); 3 output words | Equal; exact status/count/framing | Fresh CONFIG→PROCESS→END PASS | PASS; C, R, T |
| `unknown` | (1,2,127); None failing; 0 earlier words | Equal; exact status/count/framing | PASS: next `recovery_unknown` | PASS; C, R, T |
| `recovery_unknown` | (0,0,0); 3 output words | Equal; exact status/count/framing | Fresh CONFIG→PROCESS→END PASS | PASS; C, R, T |
| `reserved` | (1,3,4294967295); None failing; 0 earlier words | Equal; exact status/count/framing | PASS: next `recovery_reserved` | PASS; C, R, T |
| `recovery_reserved` | (0,0,0); 3 output words | Equal; exact status/count/framing | Fresh CONFIG→PROCESS→END PASS | PASS; C, R, T |
| `config_shift16` | (1,3,128); None failing; 3 earlier words | Equal; exact status/count/framing | PASS: next `recovery_config_shift16` | PASS; C, R, T |
| `recovery_config_shift16` | (0,0,0); 3 output words | Equal; exact status/count/framing | Fresh CONFIG→PROCESS→END PASS | PASS; C, R, T |
| `config_shift_unsignedmax` | (1,3,129); None failing; 0 earlier words | Equal; exact status/count/framing | PASS: next `recovery_config_shift_unsignedmax` | PASS; C, R, T |
| `recovery_config_shift_unsignedmax` | (0,0,0); 3 output words | Equal; exact status/count/framing | Fresh CONFIG→PROCESS→END PASS | PASS; C, R, T |
| `process_zero` | (1,4,130); None failing; 0 earlier words | Equal; exact status/count/framing | PASS: next `recovery_process_zero` | PASS; C, R, T |
| `recovery_process_zero` | (0,0,0); 3 output words | Equal; exact status/count/framing | Fresh CONFIG→PROCESS→END PASS | PASS; C, R, T |
| `process_33` | (1,4,131); None failing; 0 earlier words | Equal; exact status/count/framing | PASS: next `recovery_process_33` | PASS; C, R, T |
| `recovery_process_33` | (0,0,0); 3 output words | Equal; exact status/count/framing | Fresh CONFIG→PROCESS→END PASS | PASS; C, R, T |
| `process_unsignedmax` | (1,4,132); None failing; 0 earlier words | Equal; exact status/count/framing | PASS: next `recovery_process_unsignedmax` | PASS; C, R, T |
| `recovery_process_unsignedmax` | (0,0,0); 3 output words | Equal; exact status/count/framing | Fresh CONFIG→PROCESS→END PASS | PASS; C, R, T |
| `no_config` | (1,5,133); None failing; 0 earlier words | Equal; exact status/count/framing | PASS: next `recovery_no_config` | PASS; C, R, T |
| `recovery_no_config` | (0,0,0); 3 output words | Equal; exact status/count/framing | Fresh CONFIG→PROCESS→END PASS | PASS; C, R, T |
| `config_early` | (1,6,134); None failing; 3 earlier words | Equal; exact status/count/framing | PASS: next `recovery_config_early` | PASS; C, R, T |
| `recovery_config_early` | (0,0,0); 3 output words | Equal; exact status/count/framing | Fresh CONFIG→PROCESS→END PASS | PASS; C, R, T |
| `config_missing` | (1,7,135); None failing; 3 earlier words | Equal; exact status/count/framing | PASS: next `recovery_config_missing` | PASS; C, R, T |
| `recovery_config_missing` | (0,0,0); 3 output words | Equal; exact status/count/framing | Fresh CONFIG→PROCESS→END PASS | PASS; C, R, T |
| `process_early` | (1,6,136); None failing; 3 earlier words | Equal; exact status/count/framing | PASS: next `recovery_process_early` | PASS; C, R, T |
| `recovery_process_early` | (0,0,0); 3 output words | Equal; exact status/count/framing | Fresh CONFIG→PROCESS→END PASS | PASS; C, R, T |
| `process_missing` | (1,7,137); None failing; 3 earlier words | Equal; exact status/count/framing | PASS: next `recovery_process_missing` | PASS; C, R, T |
| `recovery_process_missing` | (0,0,0); 3 output words | Equal; exact status/count/framing | Fresh CONFIG→PROCESS→END PASS | PASS; C, R, T |
| `end_param` | (1,3,138); None failing; 0 earlier words | Equal; exact status/count/framing | PASS: next `recovery_end_param` | PASS; C, R, T |
| `recovery_end_param` | (0,0,0); 3 output words | Equal; exact status/count/framing | Fresh CONFIG→PROCESS→END PASS | PASS; C, R, T |
| `reserved_end` | (1,3,4294967295); None failing; 0 earlier words | Equal; exact status/count/framing | PASS: next `recovery_reserved_end` | PASS; C, R, T |
| `recovery_reserved_end` | (0,0,0); 3 output words | Equal; exact status/count/framing | Fresh CONFIG→PROCESS→END PASS | PASS; C, R, T |

| Requirement group | Assessment | Evidence and scope |
| --- | --- | --- |
| Eight inputs/outputs, 64 signed products, INT16 bias, exact INT32 accumulation | PASS | `qgemv.cpp` row/column loops; hand/NumPy checks and all C/R comparisons; mixed signs and extrema exercised |
| Rounding, saturation, zero, shifts 0 and 15 | PASS | `ties_shift1`, `nonties_shift2`, `shift15`, `saturation`, `zero_n32`; Python checks cover all 16 shifts |
| Sizes 1 and 32; multiple PROCESS and replacement | PASS | `identity_n1`, `mixed_n32_shift0`, `mixed_n32_shift15`, `persistence_replacement` in C/R/T |
| In-band parameters/data; separate command/response bursts; transaction IDs 0 and 0xFFFFFFFE | PASS | `persistence_replacement` C/R/T; synthesized interface report; only control/status on AXI-Lite |
| Seven distinct errors and specified priority | PASS | Error cases above; e.g. malformed PROCESS before CONFIG→1, unknown with invalid parameter→2, reserved PROCESS with zero nvec→3, zero nvec before CONFIG→4 |
| Malformed IDs never inherit earlier IDs | PASS | `header_undecodable`, `header_bad_tx_padding` follow successful IDs 99/98 yet return sentinel; `header_decodable` records 123; C/R/T |
| Parameter validation before payload, immediate abort, no drain | PASS | Header-only invalid cases; payload error cases stop on exact offending word; all C/R/T comparisons |
| No failing-command output; earlier responses remain terminated | PASS | Configured error cases retain ACK 99 and PROCESS 98 results only; full word/TLAST C/R/T checks |
| Atomic CONFIG and full PROCESS validation | PASS | `persistence_replacement`, `config_early`, `config_missing`, `process_early`, `process_missing`; staged commit in `qgemv.cpp`; C/R/T |
| No stale status/configuration across activations | PASS | Every error followed immediately by fresh valid recovery; `no_config` proves configuration does not survive earlier successful activations; C/R/T |
| Successful END status and no response | PASS | All valid cases and `end_only`; C/R/T |
| Staged tool execution and actual tool version | PASS | `evidence/python.log` precedes `evidence/csim_unsandboxed.log`, then `evidence/synth_cosim.log`, headers identify 2026.1 |
| Clock and measured throughput targets | PASS | Targets table and cited synthesis/RTL evidence |
| Sources, independent references, reproducible commands and retained evidence | PASS | `README.md`, `golden.py`, `tb.cpp`, `run.tcl`, `export_wave.tcl`, `analyze.py`, `evidence/`, full `qgemv_hls/solution1/` |

Coverage is finite; agreement is not a proof over all legal operand combinations. Atomic replacement on a failing CONFIG cannot be observed by a later PROCESS in the same activation because the protocol requires immediate halt. The test checks the externally observable behavior, while staging-before-commit is established by source/control flow. No fault injection or external-stall stress was requested; the required no-stall RTL measurement is covered.

## Assumptions

This numbered register records concrete choices where the specification leaves discretion or admits multiple readings. Each entry states the affected requirement, decision, exact resolution, rationale, and impact. Fixed requirements such as the matrix dimensions and rounding rule were implemented directly, not treated as assumptions.

1. **Assignment identity (title versus user request):** The prompt calls itself Part 3 while the user requests Part 4. Implement specification version 2, including synthesis and RTL co-simulation; this resolves naming without changing the authoritative file. Impact: naming/scope only.
2. **Command codes (“agent chooses command codes”):** Choose CONFIG=1, PROCESS=2, END=3 and no other legal opcodes; simple consecutive codes. Impact: protocol/errors.
3. **Transport width (“agent chooses transport widths”):** Use 64-bit AXI streams in both directions, matching one complete vector per word; reduces transfer overhead without changing numerical output. Impact: protocol/hardware size/throughput.
4. **Header layout (“agent chooses header layouts”):** Choose three fixed words with separate full-width opcode, ID and parameter as documented in Interface; makes incomplete-ID behavior unambiguous. No magic/version/length fields are added. Impact: protocol/errors/throughput.
5. **Header padding (“deterministic documented values”):** Set all unused header bits to zero; treat nonzero header padding as category 1. This rejects malformed encodings rather than silently truncating fields. Impact: protocol/errors.
6. **Packing/byte order (“word packing”):** Earliest INT8 occupies bits [7:0], earliest INT16 bias bits [15:0]; use two's complement, row-major weights, biases by output row. Gives explicit lane ordering independent of host memory byte order. Impact: protocol/numerical interpretation.
7. **Payload length versus padding (“number of elements, not padding bytes”):** CONFIG has 64+8=72 typed elements occupying 80 bytes/10 words; PROCESS has 8*nvec elements occupying nvec words. No length-prefix element or padding payload word is sent. All vector sizes divide transport width. Impact: protocol/throughput.
8. **Stream sidebands (not fully specified):** Use standard ap_axiu with TKEEP/TSTRB always 0xFF and no TID/TDEST/TUSER. Header byte-enable violations are category 1; payload byte enables are ignored, with legal host traffic required to enable all bytes. No eighth error category is invented. Impact: protocol/errors/hardware size. Tests use full enables.
9. **Header length for END (header-only wording):** END uses the same full three-word header with parameter zero, no payload, and no response. Simplifies fixed header parsing. Impact: protocol/throughput.
10. **Nonzero END parameter (unspecified):** Reject as code 3, the invalid-header-parameter class, rather than accepting unused nonzero fields. Documented extension does not affect required well-formed END behavior. Impact: errors/protocol.
11. **Unsigned versus “integer nvec”:** Encode full unsigned 32-bit parameter. A negative host value encoded in two's complement becomes >32 and is code 4. CONFIG shift is also full unsigned 32-bit; no low-bit truncation. Impact: errors/protocol.
12. **Response layout (unspecified):** Return one 64-bit header word containing ID in low 32 bits and zeros above. Command context determines ACK versus PROCESS response, so no response opcode/count/status field is added. END and errors emit none. Impact: protocol/throughput.
13. **Transaction-ID uniqueness (unspecified):** Permit repeated IDs, including zero; reserve only 0xFFFFFFFF. Test the maximum legal ID 0xFFFFFFFE. Sequential processing makes uniqueness unnecessary. Impact: protocol/errors.
14. **Success status tx_id (“clear tx_id at start”, no END value specified):** Keep tx_id=0 throughout a successful activation and update it only on error. This treats it as offending-ID status, while success IDs travel in responses. Impact: status/protocol.
15. **Malformed header timing (“decoded completely and unambiguously”):** ID becomes usable only when word 1 was actually received, upper padding is zero, and all its byte enables are valid. Early TLAST on word 1 still leaves a fully decoded ID; errors before word 1 or within its padding/enables yield sentinel. Never continue reading just to discover an ID. Impact: errors/protocol.
16. **Simultaneous invalid parameters (“priority”):** Reserved ID is checked before opcode-specific parameter range; all are header-parameter priority. Thus reserved ID plus illegal PROCESS size yields 3. This resolves ordering within that priority class. Impact: errors.
17. **Malformed header with other errors:** Stop on the first malformed word, before opcode/parameter/configuration checks. Unknown opcode still requires a correctly framed header before reporting 2. This applies the explicit cross-category priority without speculative reads. Impact: errors/protocol.
18. **Payload validation beyond TLAST:** All weight/input byte patterns and all bias bit patterns are legal signed values, so there is no numerical payload rejection. Only required payload TLAST errors 6/7 are checked. Impact: errors/protocol.
19. **Missing words without TLAST (no timeout specified):** Use blocking AXI stream reads; starvation stalls until data arrive or the host resets. Error 7 means a received expected final word lacks TLAST, not a time-based timeout. Avoids inventing a timeout or timing model. Impact: errors/throughput.
20. **Output termination on error (“close any already-started output burst”):** Finish all successful bursts before reading the next command and validate complete input before starting a new response. Consequently no output burst can be open at an error; emit no extra synthetic TLAST word. Impact: protocol/errors.
21. **Atomic configuration (“atomically replaces”):** Atomic means externally indivisible relative to sequential PROCESS commands, not simultaneous switching of all physical bits. Stage the entire CONFIG, then load local registers without accepting commands, set shift/valid and acknowledge. Impact: hardware size/throughput; preserves required numerical behavior.
22. **State reset (“no state ... persists”):** Invalidate configuration and reset status/shift on every activation. Physical weight/bias/payload RAM bits need not be erased because no valid computation can use them before installation. Avoids unnecessary reset circuitry. Impact: hardware size; no numerical/error difference.
23. **Concurrency (unspecified):** Commands run strictly sequentially; no overlap of a later CONFIG with earlier PROCESS or of reception with result generation. Meets order and validation requirements without additional queues. Impact: hardware size/throughput/protocol.
24. **Architecture/unrolling (unspecified):** Fully partition W/bias, unroll both dot-product dimensions, request compute II=1 and input receive II=1, leave DSP/fabric binding and RAM implementation to HLS. Chosen to meet bounded throughput without unlimited optimization. Impact: hardware size/throughput.
25. **Arithmetic representation (“exact INT32”):** Use ap_int<8>, ap_int<16>, ap_int<32> at the operand/product/accumulator boundaries; HLS may narrow mathematically equivalent internal operators. Use magnitude rounding with INT32 offset and saturate before narrowing. Impact: numerical output/hardware size.
26. **Target device (unspecified):** Retain the local example's xc7z020clg484-1, with no fabricated utilization budget. Provides a concrete reproducible target. Impact: clock/hardware size/throughput.
27. **Requested clock (only estimated clock target specified):** Request 8 ns rather than 10 ns, leave uncertainty at the installed tool's 2.16 ns default. Judge the specification's strict estimated <10 ns requirement, not an invented uncertainty-adjusted target. Impact: clock/resources.
28. **Control ABI (“AXI-Lite ... control and error/status”):** Use generated `s_axilite`/`ap_ctrl_hs`, 32-bit unsigned outputs, generated ap_vld flags and standard interrupt/auto-restart registers. Document exact offsets in Interface; do not add coefficient registers. Impact: protocol/hardware size.
29. **Activation and stream reset in testbench:** One kernel call per activation, fresh C++ input/output streams, no stale input tail retained. RTL co-simulation runs all calls in one invocation, permitting internal register state to persist physically while kernel entry resets validity/status. This follows the explicitly requested co-simulation sequence. Impact: verification/protocol.
30. **Error stimulus strategy (unspecified file/test structure):** Supply words only through the expected offending word, with no valid continuation after a failure. Any extra blocking read fails or hangs; waveform accepted-transfer counts additionally verify the exact supplied boundary. This tests immediate abort and avoids dependence on residual-queue behavior in generated co-simulation adapters. Impact: verification only.
31. **Golden-model independence (method unspecified):** Use pure Python arbitrary-precision scalar sums and divmod, a separate NumPy INT64 matrix/floor reference, explicit hand results, and deterministic seed 20261028 with 200 random vectors per shift. Avoid floating-point reference rounding. Impact: verification only.
32. **Fixture/output files (“agent chooses ... output file formats”):** Retain readable JSON and decimal text fixtures, CSV comparisons/cycle exports, JSON summaries, and native tool logs/reports/WDB. IDs/status are decimal in CSV and hex where helpful in documentation. Impact: formatting/reproducibility only.
33. **Latency definition (not separately defined):** Report the specified inclusive first-payload-to-final-result batch interval, inclusive first-result latency, and separately the tool's activation-level min/average/max. Explicitly distinguish 55 inclusive cycles from 54 edge periods. Impact: measurement interpretation only.
34. **Throughput conversion (frequency basis unspecified):** Convert cycles to seconds at the actual 8 ns co-simulation clock, not at synthesis-estimated Fmax. Inspect external accepted transfers before the clock edge and verify zero external stalls. Impact: measurement interpretation only.
35. **Waveform export details (unspecified):** Preserve the native WDB and use Vivado read-only database queries, not a second RTL run. Sample 1 ps before each rising edge, at 4+8*k ns, for 5000 cycles covering the entire 4533-cycle reported execution; assert exact fixture transfer counts. Mask query-returned data to unsigned 64 bits because Vivado may render bit-63 values as signed despite unsigned radix. Impact: measurement/formatting only.
36. **Tool invocation/version compatibility:** Use installed Vitis 2026.1 `vitis-run --mode hls --tcl`, retaining the example's batch Tcl project/solution style despite deprecation warnings. Bypass Waveflow code generation where it loses header TLAST information or emits output before validation. This is necessary to honor the professor's protocol. Impact: build/protocol.
37. **Waveflow integration scope:** Read all four requested local example files directly; use MCP's canonical component glossary for interface vocabulary. Do not call unavailable example RAG. Do not reuse the example's SimPy timing/calibration DAG; no Python timing model is built. Impact: workflow only.
38. **Evidence retention versus publication:** Keep complete local sources, logs, reports, fixtures and waveform database inside the project. Do not push or publish automatically; no commit was made during implementation. Deliverable files must be included together when the user commits/submits the project. Impact: packaging only.
39. **Test scope where unspecified:** Exercise required sizes, boundaries, every error class and immediate recovery, plus header padding, unsigned-max parameters, END parameter rejection, repeated/boundary IDs, and no-command END. Do not claim exhaustive numerical/sideband/stall-state verification or board validation. Impact: verification only.
40. **Performance retry policy:** Assess the first functionally passing synthesis/co-simulation implementation. Both stated targets pass; no kernel restructuring or performance search was undertaken. Impact: workflow only.

## Open Items

No unresolved implementation failure or missing required tool measurement remains. Independent Python checks, actual C simulation, synthesis, RTL co-simulation, and stream-level timing extraction completed successfully with retained evidence. The initial sandboxed tool launch failed license access (`evidence/csim.log`); the unsandboxed retry succeeded (`evidence/csim_unsandboxed.log`). Waveform inspection also required unsandboxed license access. These environmental failures did not indicate a functional failure.

Tool limitations: top-level synthesis latency/II are unknown for the command-controlled loop; the measured RTL latency and compute-loop II are reported instead. Synthesis numbers are estimates, not post-route or board measurements. Vivado emits signed decimal values for some 64-bit waveform samples despite requesting unsigned radix; `analyze.py` normalizes the bit pattern before comparison. Native WDB plus CSV are retained. Finite numerical verification and the header-only sideband checks have the scope stated above.

Packaging action remaining for the user: include the evidence alongside sources in the submission/commit. Files have been retained locally and no Git commit or push was performed. Nothing in the implemented accelerator or required verification awaits that packaging action.

## Run History

| Run | Spec | Changes / commands actually executed | Outcome | Evidence |
| --- | --- | --- | --- | --- |
| 1 | v2 | Read entire `prompt.md` and local `poly.py`, `poly_build.py`, `poly_evaluate_impl.tpp`, `run.tcl`; inspect installed tools and MCP components; write first implementation and fixtures; `/home/cp4523/hwdesign/.venv/bin/python golden.py` | PASS hand checks and 3200 NumPy comparisons; generated 49 activation fixtures | `evidence/python.log`, `evidence/python_checks.json`, `data/cases.json` |
| 2 | v2 | `QGEMV_STAGE=csim vitis-run --mode hls --tcl run.tcl` inside sandbox | FAIL launch: license unavailable at set_part; C simulation did not run | `evidence/csim.log` |
| 3 | v2 | Requested unsandboxed retry; request canceled by accidental Esc | NOT RUN; no implementation restart/deletion | Subsequent user retry request; no successful-run evidence claimed |
| 4 — C-simulation checkpoint | v2 | Same C-simulation command outside sandbox, after user retry request; no kernel changes | PASS: 49 activations, zero C simulation errors | `evidence/csim_unsandboxed.log`, `evidence/csim_comparison.csv` |
| 5 — synthesis then single RTL co-simulation | v2 | `QGEMV_STAGE=rtl vitis-run --mode hls --tcl run.tcl` outside sandbox; unchanged kernel/testbench/fixtures | PASS synthesis, then one XSIM co-simulation run covering all 49 activations; PASS post-check | `evidence/synth_cosim.log`, `evidence/rtl_comparison.csv`, `qgemv_hls/solution1/syn/report/`, `qgemv_hls/solution1/sim/report/` |
| 6 | v2 | `vivado -mode batch -source inspect_wave.tcl` initially sandboxed | FAIL license access before waveform query; no simulation rerun | `evidence/wave_inspect_console.log` was replaced by successful retry; no retained sandbox-failure log, so no PASS claim for that attempt |
| 7 | v2 | Unsandboxed read-only waveform API inspection; three iterations to discover supported `get_value_database -time`; first explored unsupported `write_vcd`, second unsupported `get_value -time` | Inspection only; expected query errors retained; no kernel change or RTL rerun | `evidence/wave_inspect.log`, `evidence/wave_inspect2_console.log`, `evidence/wave_inspect3_console.log` |
| 8 | v2 | `vivado -mode batch -source export_wave.tcl -log evidence/wave_export.log -journal evidence/wave_export.jou` outside sandbox | PASS: extract 5000 cycles from completed WDB; confirm clock sample polarity | `evidence/wave_export_console.log`, `evidence/rtl_cycles.csv`, native `qgemv.wdb` |
| 9 | v2 | `python3 analyze.py`; initial analysis exposed signed decimal rendering in waveform queries; normalize data modulo 2^64 and rerun | Final PASS: all accepted input/output words, C/RTL status comparisons, no-stall timing; kernel unchanged. Initial assertion was interactive output only, not a retained failed measurement | `evidence/analysis.log`, `evidence/rtl_protocol_checks.csv`, `evidence/rtl_process_timing.csv`, `evidence/synthesis_summary.json` |
| 10 | v2 | Write `README.md`, seven-section `results.md`, record spec hash; inspect final evidence and report structure | Documentation/package validation recorded separately; no further tool-performance run | `evidence/final_audit.log`, `evidence/spec.sha256` |
