# 150 — Submit one authorized synthetic report and read success

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **FEED11, FEED09 sending/success and FEED14 Parent feedback**. First scheduled consumer: [E2E-032, case 156](../E2E-Scenario-Recipes.md#e2e-032).
Read the named [block contracts](../E2E-Building-Blocks.md#about-feedback-and-customer-selected-attachments) and only the selected consumer's recipe.

Authorization is supplied by task 150a's exact reviewed profile. A changed or
expired authorization remains a blocker; do not request renewed permission for
an unchanged covered submission.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **150a** — Concrete synthetic reports, recipient and authorization scope for FEED11 consumers.

## Implementation

Reuse the concrete reviewed profile and submission authorization from task 150a.
Use an empty optional reply address for this Parent ordinary-feedback binding.
Compose FEED03/Privacy observations, one Send, FEED09 sending/success and FEED14
dismissal. Qualify these result projections through the supported real service
and dedicated recipient. Do not expand content, recipient or submission counts.

Source gap: `AccessibleUI.feedback_snapshot` / `feedback_state_operation` read
editable, idle drafts and do not implement sending, retry or success-dialog
projections. Add the finite public submission/readback operations to the shared
facade and observation registration; do not reuse an idle snapshot as success.
Bind `feedback-send` once, `feedback-status`, and the owned
`feedback-success-dialog`, `feedback-success-text` and `feedback-success-close`.
The actual `_send` → `feedback_transport.submit` → `_submission_done` /
`_success_closed` handlers in `common/oh_no_parent_control_ui/feedback.py` own
submission, clearing and exit. Runtime authorization and uncertain-input guards
remain in the shared operation; unchanged draft/chooser qualifications are reused.

## Live VM acceptance

With authorized service configuration, submit once on the VM, observe the actual app response, dismiss confirmation and reopen feedback to observe clearing. No provider receipt probe or automatic repeat send. Planning is not sending authorization.

Planned qualification selector (not registered; implement before use):

```sh
tools/run-tests integration check_e2e_feedback_send
```
