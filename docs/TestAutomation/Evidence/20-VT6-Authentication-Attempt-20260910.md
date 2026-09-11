# Task 20 — integrated VT6 authentication, first guarded attempt

## Result and qualification limit

The finite authentication dependency chain is now implemented and locally
verified: a fixed nonsecret command round trip, current-worker/capture/input
authorization, durable receipts and guarded dispatch. The first live attempt
**failed before VT6 login authorization**, with the retained final discriminator
`provenance:source-changed`. It is not an authenticated-shell qualification.
No VT6 fixture name, password or shell command was submitted. Credentials were
provisioned and staged privately; that is distinct from typing them.

The existing [VT6 contract](../../../tests/e2e/README.md#visible-vt6-installation-terminal)
owns the implementation, regression routes and remaining limits. The
[provenance contract](../../../tests/e2e/README.md#controller-owned-provenance)
now distinguishes the live source-refusal classification from still-missing
changed-file/metadata diagnosis. The [reuse map](../Reuse-Map.md#installation-helper-and-open-limits)
routes downstream installation consumers to these records.

## Implementation and executable checks

- `VT6_SHELL_LINEAGE` supplies the existing process/terminal checks to both
  the fourth identity read and `vt6_command.CommandRoundTrip`. A private shell
  digest pins the original boot, login and shell incarnations. The fixed
  keyboard command creates one nonce-named, mode-0600 marker with noclobber;
  its contents must identify that challenge and shell PID. Preparation requires
  absence; bounded completion requires the command subshell to exit, exact
  contents, safe stable metadata and repeated pinned lineage/boot checks.
  Guest observations remain read-only. Outer baseline restoration removes any
  marker created by a successful future attempt.
- `vt6_authentication.Authentication` composes existing ordered recipient,
  session and exact-pixel checks. A same-filesystem creation barrier and absent
  path/inode bind capture freshness to the trusted worker's ordered input;
  directory/file replacement, old timestamps and renamed old images refuse.
  `VerifiedInputs` binds the reference and source. The worker guard reuses the
  owned `Worker` handle, lease revalidation and staged distribution bytes.
- `Smoke` checkpoints source/run/capture identities before publishing a receipt,
  then rechecks the worker. Existing replies and partial publication refuse.
  Worker capture remains sealed before secret access. It submits one password
  and one fixed command only, and rejects an unexpected positive password-needle
  match on the preceding login screen. Failure, timeout or partial input latches
  the complete attempt; there is no retry or arbitrary command interface.
- `check_graphical_vt6_authentication.py` is the fixed guarded qualification
  entry point. It does not install a package or mark E2E-002 ready. Development
  activation is on the next invocation; no product migration or host setup change.

Verification retained for this slice:

| Scope | Result |
| --- | --- |
| Focused VT6 worker/command/controller/shell/recipient/prompt, Smoke/cleanup, serial and observation tests | 1,968 passed before the final negative-needle/directory additions |
| Final worker/controller selection | 128 passed |
| Final `make check` | 7,167 unit/contract and 58 private-D-Bus tests passed; common source/traceability checks passed |
| Isolated cleanup selection, then the dispatcher's mandatory repeat | Each passed 595 tests and 3 subtests |
| Documentation and whitespace | 241 local links across five documents passed; scoped `git diff --check HEAD` passed |

Focused routes: `tools/run-unit-tests` with
`tests/unit/test_e2e_vt6_authentication.py`, `test_e2e_vt6_command.py`,
`test_e2e_vt6_controller.py`, `test_e2e_vt6_shell.py`,
`test_e2e_vt6_recipient.py`, `test_e2e_vt6_prompt.py`,
`test_graphical_smoke.py`, `test_graphical_smoke_cleanup_safety.py`,
`test_e2e_serial_observation.py`, and `test_e2e_observation_transport.py`
(all under `tests/unit/`), with `-q --tb=short`.
The final two-module selection uses the first and third modules above.
Isolated safety uses `tools/run-unit-tests 'tests/unit/test_*cleanup_safety.py'
tests/unit/test_graphical_lease.py -q`.

Discriminating regressions include `test_real_bash_round_trip_requires_command_parsing`
(success, consumed input, partial line, collision),
`test_actual_marker_reader_checks_file_and_late_identity`,
`test_completion_wait_is_bounded_and_requires_subshell_exit`,
`test_smoke_persists_authorization_before_publication`, and
`test_input_guard_binds_live_worker_and_staged_bytes_and_always_cleans`.

Local failures and recovery remain recorded: initial controller refusal tests
expected the wrong exception class (19 failures); correcting them preserved the
actual refusal. A later one-case failure exposed a wall-clock/filesystem timestamp
race; the filesystem barrier and inode freshness checks replaced that comparison.
The new directory guard then rejected group-writable test fixtures (26 targeted
failures, also 26 failures/7,141 passes in a prematurely started `make check`).
Explicit mode-0700 fixtures corrected the tests without weakening the guard;
the final selections and common check passed. The earlier common check had
passed 7,162 unit/contract and 58 component tests before those final additions.
Several discovery reads used nonexistent guessed paths and were corrected or
abandoned. An evidence JSON parse hit the artifact reader's default 8,000-byte
limit; a bounded `--bytes 40000` checkpoint read recovered the needed fields.

## Live evidence and cleanup

Route: `tools/run-tests integration check_graphical_vt6_authentication`, exit 1.

- Attempt: `/tmp/onpc-graphical-smoke-1uzfb2sp/result.json` and `steps.json`.
- Durable qualification: `/tmp/onpc-e2e-evidence-wi62dy2e/event-000013.json`
  records `stage-started` for `vt6-login-ready`; events through 17 are retained.
- Worker: `/tmp/onpc-e2e-evidence-h4nbkeny/worker-result.json` records failure,
  worker stopped and callback closed. Its ordinary shutdown assertion was not
  reached; guarded outer restoration subsequently passed.
- Captured source: `c44935c26c7be9f2b9366b8699da6803fb7a3b15c1e68cd1649761886e3618ac`.
  Baseline: `cffe72b4c77004a010d2b0341b415853c0afce838efe4762bb84a52665ca0eb5`.
  Worker distribution: `89ec8a538814c67e0245def05f5f3feeaf79264350a2ad92d15a4f30e142fb11`.
  The retained result's input map pins each runtime file. After cleanup, all nine
  changed runtime-file byte digests matched that map. This does not establish
  unchanged metadata or identify the differing checkout input.

The completed stages were `ready`, `gdm`, `selected`, `dismissed`. The next
stage's first input recheck refused before the getty observer and before any
VT6 input receipt. Finalization preserved `provenance:source-changed`, rather
than treating the failed source-preservation flag as an unknown baseline error.
No source writes were made by this session during the attempt. Concurrent Git
index/worktree state changes were observed, but the retained evidence does not
locate the changed input or distinguish its bytes from metadata.

Final lease phase is `complete`, cleanup passed, host preserved, source not
preserved; product and collection outcomes are `not-run`. These outcomes remain
distinct from successful retention of diagnostic checkpoints. All started
commands exited and results were collected. No screenshot export, owned worker,
callback, VM lease or recovery obligation remains. Source edits were preserved;
no logs were modified or deleted. No approval or Polkit denial occurred.

## Milestone review and next action

No further implementation prerequisite is currently identified in the finite
chain. What is missing is its live proof: the provenance refusal prevented the
new auth observers, capture gate, negative needle, password and command from
executing. Existing local checks cannot supply that evidence. Next, capture
fresh current inputs and run this same guarded route after required isolated
safety checks. Preserve this failed attempt. If source drift recurs, obtain a
bounded changed-input/metadata discriminator before another unchanged expensive
attempt; do not weaken provenance or invent a blanket VM hold.

Authentication history is now one guarded attempt, failed before authorization.
Prompt-only history stays two (one failure, one corrected pass); installation
history stays 21 (three historical passes, eighteen failures). All-task VM
clearance persists. Task 20 remains earliest ready with no bypass; Task 15A's
later work remains preserved. Full Task 20 acceptance, live auth, sudo/notice
pixels, complete install/reboot/readiness and both E2E-028 startup faults remain
unfinished. The slice exceeded its planning window to finish integration and
the already-owned VM operation, including 249 seconds of guarded cleanup.

Actual settings: `gpt-6-astra` / `high`, Standard. Next: `gpt-6-astra` / `high`;
model keep, effort keep. The chain is locally proven, but its first real
authorization/input execution and a source-preservation refusal remain unresolved.
