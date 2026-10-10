# 062 — Use an app until a natural enforced lock

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **TIME04**. First scheduled consumer: [E2E-008, case 22](../E2E-Scenario-Recipes.md#e2e-008).
Read the named [block contracts](../E2E-Building-Blocks.md#time-and-ordinary-lifecycle-boundaries) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **052a** — TIME02 minute/final-second ticks.
- **047** — APP04; FLOW08 native usable-app scope.

## Implementation

Compose bounded APP03 actions/TIME03 waits, TIME02 only while visible, and public lock/input-ownership observations. Receive earlier visible balance and deadline explicitly.

Add the missing TIME04 shared declaration/worker around
`journey_blocks.native_activity_entry`, normal fixture use and
`real_interval.interval_action`; terminate on the independently observed owned
lock result. Reuse the qualified lock-surface observer for identity and harmless
input ownership, without invoking its preparatory manual Lock or replaying its
password/denial matrix. Absence of the app under a lock is not app closure.

Ready that observer before the activity loop and await the owned lock within
the original measured expiry bound. End normal app input when the observed
session leaves the usable desktop; do not race a final action against an
assumed tick or keep sending app input after lock. Shared fresh recipient
guards remain required for every action. Fixed settling sleeps and the passage
of the expected deadline supply no lock result.

## Live VM acceptance

From daily-only time prepared through customer controls, use the actual app until natural exhaustion. Observe the owned lock surface receiving harmless normal input while desktop interaction is unavailable; a password challenge is not required when the qualified surface displays a native time restriction. No manual Lock, backend expiry, or hidden-window inspection.

Planned qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_natural_expiry
```
