# 150a — Prepare the reviewed feedback submission profile

Estimate: 30–50 minutes of focused implementation and validation; not a stop
timer. Follow the [master execution contract](../E2E-Execution-Plan.md#execute-one-task).

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
isolation first. Use the shared watchvm observation and intention transport.
Require independent valid entry, wrong-entry refusal, sanitized results and owned
cleanup; host tests alone do not close this row.

```sh
tools/run-tests integration check_e2e_feedback_profile
```

## Close out

Follow the [master close-out](../E2E-Execution-Plan.md#completion-and-document-cleanup).
Record the callable and exact qualified scope in the
[catalogue](../E2E-Building-Blocks.md), check **150a** only after acceptance and
cleanup, advance to the following unchecked row, and delete this brief after
enduring context is maintained. The complete scenario stays in its own task.
