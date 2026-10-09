# 044 — Visit both retained child desktops

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Session boundary

Add both retained child bindings and complete explicit FLOW15 modes. Reuse 044b's Parent entry; keep other-parent management under task 198.

Reuse the delivered scope of tasks **044b** under the
[split-task contract](../E2E-Execution-Contracts.md#task-size-and-order).

## Scope and prerequisites

Deliver **DESK09; FLOW15 and FLOW01 retained scopes**. First scheduled consumer: [E2E-018, case 58](../E2E-Scenario-Recipes.md#e2e-018).
Read the named [block contracts](../E2E-Building-Blocks.md#desktop-and-retained-session-entry), [related block contracts](../E2E-Building-Blocks.md#reusable-journey-fragments) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **044b** — DESK09 and FLOW01 retained Parent entry.

Its transitive prerequisites retain GDM02 retained-child lock entry, DESK08/11
unlock/denial and DESK10 same-desktop window switching.

## Implementation

Implement retained-user routing, reusing normal DESK10 window switching and the qualified fresh-child FLOW15 branch. Extend FLOW15 for explicit same/retained/lock/denied entry. Reuse [qualified retained Parent entry](../E2E-Building-Blocks.md#retained-parent-desktop-and-window-entry), `retained_parent_entry` and `onpc_parent::open_for_child`'s explicit retained/same-user branches; extend their finite account/child bindings as needed without reselection hiding state. Qualify the Parent and both child account/recipient bindings required for these entries. A retained Parent window may be on App Limits: reach Screen Limits with PARENT04 before reading PARENT03. The second administrator's management desktop/window remains the separate other-parent scope.

## Live VM acceptance

On the VM, leave recognizable windows on child and Parent desktops, switch between them, unlock normally and foreground the same windows. Wrong entry modes fail without repairing state; compare retained public activity before relaunching anything.

Implementation: `journey_blocks.desktop_entry` declares the modes used by
`onpc_desktop_session::enter_desktop`; `retained_entry.PLAN` and
`RetainedEntryJourney` bind Riley/Jordan activity and desktop comparisons to the
existing recorder. `session_control.entry_identity` refuses incompatible sources
without repair. The qualification retains Jamie's Riley-selected Parent window,
both child activities, normal Riley lock/unlock, independent retained returns,
configured-zero GDM denial and the native lock restriction. Other-parent
management remains task 198.

Qualification and affected regression selectors (registered; qualification pending):

```sh
tools/run-tests --vm onpc-Ubuntu26.04,onpc-Fedora44 integration check_e2e_retained_entry integration check_e2e_retained_parent integration check_e2e_retained_unlock_success integration check_e2e_retained_unlock integration check_e2e_desktop_session integration check_e2e_window_switch
```

## Current validation and remaining work

Host safety/composition checks passed, as did source checks.
The first live qualification failed on both selected VMs at
`riley-restricted-curtain` (`child-lock-curtain`, `ui:lock-other-surface`).
Both retained child activities, normal Riley unlock, retained Parent state,
foregrounding, configured-zero GDM denial and greeter return passed beforehand;
`riley-restricted-entry-guard` independently confirmed the same locked child.
Both runners completed cleanup/restoration and preserved source/host state.

Retained reports: [Ubuntu](../../../output/test-runs/host/exports/onpc-artifact-export-o0pl6hqm/report.md)
and [Fedora](../../../output/test-runs/host/exports/onpc-artifact-export-zgtvwk5s/report.md).
Investigate this new failure in the next session, preserving the lock-surface
guard and assertions. No diagnosis, repair or retry was attempted after this
failure. All five later regression selectors remain unexecuted. Complete the
qualification and those regressions on both selected VMs before close-out.
