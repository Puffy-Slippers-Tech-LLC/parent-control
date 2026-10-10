# 141b — Remove the product and follow its reboot notice

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 40–60 minutes.

Session exception: Actual removal, the customer reboot, usable child entry and package cleanup checks form one qualification.

## Scope and prerequisites

Deliver **LIFE04 remove and LIFE05 removal activation**. Named consumer: task **141** and any
complete cases released directly by this slice in the canonical queue.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **007** — LIFE02.
- **047** — APP04 and FLOW08 native usable-app observations.
- **014** — FLOW04 kiosk.

## Implementation

Bind only the verified remove command to AUTH03's administrator authority and
shared guarded SSH package helper. Independently read completion and the final
reboot notice through FILE06; no Terminal or unrelated password prompt is
needed. Compose the shared LIFE02 reboot command and ordinary child entry using
existing qualified operations.

## Live VM acceptance

Remove through the shared administrator SSH package helper, read the real reboot notice, reboot normally and enter the child to use the fixture app. Pass applicable package cleanup checks; do not assert reinstall persistence yet.

Qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_product_remove
```
