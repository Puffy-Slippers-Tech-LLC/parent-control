# Task 20 — fresh-input VT6 attempt reaches password-recipient refusal

## Result

Authentication attempt 2 passed source preservation and the first durable VT6
getty authorization, then failed during `vt6-password-ready`. The fixture name
was submitted; no password authorization, password submission, capture receipt
or shell command followed. The live negative password-needle check on the login
screen passed: the trusted worker could reach the password-ready request only
after that check rejected the login screen.

This advances beyond [attempt 1](20-VT6-Authentication-Attempt-20260910.md), which
refused source provenance before any VT6 input. It does not resolve that earlier
source change or qualify authentication. The [owning VT6 contract](../../../tests/e2e/README.md#visible-vt6-installation-terminal)
and [reuse map](../Reuse-Map.md#installation-helper-and-open-limits) carry the
partial qualification and remaining limitation. No runtime files changed in
this slice; existing integrated code and uncommitted work were preserved.

## Retained evidence and diagnosis

Route: `tools/run-tests integration check_graphical_vt6_authentication`, exit 1.

- Result and steps: `/tmp/onpc-graphical-smoke-mkhqjkrs/result.json` and
  `steps.json`.
- Durable checkpoints: `/tmp/onpc-e2e-evidence-fkw18tqn/event-000013.json`
  through `event-000018.json`.
- Worker result: `/tmp/onpc-e2e-evidence-kyiy9vl8/worker-result.json`.
- Source: `5ef9435310f6bc82d24a8925c113fb87fe16ee28f866580ce6126aa0e2946a81`.
  Baseline: `cffe72b4c77004a010d2b0341b415853c0afce838efe4762bb84a52665ca0eb5`.
  Worker distribution: `89ec8a538814c67e0245def05f5f3feeaf79264350a2ad92d15a4f30e142fb11`.
  The complete runtime input map remains in `result.json`.

Events 13/14 bracket getty authorization at 465.514/604.359 seconds from the
qualification start: **138.845 seconds**. Event 15 starts password readiness at
607.886 seconds; event 16 records failure at 676.881: **68.995 seconds** later.
Boot corroboration passed immediately before the rejected observation. No
password-ready reply exists. Only the four GDM stages and `vt6-login-ready`
have completed receipts.

The retained observation stderr is
`/tmp/onpc-graphical-smoke-mkhqjkrs/private/command-0444-stderr.txt`.
A bounded reader extracted only `AssertionError` and guest-program line 21;
raw exception/terminal text was not emitted. Mapping the fixed
`VT6_PASSWORD_IDENTITY` composition to this line identifies the first
`/proc/<selected-unit-MainPID>/exe == /usr/bin/login` assertion. The actual
executable and cause of the unexpected state are not retained in that safe result.
The failure occurred before digest continuity comparison and echo checks;
it is not evidence of an incorrect password or a failed exact-pixel comparison.

**Leading hypothesis, not established cause:** the login prompt expired while
authorization performed a long recheck. `Authentication.observe` calls
`VerifiedInputs.recheck` before and after each stage. That method includes
`baseline_inputs` → `Capture.verify_snapshot`, including backing-chain digest
verification, as well as a source snapshot. The observed delays warrant timing
these existing components; they do not isolate which one consumed the time.
The guest's effective login timeout and the intervening executable were not
collected. No timeout, provenance, recipient or ownership guard was weakened.

## Verification and cleanup

Isolated prerequisites used `tools/run-unit-tests
'tests/unit/test_*cleanup_safety.py' tests/unit/test_graphical_lease.py -q`:
**595 passed, 3 subtests passed**. The guarded dispatcher's mandatory repeat
passed the same selection. No new runtime edit invalidated the prior common
check; no repeated product suite or package acceptance run was needed.

The live outcome is infrastructure failure `e2e:worker-execution-failed`;
product and collection outcomes remain `not-run`. Diagnostic checkpoints were
retained, which does not turn the collection outcome into a pass. Worker stopped
and callback closed. Normal scenario shutdown was not reached. Outer baseline
restoration passed, lease phase is `complete`, and final host/source preservation
are both true. The original command exited and all readers completed. There
are no screenshot exports, active owned commands or recovery obligations.
No logs were modified or deleted, and no approval or Polkit denial occurred.
Documentation edits began only after finalization exited.
Documentation validation passed 250 local links across the five changed
documents and scoped `git diff --check HEAD`. Two documentation patch attempts
refused invalid context/duplicate-path operations; corrected native patches
applied successfully without changing runtime files.

The runner's final JSON and private-directory listing exceeded display budgets;
selected durable checkpoints and the one relevant stderr supplied the needed
diagnosis without loading raw authentication captures. One search used two
nonexistent guessed baseline-module paths, then located the implementation
through a scoped source search. Neither discovery issue changed test outcomes.

## Milestone review and next bounded result

Task 20 remains earliest ready; no bypass. All-task VM clearance persists;
there is no new outside-input or writer-pause requirement. Authentication
history is now two failed guarded attempts at different boundaries; prompt
history remains two (one failure, one pass), installation history remains 21
(three historical passes, eighteen failures). Full Task 20 acceptance,
authenticated command readiness, sudo/notice pixels, install/reboot/startup and
both E2E-028 startup faults remain unfinished.

Do not repeat this attempt unchanged. Reuse the existing provenance and terminal
helpers. First obtain bounded component timing and a safe selected-unit
executable/timeout discriminator, with executable local refusal/privacy checks.
Review the effective supported login timeout alongside those observations.
If revalidation consumes the prompt lifetime, correct that scheduling/cost
boundary while retaining current-source, baseline, worker and recipient proofs;
if the recipient is already wrong before the delay, diagnose input/recipient
transition instead. Then qualify through the same guarded auth route after
isolated safety checks, collecting both hypotheses in one attempt. No additional
generic authorization gate, prompt-only rediscovery or serial requalification
is indicated. This is the missing live proof under the
[operator course correction](../Task-20.md#operator-course-correction--2026-09-10).

Actual settings: `gpt-6-astra` / `high`, Standard. Next: `gpt-6-astra` / `high`;
model keep, effort keep. The new timing/recipient interaction crosses
authorization and baseline preservation; its cause and safe correction remain
unresolved despite successful final preservation.
