# 150 — Check feedback success with the fake sender

Use the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [UI acceptance](../E2E-Execution-Contracts.md#ui-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **UI obligation; FEED11, FEED09 sending/success and FEED14 Parent
feedback** through the existing component preview. Allocation consumer: case 156.

Required tasks (current queue IDs):

- **150a** — existing component mocks and finite synthetic input allocation.

## Implementation and expected results

Reuse the Parent preview's fake HTTP Session and actual editor/encoder/retry and
result handlers. The existing `test_feedback_submission_outcomes` already covers
success/error responses, Add Email Address, anonymous confirmation and thanks;
retain that coverage and fill only missing app behavior.

With an empty optional reply, select Send once, independently require the owned
anonymous confirmation and no submission yet, then choose Send Anonymously
once. Observe the mock response through the real submission/result path and
owned thanks without a reply-follow-up note. Dismiss normally; opening the
confirmation alone must never send. Reuse existing valid-reply and confirmation
revalidation checks. An idle editable draft is not success evidence. Case 156's
allocation owns complete cleared-draft readback; do not duplicate its history.

This is a **UI obligation** under the developer's mock-sending decision.
Reuse the [component boundary](../UI-and-E2E-Coverage.md#feedback-sending-allocation); production code
and endpoint remain unchanged. Tests must make no real network request.
Numeric case IDs are allocation references only: no installed E2E pass,
real-service acceptance or delivery credit. A real-send check is separate and
optional, never a prerequisite here.

## UI acceptance

Inspect existing coverage first; fill only missing product assertions in the
named owner and reuse its shared Application UI API helpers. Do not add a
parallel fixture, mock server, portal, inbox or production mock switch.
Run the focused maintained selection after implementation:

```sh
tools/run-tests ui 'tests/ui/test_parent_feedback.py' --timeout 1800s
```

Reuse existing deterministic transport timing/error coverage in
[the transport unit owner](../../../tests/unit/test_feedback_transport.py);
run its affected selection only if transport test coverage changes. This
brief's documentation update executes no tests or acceptance.
