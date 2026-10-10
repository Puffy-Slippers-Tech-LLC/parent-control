# 079d — Observe native launch denial without a prior window

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **APP02 and FLOW08 native grid/command blocked-launch results**. Named consumer: task **079a** and any
complete cases released directly by this slice in the canonical queue.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **079** — PARENT16 and FLOW03 public app-policy editing.
- **047** — APP04; FLOW08 native usable-app scope.

## Implementation

Bind usable, hidden-grid and explicit command-denial observations under publicly saved Allowed/Hard/Soft choices. A hidden grid result requires its separately declared command-denial witness.

Reuse `AccessibleUI.native_launch_command(blocked=True)` and the existing
`native-command-blocked` operation's permission-error and complete-absence
witness. That fixed command leaf is already consumed by `removal_journey.PLAN`;
it does not qualify native-grid hiding, arbitrary targets or both rule choices.
Add the missing finite APP02/FLOW08 denial declaration/worker and grid projection,
preserving one launch per declared route and independent result readback.

The current command/snapshot adapter is restricted to native A/`primary`.
Extend it with finite declared role/instance arguments for the A/H/S/N outcomes
consumers need, including separately identified Allowed and blocked activities.
Use the existing fixture's primary/secondary public-ID scheme and fixed launch
options when simultaneous windows are required; duplicate IDs or a different
window cannot be accepted as the declared target. This is missing implementation,
not scope supplied by the existing A-only qualifier.

## Live VM acceptance

In fresh VM attempts with no earlier target window, save each declared access choice and observe native grid/command results, including an unaffected allowed target. Qualify independent valid entry; incomplete absence cannot pass.

Planned qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_native_denial
```
