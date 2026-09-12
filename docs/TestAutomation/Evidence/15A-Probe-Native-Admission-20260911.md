# 15A native admission protocol — 2026-09-11

Task 15A remains earliest ready; none bypassed. Actual settings
`gpt-6-astra/high`, Standard. All-task VM clearance persists. No Task 20 R1
recovery portion or new installed attempt; activation attempts remain two.

## Implemented boundary

The [owning admission contract](../../SystemDesign/Applications.md#pre-exec-admission-for-a-causal-witness)
now has separate native gate/witness payloads and a fixed protocol header:
`tools/execution_probe_gate.c`, `tools/execution_probe_witness.c`, and
`tools/execution_probe_protocol.h`. These are uninstalled implementation inputs;
the broker adapter and existing boot canary are unchanged. The native component
tests reuse `tests.support.terminal.capture` and its cleanup-safety regressions.
No new process launcher, permission, setup entry point or general dispatcher.

The gate waits for exactly one matching admission and write EOF before ordinary
pathname exec. It does not reconnect. The witness alone emits the execution
frame; real exec failure emits a separate failure frame. Fixed private paths,
peer-UID comparison, descriptor hygiene, finite nonblocking deadlines, bounded
framing and no raw diagnostic payload are implemented. The owning contract
records exact wire/path/descriptor behavior for the broker adapter to reuse.

## Executed qualification

`tests/component/test_execution_probe_native.py` passed **35 tests**. Compiler:
Ubuntu GCC 15.2.0 (`15.2.0-16ubuntu1`), C11, warnings-as-errors, optimization,
fortification and stack protection. The fixture compiles both real payloads
in its owned temporary directory and relocates only the compile-time runtime
root. It does not fake exec or socket I/O and does not contact host systemd.

| Planned case | Actual native observation / executable test |
| --- | --- |
| ADMIT-01 | `test_waiting_gate_execs_separate_witness_on_same_connection`: kernel peer credentials and the waiting gate executable are observed before admission; execution frame and exit 23 follow on the accepted connection. `test_fragmented_admission_is_accepted_only_after_write_eof` also proves no exec after a partial frame or a full frame without EOF. |
| ADMIT-04 (partial) | `test_denied_exec_emits_failure_then_new_gate_still_waits`: remove execute permission after hello, observe real exec failure frame/exit 70, then a later gate waits and fails without a new authorization. This is not a systemd restart or proof that the broker refuses a second candidate. |
| ADMIT-06/09 (partial) | `test_admission_deadline_never_execs_or_replays`: silence, partial admission and missing write EOF all expire with no execution frame. Broker admission-consumption state and lost creation replies are outside this test. |
| ADMIT-08 (native input) | `test_bad_admission_never_reaches_witness`: EOF, truncation, extra/duplicate/oversized data, wrong stage/invocation/version/reserved bytes. `test_ancillary_descriptors_are_refused`: SCM_RIGHTS and truncated ancillary buffers; no pipe writer survives. Broker hello/result parsing remains open. |
| ADMIT-12 (partial) | `test_gate_does_not_reconnect_after_selected_connection_loss`: close selected peer, observe failure and no new queued connection. Broker restart recovery remains open. |
| Additional preflight | Invalid invocation/token, arbitrary path, writable/non-executable/symlink witness, shared attempt directory and witness invocation without inherited socket all refuse. Diagnostics disclose only fixed categories. |

ADMIT-02/03/05/07/10/11 still require the broker/manager adapter. No complete
ADMIT matrix, installed policy result, generation receipt or Task 15A acceptance
is claimed. In particular, root-owned digest binding/immutability, one-candidate
selection, consumed-before-send state, stable manager/unit/MainPID/invocation
validation and owned socket/path removal are the next missing capabilities.
The native client never unlinks the broker's path. Packaging and removal must
ship together before installed qualification; activation is `process-restart`.
No saved-data format changed. Permanent transport-loss settlement remains open.

## Reproduction and retained results

- `tools/run-unit-tests tests/unit/test_terminal_cleanup_safety.py -q`:
  **5 passed**, exit 0, isolated before real child execution.
- `tools/run-tests component tests/component/test_execution_probe_native.py -q`:
  initial **26 passed**, exit 0; after adding path and fragmented-admission cases
  and removing an unused local variable, final **35 passed**, exit 0. Each
  component launch first passed its isolated **794 tests / 3 subtests** safety
  closure. Both launches used normal helper escalation for local sockets.
- No test failures, execution-policy or Polkit denials. One exploratory file
  discovery included an absent `native` directory; actual sources live in
  `tools`. Overbroad source output was narrowed to the owning helper/files.
- Changed-document link and scoped whitespace checks passed. No full
  `make check`, package build, VM/systemd attempt or launch matrix was run.

Final verified source SHA-256 identities:

| File | SHA-256 |
| --- | --- |
| `tools/execution_probe_gate.c` | `aeacd65aed8307c746b03d3e18316e181792144aa755a533d046b4435612e14d` |
| `tools/execution_probe_witness.c` | `a1013d99bedf649d595d42545f6c408e733da44cde86017d13b0613ec81d83d3` |
| `tools/execution_probe_protocol.h` | `74efcdf381958a613bf39bac671548e73f7d55088dc935177533365adde0a728` |
| `tests/component/test_execution_probe_native.py` | `98060638fff86acbe75627f0123b84e7134a98d7fe4bdf04b26ff2945622e0e7` |

## Cleanup and next result

Both launcher commands exited and results were collected. `capture` joined
every directly spawned compiler/gate/witness child; executor contexts completed,
socket/pipe contexts closed, attempt directories and the fixture's temporary
root were removed. No host units, VM, lease, screenshots or background process
were started; no logs were modified or deleted. Existing edits were preserved.

Next implement the bounded broker channel with one selected peer and a consumed
admission latch, identity-bound pending state and identity-safe path cleanup.
Integrate against these native tests before the retained systemd lifecycle and
guarded guest qualification. Keep current `identity-unproven` refusal.
Next settings `gpt-6-astra/high`, Standard: protocol execution is proven locally,
but broker peer authentication, interrupted sends and path ownership remain
security/concurrency work. Reassess after those executable boundaries pass.
