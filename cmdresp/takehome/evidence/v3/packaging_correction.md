# Documentation and packaging correction (no hardware run)

The v2 reason in prompt.md now identifies the earlier Part 3 prompt-grader evaluation of v1 and maps its three findings to the three v2 decisions. The findings are supplied by the submission owner in the correction request. No original Part 3 evaluation transcript, URL, evaluation identifier, score or quotation was found in the repository or available local session/history records; none is fabricated here.

Authentic corroboration: commit `2478c24bca186de31db352355d06997c4d07a5fc` introduced the v2 specification alone, including its malformed-ID rule, exhaustive ambiguity register, staged verification and explicit Part 3 grader-feedback reason. Inspect with `git show 2478c24:cmdresp/takehome/prompt.md`. It precedes implementation commit `aea86ec`. The original report is retained at [results_before_v3.md](results_before_v3.md), with Run 1 using v2 for implementation/Python fixture checks and Run 5 providing synthesis/RTL evidence. Those are later validation, not the cause of v2. The accepted v3 row is unchanged; Run 11 remains documented in results.md.

## Hash and manifest scope

- `evidence/spec.sha256`: original v2 specification hash, unchanged.
- `spec_before_packaging.sha256`: original v3 specification hash used for Run 11, byte-for-byte copy of the prior current hash. Run 11's specification is also recoverable at commit `e380d18`.
- `spec.sha256`: current v3 document hash after provenance-only editing. Normative requirements are unchanged.
- `executed_sources.sha256`: original executed source/fixture hashes, unchanged.
- `baseline_manifest.json`: original pre-v3 tracked-file baseline, unchanged; includes generated files retained locally but now excluded from submission.
- `submission_manifest_before_packaging.sha256`: exact prior submission manifest, historical scope including files now untracked. It is not the current submission inventory.
- `submission_manifest.sha256`: final staged project inventory, excluding itself and the current audit log to avoid circular hashes. Historical audit logs/scripts remain unchanged and describe their original scope. The current check is `python3 audit_packaging.py`; it does not invoke tools or regenerate measurements.

## Packaging decisions

[removed_from_tracking.txt](removed_from_tracking.txt) lists all 82 index removals: 38 simulator-vector/support files and three generated Verilog-directory artifacts per project. All remain locally with original bytes and are ignored. Neither report cites these exact files as evidence. Historical manifests describe their old inventory and do not justify keeping generated trees in the current submission.

[preserved_native_artifacts.txt](preserved_native_artifacts.txt) lists all 50 retained native artifacts: both C-simulation reports, all synthesis reports/XML, co-simulation reports and supporting report files, zero-stall settings, AXI-Lite register-map RTL and both native WDBs. The WCFG and protoinst files are unnecessary for the scripted WDB extraction, which opens the WDB directly. Original comparison CSVs, waveform extraction CSVs, status checks, logs, fixtures and source are unchanged. No synthesis or simulation was rerun.

The correction targets the remaining one Iteration point and two Repository points; a new grade is not claimed. The principal provenance limitation is the unavailable original Part 3 evaluation transcript. Current owner-supplied findings and the authentic historical v2 commit are distinguished above.
