# 190k — Stop a station report

Use the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [UI acceptance](../E2E-Execution-Contracts.md#ui-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **UI obligation; FEED09 retry and FEED17/18 kiosk direct Stop**,
allocated to case 219.

Required tasks (queue IDs):

- **190b** — kiosk component retry-entry and pending Stop observation.

## Implementation and expected results

Reuse task 190b's fake HTTP Session controls and actual request report in
kiosk mode. With one synthetic submission pending, independently observe
retry and its explicit Stop sending and close action. Activate Stop once and
require report disappearance, cancellation of pending retries and exactly one
`logout` callback. The normal Stop action is direct: no confirmation,
warning or stay response. A later released fake response must not revive the
closed report or repeat its callback. No real Internet isolation/restoration.

Keep the production close/cancellation path and use the existing preview
ownership/release cleanup. Do not replace Stop with a private callback or infer
that stopping recalls an already accepted request. Case 219's allocation
reuses this assertion set rather than adding another complete copy.

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
