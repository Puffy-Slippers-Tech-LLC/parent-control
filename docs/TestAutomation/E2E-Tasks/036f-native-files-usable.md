# 036f — Launch separate usable native windows from Files

Apply the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and the task-specific scope and acceptance below.

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **APP01/02/03 native file-manager usable/new-window route**. Named consumer: task **036a** and any
complete cases released directly by this slice in the canonical queue.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **036** — FILE05 bounded copy/rename; FIX04 synthetic files.
- **079a** — APP02 and FLOW08 native grid/command policy results.

## Implementation

Open Files directly at the prepared fixture directory through FILE04, then bind
only the exact fixture's activation and supported separate-window action. Reuse
the existing location adapter if needed; no folder browsing, copy operation,
Properties dialog or view customization belongs to this launch check. Reuse
owned app observations and one normal usability input.

## Live VM acceptance

Launch from Files, observe a normal action's effect, then open a distinguishable second window beside the first. Independently compare the original activity; wrong file or a reused first window refuses.

Apply [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Implement and register this fixed argument-free qualification, with its cleanup
coverage, before invoking it:

```sh
tools/run-tests integration check_e2e_native_files_usable
```

## Close out

Follow [completion and document cleanup](../E2E-Execution-Contracts.md#completion-and-document-cleanup)
after this task's acceptance and owned cleanup pass.
