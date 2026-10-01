# 187a — Observe and decline a overlay cooldown error

Apply the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and the task-specific scope and acceptance below.

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **REQUEST09 overlay cooldown and FEED15 decline branch**. Named consumer: task **187o** and any
complete cases released directly by this slice in the canonical queue.

**Gate:** The normal overlay reopen-and-Request sequence must complete within the actual five-second cooldown.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **048b** — Overlay AUTH01/02, valid REQUEST09, REQUEST11/12 both approved exits and FLOW05/07.
- **044** — DESK09; FLOW15 and FLOW01 retained scopes.
- **052c** — TIME03.
- **030** — FEED05; FEED10 dialog persistence.

## Implementation

Qualify the normal overlay reopen/re-entry and Request before the real five-second cooldown ends. Observe the actual too-soon result and decline reporting through owned controls. Preserve the existing public-route applicability gate.

## Live VM acceptance

Approve once on the VM, perform the normal return-and-Request within five seconds, read the error and decline. Independently observe the declared form/desktop or GDM destination and original balance before another approval. An unreachable route stays pending; no timing changes or forced errors.

Apply [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Implement and register this fixed argument-free qualification, with its cleanup
coverage, before invoking it:

```sh
tools/run-tests integration check_e2e_overlay_cooldown_error
```

## Close out

Follow [completion and document cleanup](../E2E-Execution-Contracts.md#completion-and-document-cleanup)
after this task's acceptance and owned cleanup pass.
