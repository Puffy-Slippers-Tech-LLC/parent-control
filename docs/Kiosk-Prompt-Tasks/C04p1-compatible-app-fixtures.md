# C04p1 — Verify baseline app fixture applicability

Acceptance: host

Required tasks: C04c.
Estimate: 20–30 min.

Apply the [master contract](../Kiosk-Session-Confinement-Plan.md#task-execution-contract),
[shared task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../TestAutomation/E2E-Execution-Contracts.md#capability-acceptance).

## Session boundary and deliverable

Verify the shared fixture deliverable from
[E2E task 313a](../TestAutomation/E2E-Tasks/313a-compatible-native-fixtures.md)
for the suspended [C04p consumer](C04p-app-effects.md). General fixture preparation
and its new automation belong to that E2E task, not this confinement queue.
The current directory
contains Allowed `Exact Fixture.AppImage`, a space-bearing ELF nonmatch for S's
`Lunar Client-*.AppImage`. The common renderer cannot safely allow that exception;
it deliberately omits the whole wildcard group and Parent opens its error report.
Live C04p diagnosis confirmed this with current fixture and compiler bytes.
Changing only the temporary renderer input to skip A removed the issue; no guest
state was changed. See the consumer's retained evidence and the
[owning application contract](../SystemDesign/Applications.md#live-filter-and-execution-rules).

Read the delivered 313a scope, current fixture inventory/verifier and the
[cross-plan reuse map](../TestAutomation/E2E-Building-Blocks.md#cross-plan-baseline-reuse).
Verify the exact full S target/wildcard, public A/H/S oracle, distinct instances,
source-keyed input provenance and no-omission/refusal checks apply to the baseline.
Keep Allowed A, precise whitespace H and wildcard S outcomes unchanged. Changed
paths or bytes invalidate affected old evidence; unchanged names supply no pass.

## Validation and return condition

Blocker: E2E 313a has not delivered compatible inputs. Resume when its exact host
results and source/fixture handoff are retained. This task checks applicability;
it does not execute that other workflow or absorb its implementation. Preserve
the failure evidence and return the missing feature work to its E2E owner.

Reuse valid host evidence; run only affected consistency/applicability checks
with finite timeouts. Supply no installed enforcement, approval or app-use claim,
and leave C04p unchecked. No VM refresh or development-host installation is needed.
