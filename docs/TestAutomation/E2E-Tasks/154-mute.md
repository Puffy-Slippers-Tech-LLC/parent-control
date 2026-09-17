# 154 — Deferred qualification of restored mute

This is future-feature scope, outside current-release completion. No active
task depends on it. Reconsider only after a real product release restores the
public mute control; current absence cannot qualify interaction.

## Read only this context

Use the [scoped reading rules](../E2E-Execution-Plan.md#load-only-the-selected-context).
After the feature gate opens, read only the restored mute contract and qualified
request-form/toggle callables. No other task brief or full queue is needed.

## Scope and prerequisites

Required implemented capability: **048a** — overlay/kiosk request choices,
normal exits and UI17. Use its maintained callables plus the restored feature's
contract. Preserve the saved-field obligations under
[engineering reconciliation](../E2E-Building-Blocks.md#inventory-reconciliation).
No old task document or VM state is required.

## Conditional live VM acceptance

After restoration, qualify the real control on both installed VM forms: read
initial state, set the explicit value and verify the specified surface-local
behavior and persistence through normal public exits/re-entry. Do not enable a
test-only feature switch. Require independent entry and owned cleanup. Plan this
as a focused 20–40-minute slice; split new feature requirements before work if needed.

## Close out

Keep this row unchecked while deferred. After actual implementation and live
acceptance, update the qualified scope in
[E2E-Building-Blocks.md](../E2E-Building-Blocks.md) and applicable recipe status in
[E2E-Scenario-Recipes.md](../E2E-Scenario-Recipes.md).
After any completed E2E scenario and cleanup, run
`tools/generate_test_coverage.sh` (`tools/generate_test_coverage.py`).

Only then check the [master's queue](../E2E-Task-Queue.md), refresh the
master's **Next task** pointer and remove this brief when
no longer needed, replacing its link with plain text. Validate Markdown with
`tools/read-only links`. Preserve normal artifacts; no new history document.
