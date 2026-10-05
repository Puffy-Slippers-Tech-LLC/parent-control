# 307a — Qualify installed Hebrew presentation observations

Follow the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Required tasks (queue IDs; use delivered scope, not predecessor briefs):
- **300g** — Installed Parent public language selection.

Estimate: 20–30 minutes.

## Scope and acceptance

Qualify Parent and its language chooser through an English → Hebrew → English
Preferences history. Independently compare public logical Text with the heading's
accessible name, the four native choices and checked language. Observe Cancel
focus, one normal Tab, then fresh Save focus in each language, including a second
independent chooser entry. Save and Cancel preserve selected child, zero disabled
allowance, policy rows and control identities; compare management text separately.
Refuse wrong owner, duplicate/missing IDs, stale or incomplete text, disabled
controls, mismatched labels and unexpected focus before further input/reply.

## Shared implementation

`AccessibleUI.language_presentation` extends the shared bounded LANG01 reader
with public Text/name, ID-addressed focus actions and FOCUSED observations. Later surfaces require
their own qualification. `ParentRtlJourney` / `RTL_PLAN` in
[parent_language.py](../../../tests/e2e/parent_language.py) retain the finite
history and independent literal/policy comparisons. `onpc_parent::language_navigation`
owns the guarded keyboard step; `qualify_rtl` composes the fixed slice.
Keep the affected public-observation/keyboard safety regressions and real GTK
direction/alignment checks in [test_automation_identity.py](../../../tests/ui/test_automation_identity.py).

## Implementation entry

Registered selector: `check_e2e_parent_rtl`; installed qualification pending.
Retain `check_e2e_parent_language` and affected host safety checks.

## Acceptance gate — rendered presentation

Resolved by the developer on 2026-10-05: remove visual review for this and all
future tasks and retain the no-geometry mandate. Apply the owning
[presentation acceptance rule](../../Mandates/UI-Automation-Mandate.MD#input-and-independent-results).
Public logical text, labels, identities, keyboard focus/navigation and unchanged
values remain acceptance. Pixel rendering, glyph order, clipping, font legibility
and visual alignment are excluded; no installed visual proof is claimed.
Existing host GTK direction/alignment engineering checks remain applicable.

The prior session established that public logical text and formatting cannot
independently prove rendered glyph order or unclipped legibility. It ran no VM
attempt and established no product defect. Its proposed geometry/visual-review
exception was rejected; it is not an authorized route.
