# 307 — Parent Hebrew presentation and inherited dialogs

Follow the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).
Also apply [scenario acceptance](../E2E-Execution-Contracts.md#scenario-acceptance).

Required tasks (queue IDs; use delivered scope, not predecessor briefs):
- **306a** — Parent account/policy language observations.
- **307a** — Installed Parent Hebrew/LTR presentation route.
- **307b** — Inherited Parent About/feedback language and retained synthetic draft.

Estimate: 20–30 minutes.

## Scope and acceptance

Compose one complete English → Hebrew → English Parent history from the
[fixed recipe](../E2E-Scenario-Recipes.md#parent-language-presentation-planned-task-307).
Observe management and Preferences, inherited About/feedback logical text and
exact mixed-script content through qualified public observations under the
[no-visual acceptance rule](../../Mandates/UI-Automation-Mandate.MD#input-and-independent-results).
Retain child/application names, policy, stable IDs, keyboard usability and focus.
Compare the synthetic body/reply through dialog close, language change and
reopen before new input. Host-only direction assertions cannot pass this case.

## Shared implementation

Reuse 306a/307a/307b operations in the established InstalledJourney/worker path. The case owns one finite history and its independent comparisons.

The [Parent dialog qualification](../E2E-Building-Blocks.md#parent-inherited-dialog-qualification)
supplies `AccessibleUI.parent_dialog_presentation` / `parent_dialog_operation`,
`open_about(..., language=...)`, `open_feedback(..., language=...)`,
`feedback_snapshot('synthetic-rtl')` and `onpc_parent::dialog_navigation`.
Reuse `onpc_text::replace_text` with `body-rtl` / `reply-rtl` and its guarded
worker input. `ParentDialogLanguageJourney` / `DIALOG_PLAN` in
`tests/e2e/parent_language.py` demonstrate the qualified fixed history; the case
must declare its own endpoints and immutable comparisons through shared APIs.
The qualified disabled-zero policy does not supply the recipe's enabled
60-minute Hebrew management readback. Verify that exact binding before composing it.

## Implementation entry

One planned complete case; no numeric coverage ID or executable is registered.
Allocate one stable scenario/coverage binding for the linked recipe before
implementation. Run that exact case through the maintained E2E launcher and
regenerate coverage at close-out. Prerequisite qualification is not case acceptance.
