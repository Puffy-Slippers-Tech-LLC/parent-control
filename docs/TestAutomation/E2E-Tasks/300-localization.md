# 300 — Installed personal-language acceptance

Follow the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [scenario acceptance](../E2E-Execution-Contracts.md#scenario-acceptance).
This task is queued for future implementation at the developer's request;
no installed qualification or scenario completion is claimed.

Required tasks: none (Baseline).

## Scope

Use [Localization](../../SystemDesign/Localization.md#validation-contract) and
[personal language selection](../../SystemDesign/Frontends.md#personal-language-selection)
as the behavior owners. Use only `en`, `de`, and `zh-Hans`, with different
choices for the administrator, child and kiosk accounts. The overlay and panel
share the child's choice; selecting a child or approver never transfers language
ownership. All language interactions use public controls, without direct writes
to product preferences or private backend probes.

## Shared implementation

Reuse `AccessibleUI.language_scope`, `open_language_preferences`,
`choose_language`, `save_language`, `cancel_language`,
`language_save_completed` and `complete_language_setup` in
[the shared public adapter](../../../tests/e2e/accessible_ui.py).
[UI chooser coverage](../../../tests/ui/test_language_settings.py) uses these
same operations. Extend the existing worker/staging path for installed bindings;
do not copy the chooser sequence into a case or add a second selector layer.
Reuse shared Parent/overlay command entry, account/session switching, request,
panel, About and feedback operations. The scripted
[language fixture](../../../tests/support/language_fixture.py) is host-only and
must never supply installed persistence or authorization evidence.

## Acceptance to implement

1. Observe first-run session default and native language names, save one explicit
   choice, then reopen Preferences and read its checked choice and translated
   visible/accessibility text through stable IDs. Select another candidate and
   Cancel; reopen and observe the original choice. Use a small representative
   installed slice; local failure/retry, layout and chooser permutations remain
   with [UI coverage](../UI-and-E2E-Coverage.md).
2. Set independent administrator, child and kiosk languages through each
   account's Preferences. Switch selected children/approvers and observe that
   each surface retains its owning account's language. Close/relaunch Parent and
   overlay, return to the kiosk and renew a child session; observe retained
   selections and translated surfaces without another first-run chooser.
3. Change the child's language through the overlay, close it and observe the
   panel's updated visible/accessibility text. Reopen the overlay and resume the
   child session to exercise refresh. Observe countdown progression and normal
   expiry locking through existing public blocks; changing language must not
   reset time, grant extra access or alter limits/application policy.
4. Observe inherited About/feedback language and preserved synthetic draft/reply,
   selected accounts and numeric request values after switching. Keep system
   account/application names unchanged. Exercise one ordinary approval/result
   per request surface through the existing approval flow; translated results
   must retain the same public request and policy behavior.
5. Reopen independent accounts to confirm persistence/isolation using public
   selected values and product results. Run offline to establish that packaged
   catalogues work without downloads, including German and CJK text.

## Future entry

Before implementation, allocate stable scenario IDs, recipes, worker bindings
and any prerequisite qualification tasks under the execution plan's sizing and
ordering contract. No executable selector is registered by this brief. Leave
this row unchecked until that future work and installed acceptance are complete.
