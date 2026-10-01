# 048 — Qualify direct and panel entry to the child overlay

Use the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **DESK12, REQUEST02 direct entry, REQUEST13 panel entry and REQUEST03 overlay readback**. First scheduled consumer: [E2E-015, case 44](../E2E-Scenario-Recipes.md#e2e-015).
Read the named [block contracts](../E2E-Building-Blocks.md#desktop-and-retained-session-entry), [related block contracts](../E2E-Building-Blocks.md#kiosk-child-overlay-and-the-shared-request-form) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **043** — GDM06/07, DESK01 and FLOW15 child fresh entry/denial; DESK11 rejected-GDM return.
- **011** — REQUEST01, REQUEST03.

## Implementation

Qualify normal unlocked-child panel routing (DESK12). For ordinary overlay entry, invoke the installed child command through REQUEST02 and independently observe form count and fixed child with REQUEST03. Separately qualify REQUEST13's graphical panel entry for E2E-012's explicit launch and singleton check. Reuse the shared immutable reader. Choice editing, exits and authentication are separately qualified bindings; fullscreen reveal belongs to its game consumer.

## Live VM acceptance

On the VM with publicly prepared usable child time and fresh child entry, directly invoke the child command and observe exactly one form with the intended fixed child and readable controls. Cancel and repeat from an independently reached child desktop. In a separate entry, activate the panel request control twice deliberately and observe exactly one form with the same fixed child. Use normal Cancel solely to end qualification; this does not qualify the reusable exit binding. Never select another overlay child.

Implemented callables: `shell_panel.PLAN` / `ShellPanelJourney`,
`journey_blocks.overlay_entry` / `onpc_request_flow::overlay_entry`,
`AccessibleUI.overlay_panel_target`, `overlay_panel_launch`, and
`kiosk_request_form(enabled=True, overlay=True)`. The immutable
`RequestObservation` validates `overlay-request-form` independently.
`onpc_challenges::shell_panel` composes the qualification in the existing envelope.
Host safety and installed qualification remain required before closing this task.

Registered qualification selector:

```sh
tools/run-tests integration check_e2e_shell_panel
```

## Recovery boundary

The previous direct-form diagnostic parser defect and stale language snapshot
are resolved. Preserve the guarded shared stream parser and default approver
Casey (`other-fixture-parent`); no product behavior decision is pending.

The retained panel failure in `20261001T185732Z-c40fe452` was mechanical:
`private/command-0367-stderr.txt` under
`output/test-runs/privileged/allocations/onpc-graphical-smoke-he7zlyrl`
reports `ui:missing-action`. [Shell 50's button accessibility implementation](https://github.com/GNOME/gnome-shell/blob/50.0/src/st/st-button.c)
has no Action interface. The ID/session/owner readiness checks passed before
any activation. Shared `overlay_panel_launch` now focuses the ID-owned control
through Component, independently reacquires the same focused target with prompt
guards, then releases one Enter in `onpc_request_flow::overlay_entry`.
Focus failure and uncertain input cannot replay; form readback remains independent.
The host reproduction failed before this correction in `20261001T190910Z-109a8736`.

All 2302 affected host checks passed in
`output/test-runs/host/reports/20261001T191104Z-ad41a766/report.md`, including
focus/ownership/prompt/replay refusals, actual worker key order and failure stops,
shared diagnostic decoding, immutable projections, cleanup and bundle guards.
Scheduling/plan checks passed 123 checks in `20261001T191332Z-f225d67f`.
Test/tool/documentation changes do not affect package/build inputs.

Maintained snapshot preparation reused `onpc-v1.2` with `--overwrite false`;
both recorded maintenance stops completed successfully. Live qualification on
every enabled VM (the enabled Ubuntu target at the time) failed in
`output/test-runs/host/reports/20261001T191702Z-cab9c288/report.md` after
`direct-launch`, before `direct-form`, with `e2e:worker-execution-failed`
(`CommandError`, `step-2`; terminal category `command:failed:ssh`). Parent setup,
public 900-second daily-time preparation, wrong-account refusal and fresh child
entry passed. The panel correction was not reached. The cause of this new
failure remains undiagnosed; no investigation, repair or retry followed it.
Worker stopped and callback closed, but normal shutdown verification was false.
Owned cleanup, baseline restoration and host/source preservation passed;
collection and the kiosk regressions were not reached. A subsequent guarded
status probe confirmed the VM off.

Retained evidence:
`output/test-runs/privileged/allocations/onpc-graphical-smoke-z0mgkzqv`,
`output/test-runs/privileged/allocations/onpc-e2e-evidence-qdq7xs8b/worker-result.json`,
`output/test-runs/privileged/allocations/onpc-e2e-evidence-hb_ahubl`,
and `output/test-runs/host/allocations/onpc-vm-queue-jr6tvnbu/results.json`.
Use the maintained artifact reader and keep raw captures private.

Next session: recheck cleanup, diagnose and repair this new failure, finish
affected host validation, then prepare through the shared live contract and run
`check_e2e_shell_panel` without `--vm`. Reuse the refreshed snapshot unless app
inputs change. After it passes, run `check_e2e_kiosk_entry` and
`check_e2e_kiosk_eligible_choices` separately without `--vm` for shared REQUEST03.
All enabled VMs and owned cleanup must pass before close-out. No adviser has
been consulted; apply the current Sol High / bounded Astra High escalation policy.
