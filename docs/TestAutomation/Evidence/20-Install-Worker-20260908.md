# Task 20 installation worker integration and first live attempt

Scope: authenticated installation helper qualification, **not accepted** and
not E2E-002 product coverage. Actual settings: `gpt-6-astra` / `high`, Standard.
Task 20 remains earliest ready; no bypass. The all-task VM clearance persists.

## Implemented and locally verified

`check_graphical_smoke.Smoke` now orders the three installation stages between
authenticated serial login and logout/GDM return. It drains pending serial input
before observations, rejects post-authentication screenshots, binds the existing
`InstallationBoundary` to the guarded observer and persists each safe proof
before publishing its reply. `smoke.pm` dispatches `onpc_serial::run_install`.
The accepted non-installation paths retain their original actions.

The host-safe and installed dispatchers accept the mutually exclusive fixed
`--qualify-install` option with verified artifacts, rejecting scenario/list
overrides. It enables fixture credentials and the serial transport under the
existing lease. No arbitrary command or package-path argument is exposed.
`./setup.sh --test-tools-only` refreshed the dispatcher successfully; existing
scoped grants sufficed, with no approval or Polkit denial. Activation is `none`
(next invocation); no product integration or saved-data change.

Verification:

- `tools/run-unit-tests tests/unit/test_graphical_smoke.py tests/unit/test_e2e_runner.py tests/unit/test_e2e_install_helper.py tests/unit/test_e2e_installation_boundary.py tests/unit/test_e2e_serial_helper.py -q`:
  **130 passed, 1.68s**, handle 22498, exit 0. Includes buffered-input,
  observation/checkpoint failure, capture refusal and qualification-selector cases.
- Isolated `tools/run-unit-tests 'tests/unit/test_*cleanup_safety.py' tests/unit/test_graphical_lease.py -q`:
  **521 passed, 3 subtests, 5.08s**, handle 13498, exit 0.
- `make check`: **3,202 unit tests, 72.90s; 17 private-D-Bus tests, 0.46s**;
  stage traceability and common checks passed, handle 19206, exit 0.
- Scoped staged/unstaged whitespace and documentation link checks passed.

## Live result and evidence

Build: `tools/run-tests artifacts build`, handle **58025**, exit 0;
`/tmp/onpc-test-artifacts-9z7n87ja`. Run:
`tools/run-tests e2e --qualify-install --artifacts /tmp/onpc-test-artifacts-9z7n87ja`,
handle **14331**, **exit 1**, **1004.446s**. The dispatcher repeated its isolated
safety prerequisite: 521 passed, 3 subtests, 6.25s. No checkout edits occurred
from build through terminal collection/cleanup.

| Evidence | Location |
| --- | --- |
| Terminal result, exact source/package/environment identities, stages and split outcomes | `/tmp/onpc-graphical-smoke-8268hxwi/result.json` |
| Ordered, secret-scanned qualification checkpoints | `/tmp/onpc-e2e-evidence-2fb6zkxs/event-000001.json` through `event-000024.json` |
| Worker result and cleanup | `/tmp/onpc-e2e-evidence-ko22adks/worker-result.json` |
| Private module result and fixed failure text | `/tmp/onpc-graphical-smoke-8268hxwi/testresults/result-smoke.json`, `smoke-17.txt` |
| Private worker diagnostics; use fixed-token filters only | `/tmp/onpc-graphical-smoke-8268hxwi/worker-private.log` |

Package SHA256: `ee74297247c1b4b61628b53eb5e12998dcb10a678939e6a021ca730a51664c0f`.
Source SHA256: `bc51ff6b0519fbe40c1bf40b4c7981733afbf808b23a1e11ee9b0a202e26a447`.
Handoff edits invalidate reuse of these artifacts for the next attempt.

The run verified fixture credentials, transferred assets, GDM observations,
real serial login and `install-ready`: package/core payload absence, verified
assets, active fixture session and unchanged boot identity. The fixed command
was typed. **The 30-second sudo-prompt match failed** before any
`install-password` request; no sudo password or package-completion proof was
sent. This is a prompt acquisition/matching failure, **not a sudo identity-probe
refusal**. The expected prompt text in log lines 98–102 includes command/regex
logging and does not prove that the guest rendered that prompt. Line 102's
fixed `: fail` outcome discriminates this from an installation precondition
failure. The serial wrapper collapses its internal error to
`serial:qualification-failed`; raw terminal contents were not exported.

The backend exited 0 but recorded a failed module, correctly failing the
qualification as `e2e:worker-execution-failed`. Product outcome is `not-run`;
collection's aggregate label remains `not-run` on this failure, although the
checkpoint collector verified and terminal reports are retained. No successful
installation, deliberate live denial, reboot, readiness or startup-fault
acceptance is claimed. **One expensive attempt on this prompt blocker; no retry.**

## Cleanup and next discriminating observation

Worker stopped and callback closed. Its `shutdown_verified=false` records that
normal journey shutdown was not reached; the outer guard powered off and
restored/verified the retained baseline. Terminal lease phase is `complete`,
cleanup passed, and host/source preservation are true. The command exited and
released its lease. No owned operation, exported screenshot or recovery remains.
Reading `serial-console.out` metadata through the artifact helper refused its
nonregular FIFO type; it was left untouched, with no alternative access. One
diagnostic regex used unsupported lookbehind and was corrected to a fixed-token
filter; no raw authentication output was emitted. No execution-policy denial.

Next: add locally tested, fixed safe installation checkpoints and prompt-result
diagnostics to distinguish sudo command failure, prompt bytes/terminator mismatch
and absent input without exposing terminal text. Inspect the pinned public API
where necessary; retain exact-command/no-echo/process proof and capture sealing.
Then build fresh artifacts and run one guarded diagnostic attempt. Establish a
real success and deliberate live refusal before expanding to reboot/readiness.
Do not simply relax the regex or repeat this unchanged attempt.

Next settings: `gpt-6-astra` / `high`; unresolved live authentication diagnosis
and privacy boundaries still require Astra. Remaining Task 20 estimates are
**Unknown sessions / Unknown minutes**: one measured attempt took 16.7 minutes,
but successful installation, reboot continuity and both startup faults remain
unqualified. The slice ran past its initial review budget to finish the owned
attempt, final provenance checks and guarded cleanup.
