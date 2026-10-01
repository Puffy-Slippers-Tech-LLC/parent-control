# 150a — Prepare the reviewed feedback submission profile

Apply the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and the task-specific scope and acceptance below.

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **Concrete synthetic reports, recipient and authorization scope for FEED11 consumers**.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **038** — FEED06, FEED07, FEED12, FEED13.
- **031a** — FEED09 collection trace.
- **030** — FEED05; FEED10 dialog persistence.
- **052c** — TIME03.

## Implementation

Prepare the supported real feedback-service profile, dedicated recipient,
synthetic drafts/attachments and redacted Privacy projections required by the
[feedback recipes](../E2E-Scenario-Recipes.md#sending-background-completion-and-report-exits).
Enumerate the exact capability qualifications and numeric scenario submissions
that the authorization will cover, with bounded counts and the stop/retry cases.
Reuse an existing supported service/recipient configuration. This task does not
provision mailboxes, set up SMTP/DNS, build a test portal or qualify service
administration. If that profile is unavailable, record the exact prerequisite.
Later acceptance stops at the app's real response and declared exit; delivery
receipts and inbox contents are not E2E prerequisites.
Record only private profile references and nonsecret scope in maintained fixture
metadata; never create a parallel evidence document or edit the portal.

## Live VM acceptance

Open the actual Parent feedback draft on the guarded VM and qualify the reviewed
content, attachment and Privacy readbacks without Send. Produce concrete reviewable
inputs first. Reuse explicit sending authorization that covers this exact profile;
otherwise request it as the final prerequisite and keep this task current. Do not
send here. After authorization is recorded, later tasks reuse it without renewed
permission unless the reviewed content, recipient or submission scope changes.

Implement and register the following fixed qualification in the existing guarded
envelope before invoking it. Pass the affected cleanup/ownership regressions in
isolation first. Use the shared watch observation and intention transport.
Require independent valid entry, wrong-entry refusal, sanitized results and owned
cleanup; host tests alone do not close this row.

```sh
tools/run-tests integration check_e2e_feedback_profile
```

## Close out

Follow [completion and document cleanup](../E2E-Execution-Contracts.md#completion-and-document-cleanup)
after this task's acceptance and owned cleanup pass.
