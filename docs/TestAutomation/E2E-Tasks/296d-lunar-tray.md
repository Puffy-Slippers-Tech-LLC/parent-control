# 296d — Close Lunar to its tray and restore it

Apply the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and the task-specific scope and acceptance below.

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **APP06 Lunar/tray snapshot and close-to-tray/restore**. Named consumer: task **296** and any
complete cases released directly by this slice in the canonical queue.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **296c** — APP01/02/03/UI18 Lunar original-AppImage usable launch and Quit.

## Implementation

Extend the qualified Lunar adapter with the actual tray owner/entry and independent surrounding-desktop snapshots. Keep window close distinct from genuine Quit.

## Live VM acceptance

Launch Lunar, close to tray, observe the tray with the main window absent, restore the same Lunar surface, then Quit through the qualified operation. Wrong tray owner, incomplete absence and uncertain input refuse.

Apply [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Implement and register this fixed argument-free qualification, with its cleanup
coverage, before invoking it:

```sh
tools/run-tests integration check_e2e_lunar_tray
```

## Close out

Follow [completion and document cleanup](../E2E-Execution-Contracts.md#completion-and-document-cleanup)
after this task's acceptance and owned cleanup pass.
