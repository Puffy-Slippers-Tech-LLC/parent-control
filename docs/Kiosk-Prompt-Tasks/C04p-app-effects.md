# C04p — Validate baseline time and app effects using E2E coverage

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

Required tasks: C04c, C04p1.
Estimate: 20–30 min.

Apply the [master contract](../Kiosk-Session-Confinement-Plan.md#task-execution-contract),
[shared task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../TestAutomation/E2E-Execution-Contracts.md#capability-acceptance).

## Session boundary and deliverable

Consume [E2E task 313](../TestAutomation/E2E-Tasks/313-native-grant-effects.md)'s
finite both-target grant/use/revocation history under the
[reuse map](../TestAutomation/E2E-Building-Blocks.md#cross-plan-baseline-reuse).
That E2E task owns new general policy, fixture-instance, duration and denial
bindings and their installed qualification. This task owns their applicability
to the rebuilt confinement baseline, not a second feature implementation.

Verify retained exact candidate/caller/provider/fixture evidence, positive
grant-only time, usable A/S, denied H, public revoke/Confirm, zero grant,
unchanged saved rules, S denial, time restriction and full public/owned
restoration. Reuse matching installed results. Run the existing
`check_e2e_baseline_app_effects` selector on both targets only if evidence is
missing or invalidated, keeping its original inputs and 1800-second bounds.
Feature defects or missing shared bindings return to E2E 313; confinement-caused
entry/lifetime defects remain in this queue with targeted regression coverage.

Blocker: E2E 313's installed qualification is pending. Resume with its retained
both-target results and C04p1's applicability check; do not execute the other
workflow implicitly. Update B2 only for verified exact scope, preserving stable
IDs, failures and pending variants. This supplies no complete C05 journey.

## Retained work and return condition

The qualifier and finite H/S, A-primary/S-secondary, strong execution-denial and
600-second public-request bindings are implemented. Focused host validation
passed 4,522 checks in `20261021T165658Z-c5db5cc0`; five strengthened
diagnostic-route checks exercise the real native-action chain. Independent test
review found an A/S foreground-order problem; closing S before A resolved it.
No product code changed and no installed acceptance passed.

The latest installed attempts stopped at `soft-final-match` on both targets:
Ubuntu `20261021T164144Z-4bb8c339`, Fedora `20261021T164144Z-b0f7c88d`. A separate
owned Ubuntu reproduction reached the same saved S policy; public API reads
found a modal `feedback-dialog`. The installed renderer reported exactly S's
wildcard omitted, with strict reason `existing nonmatching executable cannot be
represented`. An in-memory-only comparison excluding Allowed A from the
exception candidates restored the directory guard. No policy or files changed.
All six inspected native/GUI files matched the guest receipt and frozen input
hashes; the installed compiler matched current source. This is the documented
[rule-isolation limitation](../SystemDesign/Applications.md#live-filter-and-execution-rules),
not evidence of a new confinement defect. The current shared directory contains
Allowed space-bearing ELF A; H is blocked and S matches, so neither supplies
that conflicting nonmatch.

E2E 313a now owns compatible fixture preparation, E2E 313 owns completion of
the retained qualifier, and C04p1 checks the fixture handoff. Preserve the original
uninterrupted grant/use/revocation/restoration history on both targets.
Do not suppress the warning, block A, replace S's wildcard with a precise rule,
or infer any approval/app-use/revocation credit from these stopped attempts.
The maintenance reproduction was
`onpc-baseline-app-effects-diagnosis-oebqmhja`; its workers and callbacks closed.
The owned maintenance instance was restored and stopped; both targets are off.
All helpers finished, temporary probe scripts were removed, and no Git close-out
or development-host product installation occurred. Plan/launcher consistency
passed 670 checks in `20261021T171132Z-c42e34f9`; structure, links and diff checks
passed. Only test/tooling/documentation changed, so no product build was required.

The verified cumulative [evidence bundle](../../output/test-runs/host/exports/onpc-evidence-bundle-dpr498bp/evidence.zip)
retains 126 files, including both original failures, latest per-target results,
current host reports, diagnostic prefix and fixture-input manifests. Its SHA-256
is `4967eb4584cf98073da50a1c52e99b9c272a273afa1336eeca8cc34e795e72da`.
The latest results retain `lease_phase=complete`, source/host preservation and
cleanup passed; product and collection are not-run. Preserve those original
outcomes when resuming. The live read-only causal probe and source review supply
diagnosis only, not installed acceptance.
