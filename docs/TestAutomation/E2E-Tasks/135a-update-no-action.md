# 135a — Qualify a real update requiring no activation

Use the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **LIFE04 update and LIFE05 no-action notice**. Named consumer: task **135** and any
complete cases released directly by this slice in the canonical queue.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **028** — LIFE01.
- **044** — DESK09; FLOW15 and FLOW01 retained scopes.
- **007** — LIFE02.
- **079** — PARENT16 and FLOW03 public app-policy editing.
- **048a** — Overlay REQUEST04/05/06/08, invalid REQUEST09, REQUEST11/12 Cancel/Escape and FLOW04.

## Implementation

Bind the verified no-action old/new package pair to the shared LIFE04
administrator SSH package command. Independently read completion and its actual
notice through FILE06 without adding a restart; retain mechanical
activation/migration checks. No Terminal rendering or password-prompt exercise.

## Live VM acceptance

Install the declared no-action update, independently read the final notice and unchanged usable app entry/settings. Wrong assets, failed completion or an unexpected activation notice refuse.

Qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_update_no_action
```
