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

The retained direct-form failure was a mechanical controller defect: the shared
form reader emitted valid diagnostic JSON lines and a successful final reply,
but overlay observation bypassed the station's guarded stream parser.
`UiObservations.call` now parses both surfaces with the same diagnostic and
sole-final-reply guards while keeping child-session binding separate.
Real controller decoding, arbitrary chunks, malformed streams and owned
transport timeout are covered. Scoped host checks passed all 2229 checks in
`output/test-runs/host/reports/20261001T185452Z-e1115191/report.md`;
scheduling/plan checks passed 190 checks in `20261001T185632Z-a23477dc`.
Test/tool/documentation changes do not affect package/build inputs.

The stale app snapshot was previously rebuilt with current language controls;
this session reused `onpc-v1.2` with `--overwrite false` and released maintenance
ownership. Do not repeat the resolved snapshot or diagnostic-parser diagnosis.

The new attempt on every enabled VM (currently `onpc-Ubuntu26.04`) failed in
`output/test-runs/host/reports/20261001T185732Z-c40fe452/report.md` after
`panel-panel`, before `panel-launch`, with `e2e:worker-execution-failed`
(`CommandError`, `step-2`; terminal category `command:failed:ssh`). Parent setup,
public 900-second daily-time preparation, wrong-account refusal, fresh child
entry, both direct launches/fixed-child form assertions, their Cancel/desktop
returns and panel readiness passed. The new cause remains undiagnosed; this is
not an established product defect. No investigation, repair or retry followed
this new failure. The worker stopped and callback closed, but normal shutdown
verification was false. Owned cleanup, baseline restoration and host/source
preservation passed; collection, panel acceptance and required live kiosk
regressions were not reached. A subsequent status probe confirmed the VM off.

Evidence roots:
`output/test-runs/privileged/allocations/onpc-graphical-smoke-he7zlyrl`,
`output/test-runs/privileged/allocations/onpc-e2e-evidence-pt4v4ifs/worker-result.json`,
and `output/test-runs/privileged/allocations/onpc-e2e-evidence-9tqa9tj0`.
The queue summary is
`output/test-runs/host/allocations/onpc-vm-queue-s6qtakgd/results.json`.
Use the maintained artifact reader; keep raw captures private.

Next session: diagnose and repair this retained failure, rerun affected host
checks, then prepare the app snapshot under the shared live contract and run the
qualification without `--vm`. Reuse the refreshed snapshot with
`--overwrite false` unless application inputs change. After qualification passes,
run `check_e2e_kiosk_entry` and `check_e2e_kiosk_eligible_choices` as separate
`tools/run-tests integration` selections for the shared REQUEST03 reader.
Close only after all acceptance and owned cleanup pass. No adviser has been
consulted; apply the current Sol High / bounded Astra High escalation policy.
