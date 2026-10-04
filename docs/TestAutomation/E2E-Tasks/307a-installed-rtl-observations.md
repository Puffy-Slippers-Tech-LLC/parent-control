# 307a — Qualify installed Hebrew presentation observations

Follow the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Required tasks (queue IDs; use delivered scope, not predecessor briefs):
- **300g** — Installed Parent public language selection.

Estimate: 20–30 minutes.

## Scope and acceptance

Qualify a bounded public observation route for Parent and its language chooser:
English → Hebrew → English through Preferences. After stable-ID resolution,
independently observe actual RTL direction/logical alignment, restored LTR,
matching visible/accessibility labels, mixed Hebrew/Latin text and usable keyboard
navigation/focus. Preserve selected child, policy and control identities.

This is a missing capability: current host direction tests inspect GTK widgets
directly and review images explicitly supply no test outcome. They do not
establish installed acceptance. Determine whether the supported public semantics
can prove the required presentation, including legible, unclipped Hebrew and
correct bidi rendering. Catalogue direction, selected language, text presence,
private GTK probes and screenshots alone cannot supply that proof. Follow the
UI mandate's geometry/layout restrictions; if the required result has no
permitted observation route, retain that concrete gate and obtain the missing
acceptance decision before claiming qualification. Do not weaken the requirement
or silently authorize a new selector technique.

Refuse wrong owner, duplicate/missing IDs, stale or incomplete attributes, wrong
direction and mismatched focus/results; qualify independent valid entry.

## Shared implementation

Start at `AccessibleUI.read_language` / `parent_language_management`,
[localization_review.py](../../../tests/support/localization_review.py),
[test_automation_identity.py](../../../tests/ui/test_automation_identity.py) and
the [UI mandate](../../Mandates/UI-Automation-Mandate.MD).
Extend one shared bounded observation contract, usable by later GTK surfaces;
each later surface still requires its own installed qualification.

## Implementation entry

Planned selector: `check_e2e_parent_rtl`; unregistered and unqualified.
Register its fixed binding before invoking
`tools/run-tests integration check_e2e_parent_rtl`.
Retain Parent LANG01 and affected public-observation/keyboard safety checks. Host layout permutations remain with UI coverage.
