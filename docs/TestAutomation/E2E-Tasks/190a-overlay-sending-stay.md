# 190a — Check overlay report retry and recovery

Use the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [UI acceptance](../E2E-Execution-Contracts.md#ui-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **UI obligation; FEED09 child-overlay retry/recovery and FEED17 pending
Stop action**. Task 190o owns the separate direct-stop result.

Required tasks (queue IDs):

- **150** — existing fake HTTP Session and submission/result handling.

## Implementation and expected results

Use the existing request preview report in child-overlay mode and extend its fake
HTTP Session only with finite retry-then-success response/release controls.
No installed request-error trigger, VM Internet isolation or real network is needed.
Keep the actual encoder, retry controller and result/dialog handlers.

Send one synthetic report, independently observe public retry and the enabled
Stop sending and close action while leaving it untouched. Release the same
submission's successful mock response within its normal retry lifetime. Require
owned thanks and no `close_overlay` callback before manual dismissal, then
report closure and exactly one callback. No second Send or Close while retrying;
no warning/stay dialog belongs to this flow. Reuse existing success/callback
coverage; fill only the missing retry/recovery behavior. Pure timing/backoff and
frozen-identity combinations stay in the transport unit owner.

The preview records the real report-close flow's `close_overlay` or `logout`
callback. Assert that callback and its ordering, not an installed desktop/GDM
result. Installed destinations remain with the public
[request-exit owners](../E2E-Building-Blocks.md#kiosk-child-overlay-and-the-shared-request-form).

This is a **UI obligation** under the developer's mock-sending decision.
Reuse the [component boundary](../UI-and-E2E-Coverage.md#feedback-sending-allocation); production code
and endpoint remain unchanged. Tests must make no real network request.
Numeric case IDs are allocation references only: no installed E2E pass,
real-service acceptance or delivery credit. A real-send check is separate and
optional, never a prerequisite here.

## UI acceptance

Reuse [the existing error-report owner](../../../tests/ui/test_error_feedback.py)
and [request component preview](../../../tests/ui/request_component_preview.py).
Inspect delivered coverage first and add only missing product assertions,
through the shared Application UI API helpers. Keep actual editor, encoder,
retry/result and dialog handlers; extend only the existing fake HTTP Session's
finite response/release controls where needed. No parallel framework or server.

```sh
tools/run-tests ui 'tests/ui/test_error_feedback.py' --timeout 1800s
```

Pure backoff, expiry, response and frozen-submission checks remain in the existing
[transport unit owner](../../../tests/unit/test_feedback_transport.py). Run its
affected selection only if that coverage changes. Documentation edits alone
execute no tests or acceptance.
