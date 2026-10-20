# R05a — Repair visibility by supported capability

Acceptance: host

Required tasks: R04 — both-platform early architecture proof.
Estimate: 60–90 minutes; [R01 mechanism estimate](../SystemDesign/Kiosk-Confinement.md#implementation-estimates-after-integrated-review).
Size independent work before execution; this forecast does not expand the session exception or reduce acceptance.

Read the [master](../Kiosk-Resilience-Plan.md#target-design), R01's accepted
configuration decision in the [lifecycle owner](../SystemDesign/Lifecycle.md#r01d-configuration-and-quarantine-decision)
and [task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract).

## Session boundary and deliverable

Extract AccountsService visibility repair from R05. Read complete
`repair_kiosk_visibility()`, cache-version/schema/transaction and provisioning/
package callers. Implement R01d's selected recognized-key-file boolean adapter,
clean visible-state fast path and public fresh-cache/readback route without
exact-version admission. Preserve unknown/unowned fields,
ordinary users and ownership checks; do not write an unknown schema blindly.
An unfamiliar compatible version alone cannot veto setup. Validate actual grammar
and the single target key; no private write on unknown/ambiguous representation.
Keep exact slot recovery, stopped-daemon serialization and one bounded retained
repair/reload with durable plus public verification. R05b owns quarantine
release and R08a owns optional icon fallback.

## Acceptance and close-out

Use registered provisioning/lifecycle host checks for compatible-version repair,
unsupported actual capability/schema, interrupted transaction and unrelated
metadata preservation. Distinguish simulated version variation from a real
dependency update. Final installed F controls must prove public visibility,
passwordless entry and approval; host tests supply none. Require the master's
product review/revision and final packaged-input `make build`; update current
implementation/ledger and record exact changes for R05/R09c1. Complete owned cleanup.
