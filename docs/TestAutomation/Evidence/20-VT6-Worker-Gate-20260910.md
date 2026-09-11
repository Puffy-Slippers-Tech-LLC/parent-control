# Task 20 — one-shot VT6 authentication worker gate

## Result and scope

Implemented `onpc_vt6::authenticate(exchange)` with a distinct, exact controller
receipt protocol. It reuses the maintained prompt needle, public os-autoinst
VNC/password APIs and `onpc_password` capture sealing. It requires exact-pixel
authorization before secret access, submits once, and requires independent
session/shell/lineage proofs before returning success. Failed or partial input
never retries. The credential-free inspector shares the attempt latch.
The [owning VT6 contract](../../../tests/e2e/README.md#visible-vt6-installation-terminal)
contains the protocol, canonical tests and its limitations; the
[reuse map](../Reuse-Map.md#installation-helper-and-open-limits) links this result.

This completes the worker boundary only. `smoke.pm` does not select the new
function, and no existing callback can issue its authorization. The broader
input-route slice was bounded here after inspection confirmed the existing
probes establish process identity only within individual observations, while
the session probe establishes neither shell readiness nor cross-observation
login continuity. Those missing capabilities must be implemented before enabling
the controller or qualifying live input. The fixed stage/boot receipts reject
reordering and boot changes, but alone cannot identify a same-stage/same-boot
replay. The controller must bind current worker, capture and input provenance.
No new collector, generic terminal fallback, setup or VM maintenance was added.

## Verification

- Initial worker/inspector selection: **110 passed**.
- After adding late console/policy-change checks:
  `tools/run-unit-tests tests/unit/test_e2e_vt6_authentication.py
  tests/unit/test_e2e_vt6_prompt.py tests/unit/test_e2e_secret_variables.py
  tests/unit/test_e2e_serial_helper.py tests/unit/test_e2e_needle_inputs.py
  tests/unit/test_graphical_worker.py -q --tb=short`: **309 passed**.
- `make check`: **exit 0**, **6,841 unit/contract and 58 private-D-Bus component
  tests passed**, plus stage traceability and common source checks. Checkout
  inputs remained unchanged through completion; documentation followed.
- `test_one_shot_worker_seals_capture_before_receipt_and_secret_access`
  exercises the actual Perl worker and invokes the real capture helper at both
  sensitive boundaries to prove it is sealed.
- Receipt tests cover mandatory booleans, wrong shapes/fields/types, reordered
  stages, boot changes and refusal without secret retrieval before authorization.
  API/credential tests cover malformed secrets, failed/partial typing or Enter,
  shared inspector/authentication latches and fixed error privacy.
  `test_late_console_or_capture_policy_change_prevents_submission` covers loss
  immediately before typing and immediately before submission.
- No tests failed in this slice. No VM/build or acceptance attempt was made.
  Historical [prompt attempts](20-VT6-Prompt-Qualification-20260910.md),
  [matcher failures and correction](20-VT6-Pixel-Gate-20260910.md), and
  [installation/reboot evidence](../Task-20.md#task-20-continuation--2026-09-08)
  remain unchanged; local worker tests do not extend their live scope.
- Documentation validation: **211 local links across five documents, none
  missing**; scoped `git diff --check` passed. Continuation contains exactly one
  supported settings line and selects the earliest ready task.

## Cleanup and continuation

All started commands exited and results were collected. No VM lease, worker,
callback, screenshot export or recovery obligation was created. No approval or
Polkit denial occurred. Prior workspace edits were preserved. **All-task VM
clearance persists**; missing controller implementation limits live readiness.

Task 20 remains earliest ready, with no bypass; Task 15A's later work remains
preserved. Task 20 acceptance, sudo/notice pixels, full installation/reboot/startup
and both E2E-028 startup faults remain unfinished. Next implement the controller's
recipient/capture continuity and shell-readiness proofs, then connect this worker
and qualify the smallest guarded authenticated success/refusal after isolated
safety checks. Do not repeat prompt-only collection or issue placeholder proofs.

Actual settings: `gpt-6-astra` / `high`, Standard. Next settings:
`gpt-6-astra` / `high`, Standard: the worker protocol is locally verified, but
controller authorization, capture freshness and cross-observation process/session
continuity remain unresolved security/correctness boundaries.
