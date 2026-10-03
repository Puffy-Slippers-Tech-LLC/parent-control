# 300 — Installed personal-language acceptance

Follow the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract),
[capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance)
and [scenario acceptance](../E2E-Execution-Contracts.md#scenario-acceptance).
This task is active at the developer's request;
no installed qualification or scenario completion is claimed.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):
- **300a** — Declared Chinese baseline language assets and independent FIX06 readiness verification.

Estimate: 60–90 minutes.
Session exception: The installed persistence and account-isolation history includes a real upgrade without reboot, the required reboot and renewed kiosk sessions in one continuous case, retaining independent language choices and unchanged policy results throughout.

## Scope

Use [Localization](../../SystemDesign/Localization.md#validation-contract) and
[personal language selection](../../SystemDesign/Frontends.md#personal-language-selection)
as the behavior owners. Use `en`, `de`, `zh-Hans`, and `he` (Hebrew), with different
personal choices for the administrator and the two children. Parent retains the
administrator's choice when its selected child changes. The overlay and panel
share the signed-in child's choice; kiosk follows its selected child's choice,
independently of the station's desktop language or selected approver. All product
language interactions use public controls, without direct writes to preferences
or private backend probes.

The added kiosk regression uses **Simplified Chinese only**, with the kiosk
station and administrator desktop languages left English. Retain the existing
representative multilingual/RTL acceptance below; do not multiply the new
upgrade/reboot/authentication history by those languages. Compose all of this
task's acceptance into **one complete E2E case**, not separate cases for each
reported symptom. The fixed Chinese history is owned by
[the Chinese kiosk language lifecycle recipe](../E2E-Scenario-Recipes.md#chinese-kiosk-language-lifecycle-planned-task-300).

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

Chinese language installation belongs exclusively to `tools/prepare-baseline`:
task 300a qualified the installed locale, system/PolicyKit translations and CJK
font assets there, with idempotent reconciliation and independent read-only FIX06
verification on Ubuntu 26.04. Attempts
and app-snapshot preparation only verify them. Use the planned shared
**DESK13** building block for the child's desktop-language switch through a
supported system API; the case passes the account and `zh_CN.UTF-8`, never
implements a setter or edits locale files. See
[Chinese language preparation and desktop-language setup](../E2E-Building-Blocks.md#chinese-language-preparation-and-desktop-language-setup).
Product language selection still uses the existing public chooser operations.
Observe first presentation before `complete_language_setup` or any generic
first-run handler can save, dismiss or change it.

Reuse LIFE04's package lifecycle path and LIFE02's reboot path. The real
v1.2-to-current upgrade without reboot, selected-child reboot-required result,
DESK13 and Chinese MATE authentication binding need qualification before this
case can run. The existing English MATE provider qualification does not qualify
Chinese labels or a restarted agent. Use supported locale/session APIs and the
normal unmodified PolicyKit agent; no dialog patching or injected translations.

## Acceptance to implement

1. Observe first-run session default and native language names, save one explicit
   choice, then reopen Preferences and read its checked choice and translated
   visible/accessibility text through stable IDs. Select another candidate and
   Cancel; reopen and observe the original choice. Use a small representative
   installed slice; local failure/retry, layout and chooser permutations remain
   with [UI coverage](../UI-and-E2E-Coverage.md).
2. Set independent administrator and two-child languages through Parent,
   overlay and kiosk Preferences. Switch selected children/approvers: Parent
   retains the administrator's language, kiosk restores the selected child's
   language, and changing approver leaves the request language unchanged.
   Reopen the same child's overlay to confirm its choice is shared with kiosk
   and panel. Close/relaunch Parent and overlay, return to the kiosk and renew a
   child session; observe retained selections and translated surfaces without
   another first-run chooser.
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
   catalogues work without downloads, including German, CJK and Hebrew text.
6. Explicitly validate Hebrew RTL presentation on installed Parent, child
   overlay, child panel (including its tooltip/menu) and kiosk, plus inherited
   About and feedback dialogs. Switch from English to Hebrew and back through
   public Preferences; observe RTL direction and logical alignment in Hebrew,
   restored LTR direction in English and legible, unclipped Hebrew text. Check
   mixed Hebrew/Latin text, account/application names, numeric durations and
   synthetic draft/reply content for correct bidirectional presentation and
   unchanged values. Verify usable keyboard navigation, stable public control
   IDs and matching translated visible/accessibility labels in both directions.
   Preserve selections, drafts, focus and policy/countdown behavior throughout;
   another RTL language or host-only layout evidence does not replace this
   installed Hebrew acceptance. Keep exhaustive scale/layout permutations with
   [UI coverage](../UI-and-E2E-Coverage.md).
7. Execute the linked Chinese lifecycle recipe before saving any personal
   language preference for the selected child: real upgrade with no intervening
   reboot, Chinese reboot-required prompt, reboot, Chinese first-run language
   dialog and initial kiosk form, explicit Chinese save and real approval,
   then fresh kiosk re-entry and a second real approval. Require Chinese native
   PolicyKit buttons and system-owned explanatory/password text as well as the
   product-owned request message on both approval prompts. Observe actual
   translated controls and public results; an environment setting, product
   message alone, mocked prompt or English approval pass does not cover this.

## Session boundary

Task 300 remains unchecked. Queue repair extracted its first missing capability
as **300a**, immediately before this task. Its Chinese baseline and read-only
FIX06 qualification passed, including the native fixture regression.
This task retains the complete
multilingual/RTL and Chinese lifecycle history, with no acceptance credit from
the extraction. DESK13 has no callable or qualification, LIFE04 qualifies only
fresh installation, and the native authentication provider is qualified only
for English. Allocate those remaining prerequisite slices before implementing
or registering the single complete case. No live attempt has been made.

## Implementation entry

Before implementation, allocate stable scenario IDs, recipes, worker bindings
and any prerequisite qualification tasks under the execution plan's sizing and
ordering contract. Insert any newly identified prerequisite immediately before
its consumer and split independent capability work before implementation. No
executable selector is registered by this brief. Leave this row unchecked until
that work and installed acceptance are complete.

Allocate exactly one numeric case for the complete history; the Chinese phases
are ordered assertions inside it. Reuse task 300a's qualified baseline language
readiness. Qualify DESK13,
the real update/reboot-required composition and the Chinese native provider
binding in bounded prerequisite slices before registering that complete case.
Preserve the v1.2 package asset/version gate: unavailable verified upgrade inputs
remain a blocker, never a simulated reboot-required state or a reinstall.
