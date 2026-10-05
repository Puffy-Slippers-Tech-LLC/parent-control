# 307c — Qualify enabled Parent Hebrew policy observations

Follow the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Required tasks (queue IDs; use delivered scope, not predecessor briefs):
- **306a** — Enabled Parent account/policy/name/balance observations in English and Chinese.
- **307a** — Installed Parent English/Hebrew chooser and keyboard presentation route.

Estimate: 20–30 minutes.

## Scope and acceptance

Qualify one missing result binding needed by the
[Parent presentation recipe](../E2E-Scenario-Recipes.md#parent-language-presentation-planned-task-307):
Jamie manages Riley with screen-time control enabled, a public 60-minute
allowance, zero grant and captured application rules. Use normal Parent controls
for setup; capture an immutable English policy/account/application-name and
balance baseline before changing language through Preferences.

Observe English → Hebrew → English management labels, accessible switch name,
allowance and expanded public time explanation. Independently read the selected
child UID/name, unchanged saved allowance, enabled control, complete app rules
and application names at each boundary. Require zero one-time grant, equal daily
and total balances and positive daily time no greater than 3600 seconds. Compare
later balances against the immutable English capture with the existing
600-second elapsed bound and two-second refresh/formatter tolerance. Bind Hebrew
duration text to its numeric result; no private state or translated-string-only
substitute may establish preserved policy.

Use two independent public read entries per language, closing any chooser before
policy observation. Reuse the qualified chooser's checked-choice/focus/navigation
operations. Refuse a wrong selected child, disabled control, wrong allowance,
wrong language and malformed public balances before a successful recorder reply.
Follow the [no-visual acceptance rule](../../Mandates/UI-Automation-Mandate.MD#input-and-independent-results).
This capability supplies no inherited-dialog, approval or complete-case credit.

## Implementation entry and reading route

The gap is explicit in `PARENT_LANGUAGE_STATES`,
`AccessibleUI.parent_language_state`, `time_explanation` and `duration_projection`
in [accessible_ui.py](../../../tests/e2e/accessible_ui.py). Extend only the finite
Riley/Hebrew enabled binding, retaining existing English/Chinese bindings and
guards. Follow the decoder's enabled `language_state` branch in
[ui_observations.py](../../../tests/e2e/ui_observations.py).

Reuse the shared InstalledJourney/worker path and public language comparisons:
`ParentLanguageIsolationJourney` / `ISOLATION_PLAN`, `ParentRtlJourney` / `RTL_PLAN`
in [parent_language.py](../../../tests/e2e/parent_language.py),
[language_composition.py](../../../tests/e2e/language_composition.py), and
`onpc_parent::language_selection`, `language_navigation` and
`qualify_language_isolation` in
[onpc_parent.pm](../../../tests/integration/graphical_smoke/lib/onpc_parent.pm).
The [language catalogue](../E2E-Building-Blocks.md#personal-language-selection)
owns current qualified scopes. The new qualification owns its finite inputs,
immutable capture endpoints and literal Hebrew management/balance oracles;
shared libraries own mechanics and reusable comparisons.

Host checks must exercise real GTK Hebrew allowance/expanded explanation,
actual controller decoding, recorder success/refusal and the worker's real
checkpoint order. Extend
[language safety regressions](../../../tests/unit/test_parent_language_cleanup_safety.py)
and [GTK language checks](../../../tests/ui/test_language_settings.py);
retain affected time-explanation and existing English/Chinese checks. Review
applicable unit/cleanup/UI resource classifications when adding modules or
changing ownership. Finish composition preflight before live input.

## Live qualification

Implement the planned argument-free selector
`check_e2e_parent_hebrew_policy` in the maintained integration/worker envelope;
it is not yet registered. Bind preparation and launch to matching current-source
named package inputs. Use authorized app-snapshot preparation with overwrite
false for test-only changes, and release maintenance before execution.

After host validation, run the fixed qualification and required enabled-policy,
chooser and public-time regressions on the selected VM through `tools/run-tests`:

```bash
tools/run-tests --vm onpc-Ubuntu26.04 integration check_e2e_parent_hebrew_policy
tools/run-tests --vm onpc-Ubuntu26.04 integration check_e2e_parent_language_isolation check_e2e_parent_rtl check_e2e_time_explanation
```

Require collection, worker shutdown, owned cleanup, baseline restoration,
finalization, preservation and retained reports for every required slice. Apply
the launcher's first-new-live-failure handoff boundary. Close only 307c after its
acceptance passes; return to task 307 in a fresh session without registering or
implementing that complete case here.
