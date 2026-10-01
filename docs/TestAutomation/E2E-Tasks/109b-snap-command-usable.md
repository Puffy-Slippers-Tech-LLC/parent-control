# 109b — Launch and use Snap fixtures by command

Apply the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and the task-specific scope and acceptance below.

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **APP01/02/03/04 and FLOW08 Snap command usable/new-window route**. Named consumer: task **109** and any
complete cases released directly by this slice in the canonical queue.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **109p** — Snap baseline assets and verification; FIX04 transfer only.
- **079a** — APP02 and FLOW08 native grid/command policy results.

## Implementation

Reuse the qualified installed Snap profile and guarded SSH command binding. Bind fixed command launch, owned window/usability observations, immutable activity and a supported separate-window command.

## Live VM acceptance

Launch each declared Snap fixture, perform its normal action, capture S and open a distinguishable second instance while the earlier activity remains. Qualify independent guarded SSH command entry and wrong-scope/echo-only/uncertain-input refusal.

Apply [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Implement and register this fixed argument-free qualification, with its cleanup
coverage, before invoking it:

```sh
tools/run-tests integration check_e2e_snap_command_usable
```

## Close out

Follow [completion and document cleanup](../E2E-Execution-Contracts.md#completion-and-document-cleanup)
after this task's acceptance and owned cleanup pass.
