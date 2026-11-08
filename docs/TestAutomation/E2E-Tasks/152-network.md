# 152 — Check feedback recovers after a retryable response

Use the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [UI acceptance](../E2E-Execution-Contracts.md#ui-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **UI obligation; FEED09 Parent retry/recovery** using the existing fake
HTTP Session, without changing host or guest connectivity.

Required tasks (current queue IDs):

- **150** — Parent mock-response submission and result handling.

## Implementation and expected results

Reuse the Parent component preview's fake HTTP Session. Add only the missing
finite retry-then-success response/release control there, exercising the actual
encoder and retry controller. Do not replace `submit` with a success stub or add
a server/network harness. Existing transport unit checks own exact backoff,
expiry and frozen identity; no long retry-window sleep or product timing change.

Send one synthetic report; with empty reply, explicitly confirm Send
Anonymously. Independently observe public retry while the dialog stays open,
release the same mock submission's next successful response and require its
actual success/thanks result. No second explicit Send. Check meaningful UI
sensitivity and preserved frozen input through the existing owner, without
repeating Privacy/attachment/collection matrices.

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
