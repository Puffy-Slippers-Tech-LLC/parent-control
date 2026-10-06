# 187b — Observe and decline a kiosk cooldown error

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **REQUEST09 kiosk cooldown and FEED15 decline branch**. Named consumer: task **187k** and any
complete cases released directly by this slice in the canonical queue.

**Gate:** The normal station re-entry-and-Request sequence must complete within the actual five-second cooldown.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **021** — FLOW05/06/07 kiosk.
- **044** — DESK09; FLOW15 and FLOW01 retained scopes.
- **052c** — TIME03.
- **030** — FEED05; FEED10 dialog persistence.

## Implementation

Qualify the normal kiosk reopen/re-entry and Request before the real five-second cooldown ends. Observe the actual too-soon result and decline reporting through owned controls. Preserve the existing public-route applicability gate.

## Live VM acceptance

Approve once on the VM, perform the normal return-and-Request within five seconds, read the error and decline. Independently observe the declared form/desktop or GDM destination and original balance before another approval. An unreachable route stays pending; no timing changes or forced errors.

Qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_kiosk_cooldown_error
```
