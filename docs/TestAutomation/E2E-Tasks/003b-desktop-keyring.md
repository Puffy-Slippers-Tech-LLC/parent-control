# 003b — Cancel a real keyring prompt after login

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Session boundary

Add real gcr Cancel and resume the interrupted observation without replay. Use 003ba for positive no-prompt login; the real-prompt profile and prompt-replacement refusals below remain required.

Task **003ba** supplies the extracted operations through its maintained
callables and qualified scope. The delivery below is cumulative with those
prerequisites. Implement only the remaining slice above. Keep the original
acceptance results: reuse valid independent-branch evidence, and run every new
composition and any earlier branch affected by the change. No saved VM state or
predecessor brief is an input to this session.

## Scope and prerequisites

Deliver **GDM05 successful fresh fixture entry; DESK01; real gcr prompt Cancel and independent desktop readback**.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **003a** — GDM01/02 ordinary prompt entry; GDM03/04/08/09 recipient, refusal and Escape-return proofs.
- **003ba** — GDM05 fresh Parent/standard entry and DESK01 no-prompt desktop.

## Read only this context

Read the [search/sign-in contract](../E2E-Building-Blocks.md#search-and-standard-sign-in-contracts), [credential boundary](../../../tests/e2e/README.md#credential-staging-and-password-capture-boundary), desktop/prompt callables in [accessible_ui.py](../../../tests/e2e/accessible_ui.py), and the entry stages of [desktop_session.py](../../../tests/e2e/desktop_session.py).
The fresh no-prompt entry plans are in [fresh_desktop.py](../../../tests/e2e/fresh_desktop.py), with fixed worker input in [onpc_fresh_desktop.pm](../../../tests/integration/graphical_smoke/lib/onpc_fresh_desktop.pm) and separate-attempt qualification in [check_e2e_fresh_desktop.py](../../../tests/integration/check_e2e_fresh_desktop.py).
Read the affected safety tests and named source callables, not predecessor
briefs or unrelated providers. Current route qualification comes from the
catalogue; a checked historical task does not override it.

## Implementation

Reuse the qualified Parent and standard fresh no-prompt bindings without replaying their secret input. Add only the gcr provider's normal Cancel action and observed disappearance. Declare a reproducible prepared entry state for a real keyring prompt before running; absent-prompt mocks cannot qualify Cancel. This is preparation for the retained search and session consumers, with no keyring password access. Keep GDM submission, desktop observation and gcr cancellation as separately tested leaves within this slice.

## Live VM acceptance

Qualify fresh Parent and standard-account entry in separate attempts, including wrong-recipient refusal and intended public desktop observation. In the real gcr-prompt attempt, prove its owner/dialog and masked-field focus, Cancel once, observe disappearance and resume the interrupted observation without replaying input. Independently supplied desktop entry must also work. Tests reject replacement/queued prompts, unknown modals, incomplete absence, lost focus and uncertain action. Require private capture reconciliation, public results and cleanup.

Implement and register this planned fixed qualification before invoking it:

```sh
tools/run-tests integration check_e2e_desktop_keyring
```

Use the existing guarded envelope. Pass applicable cleanup-safety checks in
isolation before live execution; require independent valid entry, wrong-entry
refusal, sanitized evidence and owned cleanup. A new selector needs its
argument-free launcher and cleanup coverage. Host tests alone cannot close this row.

## Close out

Follow the [master close-out](../E2E-Execution-Plan.md#completion-and-document-cleanup).
Record only the proven callable/scope and existing artifact pointer, check
**003b** after its acceptance and cleanup, and advance the master's sole
pointer to the following unchecked row. An unmet requirement keeps this task
current. Delete this brief after enduring context is in the catalogue/source.
