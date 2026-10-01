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

Implementation and scoped host validation passed, including worker-order and
failure-stop, immutable decoder, entry/refusal, recorder durability and cleanup
checks: `output/test-runs/host/reports/20261001T184237Z-d71170cd/report.md`
(2081 checks). Test-only changes do not affect package/build inputs.

The prior Parent-language timeout came from a stale installed package without
the current language controls. Maintained app-snapshot preparation with
`--overwrite true` rebuilt `onpc-v1.2`; guarded maintenance inspection confirmed
the installed language controls, and maintenance stop completed. The new live
run passed Parent setup, public 900-second daily-time preparation, wrong-account
refusal and fresh child entry. Do not repeat the old failure diagnosis.

The new attempt on every enabled VM (currently `onpc-Ubuntu26.04`) failed in
`output/test-runs/host/reports/20261001T184419Z-4be29aa0/report.md` after
`direct-launch`, before `direct-form`, with `e2e:worker-execution-failed`
(`EvidenceError`, `step-2`). The cause remains undiagnosed; this is not an
established product defect. No investigation, repair or retry followed this
new failure. The worker stopped and callback closed, but normal shutdown
verification was false. Owned cleanup, baseline restoration and host/source
preservation passed; collection and overlay acceptance were not reached.

Evidence roots:
`output/test-runs/privileged/allocations/onpc-graphical-smoke-igd8tula`,
`output/test-runs/privileged/allocations/onpc-e2e-evidence-51xfd6l8/worker-result.json`,
and `output/test-runs/privileged/allocations/onpc-e2e-evidence-7tp3pljp`.
The queue summary is
`output/test-runs/host/allocations/onpc-vm-queue-swvkiqw9/results.json`.
Use the maintained artifact reader; keep raw captures private.

Next session: diagnose and repair this retained failure, rerun affected host
checks, then prepare the app snapshot under the shared live contract and run the
qualification without `--vm`. Reuse the refreshed snapshot with
`--overwrite false` unless application inputs change. After qualification passes,
run `check_e2e_kiosk_entry` and `check_e2e_kiosk_eligible_choices` as separate
`tools/run-tests integration` selections for the shared REQUEST03 reader.
Close only after all acceptance and owned cleanup pass. No adviser has been
consulted; apply the current Sol High / bounded Astra High escalation policy.
