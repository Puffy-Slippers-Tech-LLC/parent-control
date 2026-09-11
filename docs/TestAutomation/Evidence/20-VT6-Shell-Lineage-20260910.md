# Task 20 — VT6 authenticated shell lineage

## Result and limits

Added fixed `VT6_SHELL_IDENTITY` and the fourth, single-use
`ReadOnlyObservations.read('vt6-shell-identity')` observation. It reuses the
existing sudo observer's detached-login/direct-shell-child model and the
recipient gate's boot/unit/PID/start-time digest. The same login incarnation
must survive authentication. The shell must be its sole direct fixture-owned
login Bash child, in its own foreground VT6 session with all standard
descriptors on VT6. Repeated identity, executable, credentials, boot, active-VT
and terminal checks refuse replacement; every opened terminal descriptor closes.
Only fixed booleans and the boot digest reach callers.

The [owning contract](../../../tests/e2e/README.md#visible-vt6-installation-terminal)
and [reuse map](../Reuse-Map.md#installation-helper-and-open-limits) now publish
the helper, tests and limits. The upstream
[login implementation](https://raw.githubusercontent.com/util-linux/util-linux/master/login-utils/login.c)
confirms that the shell creates a new session after login detaches its terminal.
The slice narrowed from combined shell readiness/lineage to executable lineage:
foreground Bash can still execute startup code or a builtin consuming input.
No `vt6_shell_ready_verified` proof is issued. `vt6-session` is independently
required, and shell observation has no startup wait. Dispatch remains disabled.

The next readiness proof should use a fixed nonsecret keyboard command round
trip with fresh completion evidence bound to the current attempt, boot and
pinned shell. Design and implement it under the sealed-capture/no-retry contract;
do not infer parsing readiness from process names, empty children, raw-mode
flags, wait channels or syscalls. Current worker/capture/input provenance and
durable exact-pixel authorization also remain unimplemented. No VM attempt was
started, and no live qualification is added. **All-task VM clearance persists**.

## Verification and inputs

- `tools/run-unit-tests tests/unit/test_e2e_vt6_shell.py
  tests/unit/test_e2e_vt6_recipient.py tests/unit/test_e2e_serial_observation.py
  tests/unit/test_e2e_observation_transport.py -q`: **1,637 passed**, exit 0.
- `test_vt6_shell_follows_only_pinned_login_child` executes the actual guest
  program across 53 success/refusal cases: wrong/replaced unit or child,
  ancestry/session/foreground, process state/start time, credentials/executable,
  binary ownership/mode, descriptors, boot/active-VT and read/open errors.
  Success uses the shell's new session, and terminal cleanup is asserted.
- The recipient tests now cover all four stages, strict output parsing,
  boot/recipient changes, skipped/replayed reads, ownership/transport failures,
  permanent refusal and absence of command/password authorization proofs.
- `make check`: **7,051 unit/contract and 58 private-D-Bus component tests
  passed**, exit 0, including common source and stage traceability checks.
  No source or documentation edits occurred during the command. Common pytest
  time was 116.74 seconds plus 1.52 seconds for private-D-Bus components.
- Documentation checks: **226 local links across five documents, none missing**;
  scoped `git diff --check` passed. Continuation selects the earliest ready task
  and has exactly one supported settings line with a fresh reason.
- No test failed. Two discovery searches referenced nonexistent guessed files;
  scoped discovery/current imports supplied the actual source locations. One
  documentation patch had a context mismatch; another was rejected for duplicate
  path operations. Neither applied changes; corrected explicit updates succeeded.
  These caused no runtime or cleanup fault.
  The GNU Bash manual web endpoint returned an internal error; no conclusion
  relies on that failed fetch. Historical live failures remain in the
  [active handoff](../Task-20.md#task-20-continuation--2026-09-08).

Verified implementation SHA-256 values (documentation updated after checks):

| File | SHA-256 |
| --- | --- |
| `tests/e2e/guest_observations.py` | `fac6f6feb0a33abab93b3f7eeca0a9f93fb1802ae5f8dd2feefd3f2df03676b8` |
| `tests/e2e/observation_transport.py` | `8221bc02e45a47d2b316c78a8c4db2fb8da8a1cf7622cc92273a4c3ecb25fda8` |
| `tests/unit/test_e2e_vt6_shell.py` | `9265bd78274f7d48855610cdb1848f8c381e69d7023ad80ba718251344b15d4e` |
| `tests/unit/test_e2e_vt6_recipient.py` | `6a1cce321750c517791e51b19ce63489480b19b6d07d893182793bd89f4c2e72` |

## Handoff and cleanup

All started test commands exited with results collected. No VM operation, lease,
worker, callback, screenshot export or recovery obligation was created. No
approval or Polkit denial occurred. The worktree started clean; unrelated work
was preserved. No source logs were changed. Prompt history remains two attempts
(one failure, one corrected pass); installation history remains 21 (three
historical passes, eighteen failures).

Task 20 remains earliest ready, with no bypass. Task 15A remains preserved.
Task 20 acceptance, live command readiness/authentication, sudo/notice pixels,
complete install/reboot/startup and both E2E-028 faults remain unfinished.
Actual settings: `gpt-6-astra` / `high`, Standard. Next recommendation remains
`gpt-6-astra` / `high`: lineage now passes locally, while command-round-trip
authorization and fresh capture/durable receipt binding remain unresolved
security and correctness boundaries.
