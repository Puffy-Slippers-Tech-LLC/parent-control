# 189k — Check Send without logs with the fake sender

Use the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [UI acceptance](../E2E-Execution-Contracts.md#ui-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **UI obligation; FEED11 explicit Send without logs and FEED09/14 kiosk
result**, allocated to case 213.

Required tasks (queue IDs):

- **150** — existing mock-response sending/result path.

## Implementation and expected results

Use the request component preview's existing
`service-failure-logs-unavailable` collector fixture in kiosk mode. A public
installed collection-failure trigger and task 188k are not gates for this local
behavior. Independently read terminal collection failure before recovery/send;
Internet loss is not the collection-failure mechanism.

Extend the existing unavailable-log report check only for the explicit
`feedback-send-without-logs` action; its current remove-logs then Send path
already covers preserving edited content. Read usable editing/Close and kiosk
restrictions: no Add files, download, attachment shortcut or external Privacy
link; in-app Privacy remains readable. Activate Send without logs once on the
valid edited draft. The real handler must omit diagnostics in the encoded
request, preserve customer text, and show owned thanks on the fake success
response. A separate Retry recovery history is not required.

Require report exit still pending until manual thanks dismissal, then report
closure and exactly one kiosk `logout` callback. Failed sending preserves the
draft and must never count as success.

The preview records the real report-close flow's `close_overlay` or `logout`
callback. Assert that callback and its ordering, not an installed desktop/GDM
result. Installed destinations remain with the public
[request-exit owners](../E2E-Building-Blocks.md#kiosk-child-overlay-and-the-shared-request-form).

This is a **UI obligation** under the developer's mock-sending decision.
Reuse [150a's component boundary](150a-feedback-profile.md); production code
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
