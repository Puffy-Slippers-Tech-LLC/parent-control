# 300j — Qualify kiosk selected-child language restoration

Follow the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).
Qualify one fixed REQUEST04/LANG01 station account/language binding; no complete
scenario or other language surface is qualified by this task.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):
- **024c** — Qualified multiple-account fixture, exact kiosk child/approver sets and all four English selection pairs with independent form readback.
- **300g** — Qualified public Parent language observations and ordinary launch/persistence mechanics.
- **300h** — Qualified fixed Jordan kiosk chooser Save/Cancel, translated form observations and normal re-entry.

Estimate: 20–30 minutes.

## Scope and finite qualification

Use [personal language selection](../../SystemDesign/Frontends.md#personal-language-selection)
and [the localization validation contract](../../SystemDesign/Localization.md#validation-contract)
as behavior owners. Use the current-source installed product and the normal
English station/administrator desktop languages. Keep Jamie's product language
English. Enable Riley and Jordan through public Parent controls with zero daily
allowance; record each child's public settings, time balances and app rows.
No request is submitted and no language or policy preference is written privately.

This capability qualification may use the maintained installed snapshot for the
latest verified current-source package. It does not own package installation,
reboot-required presentation or Chinese approval acceptance. Task 300's linked
[Chinese recipe](../E2E-Scenario-Recipes.md#chinese-kiosk-language-lifecycle-planned-task-300)
now starts product-free, installs the latest package once and tests its Chinese
pre-reboot prompt, reboot, first presentation and two real approvals. Do not add
a v1.2 installation, upgrade or dual-package input to 300j or its consumer.

1. Enter the dedicated kiosk through the shared station entry. Independently
   bind its selected public child UID. Use the shared public chooser to save
   Jordan's German choice and Riley's Hebrew choice. Observe each checked choice
   and translated visible/accessibility form text independently; account names
   remain unchanged. Initial setup of an unset child uses the shared chooser,
   with its separate input/result boundary, not a copied selector sequence.
2. Switch Jordan → Riley → Jordan through the public child selector. Before each
   input bind the owning station, selected child and current language; after
   selection independently require the new UID and that child's retained
   language, no startup chooser, and translated form. Reopen Preferences, read
   the checked choice and Cancel without saving another candidate. Retain the
   default 1800-second request, no custom text and soft apps excluded for both
   children; compare each child's own before/after projection.
3. For each selected child, switch Jamie → Casey → Jamie through the public
   approver selector. Require the same child, checked language and translated
   form after each switch; only the approver identity changes. Check exact
   offered UID sets and unchanged literal account names. The chosen approver's
   language must not determine the request language.
4. Leave normally, enter a fresh kiosk session, select each child again and
   independently observe German/Hebrew and its checked preference without
   first-run setup. Return normally to Jamie's Parent window and compare both
   children's public policy/time/app projections to their recorded originals;
   require English Parent presentation and its retained English choice.
5. Exercise independent valid entries and wrong-surface, wrong-child,
   missing/duplicate UID, wrong offered-set, stale ownership and mismatched
   pre/post-language refusal before input. Retain uncertain-input terminal
   behavior and never replay a selection whose effect is unknown.

## Shared implementation and scoped reads

Reuse [LANG01](../E2E-Building-Blocks.md#personal-language-selection) and
[REQUEST04](../E2E-Building-Blocks.md#kiosk-child-overlay-and-the-shared-request-form).
Read complete `AccessibleUI.select_kiosk_account`, `kiosk_account_snapshot`,
`kiosk_request_form`, `read_language`, `kiosk_language_form`,
`request_language_operation` and their affected callers in
[accessible_ui.py](../../../tests/e2e/accessible_ui.py).
The original preflight found English-only offered-choice labels, selected-account
descriptions and form readback, with the kiosk language form bound to Jordan.
The active implementation adds explicit bounded account/language bindings in these shared owners,
including distinct pre-input and resulting language on a child switch. Preserve
default English consumers, automatic setup's separate confirmed input and the
fixed Riley overlay's active-session/child guard. Readiness and checked choices
must be observed, not inferred from submitted values or catalogue lookups.

Trace the new nondefault identity/language through operation registration,
[UiObservations](../../../tests/e2e/ui_observations.py), decoder/recorder comparisons,
[journey_blocks.language_selection](../../../tests/e2e/journey_blocks.py),
[onpc_parent::language_selection](../../../tests/integration/graphical_smoke/lib/onpc_parent.pm)
and the shared [request worker](../../../tests/integration/graphical_smoke/lib/onpc_request_flow.pm).
Reuse the finite literal chooser/form oracles from
[kiosk_language.py](../../../tests/e2e/kiosk_language.py), with caller-owned
per-child capture and preservation assertions. Extend shared mechanics; do not
copy `onpc_request_flow::kiosk_language` into the new qualification.
The product's translated account label/description contract is in
`GatewayDropDown.set_items` / `_describe_trigger` in
[request_content.py](../../../kiosk/oh_no_parent_control_kiosk/request_content.py).
No product change is established as necessary by this preflight.

Supporting checks include the affected kiosk-language and kiosk-account-selector
unit/UI tests, recorder/schema/actual worker-order checks and applicable cleanup
inventory. Use [composition preflight](../E2E-Building-Blocks.md#composition-preflight)
for nondefault child and mismatched receipt/result tests before live entry.
The [UI/E2E allocation](../UI-and-E2E-Coverage.md) retains exhaustive chooser,
failure/retry and layout permutations on the host.

## Live selectors

The argument-free selector and current-source automatic input preparation are
now registered in the working tree. Implementation and qualification are still
in progress; registration alone establishes no acceptance. Complete its shared
worker, assertions and supporting validation before running:

```bash
tools/run-tests --vm onpc-Ubuntu26.04 integration check_e2e_kiosk_language_restoration
```

Required affected fixed-language and English selector regressions:

```bash
tools/run-tests --vm onpc-Ubuntu26.04 integration check_e2e_kiosk_language
tools/run-tests --vm onpc-Ubuntu26.04 integration check_e2e_kiosk_eligible_choices
```

If the shared overlay form/chooser boundary changes, retain:

```bash
tools/run-tests --vm onpc-Ubuntu26.04 integration check_e2e_overlay_language
```

Shared Parent launch changes retain case 6 under the execution contract. Run
each selected VM with the launcher's ownership/watch/snapshot/collection/cleanup
guards. These selectors supply only their exact qualifications, never the
complete Chinese or multilingual/RTL scenarios in the acceptance decomposition.

## Session boundary

This session completes only this fixed station restoration slice and its
required regressions. Its finite German/Hebrew acceptance is unchanged.
The [acceptance decomposition](../E2E-Scenario-Recipes.md#personal-language-acceptance-decomposition)
assigns the remaining independent histories and missing capabilities to tasks
300k, 300 and 306–310. After close-out, advance the next-task pointer to 300k;
leave those tasks to normal later execution. This slice supplies no complete-case
acceptance.

The launcher's saved task-300 handoff predates both the latest-install scope
and this decomposition. Current briefs and recipes supersede its combined-case
and Chinese-upgrade wording. Preserve checkpoints, prompts and evidence; do not
restore 300c/300d as required upgrade prerequisites.
