# 047a — Compose retained app visits for distinct users

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **FLOW09 and FLOW14 distinct-user retention**. First scheduled consumer: [E2E-010, case 25](../E2E-Scenario-Recipes.md#e2e-010).
Read the named [block contracts](../E2E-Building-Blocks.md#reusable-journey-fragments) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **047** — APP04; FLOW08 native usable-app scope.
- **044** — DESK09; FLOW15 and FLOW01 retained scopes.

## Implementation

Compose FLOW09 from legitimate retained entry, APP04 comparison and APP03 use.
Compose FLOW14 from the explicit per-user entry, FLOW08, activity capture and
Switch User sequence. Carry the prior observations and current surface; do not
replace an existing desktop or relaunch an app to satisfy continuity.
Same-child multiple desktops retain their separate gate.

Implement the missing FLOW09/FLOW14 shared declaration/worker using
`journey_blocks.desktop_entry`, `native_activity_entry`, `native_activity_resume`
and `InstalledJourney.check_activity`. Current fixture activity is a finite
native-primary submitted draft; add only the declared user's binding needed by
case 25: the foreground Parent as well as the existing child roles. Current
`native_activity_entry` / `native_activity_resume` accept only the two child
roles; explicitly extend the Parent identity/result path before advertising
FLOW14's Parent branch. Retained entry consumes the existing session/activity ledger, never the
complete 044 qualifier or its denial/lock branches.

## Live VM acceptance

On the installed VM, prepare and capture recognizable activities for the child
and declared other user, preserving both through normal Switch User. Return
legitimately to each original desktop and prove the same activity remains
usable. FLOW14 starts and ends at GDM; FLOW09 ends at the named usable activity.
Independent retained entry must work; a missing prior observation or wrong
entry mode refuses without recreating state.

Planned qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_retained_app_visits
```
