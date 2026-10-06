# 155a — Compare overlay choices at the kiosk

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **FLOW12 overlay-to-kiosk choices for both children**. Named consumer: task **155** and any
complete cases released directly by this slice in the canonical queue.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **048a** — Overlay REQUEST04/05/06/08, invalid REQUEST09, REQUEST11/12 Cancel/Escape and FLOW04.
- **044** — DESK09; FLOW15 and FLOW01 retained scopes.
- **180** — FLOW01 same-user entry; FLOW16 fresh/same Parent allowance setup.

## Implementation

Compose only overlay-to-kiosk with explicit exit/entry and immutable comparison. Duration/custom/soft-app follow the child; preserve local approver defaults.

## Live VM acceptance

Publicly enable both children, seed different overlay values and local approvers, then enter kiosk and read each destination before editing. Finish with the form open and qualify independent valid entry.

Qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_choices_overlay_to_kiosk
```
