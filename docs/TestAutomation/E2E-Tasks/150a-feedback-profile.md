# 150a — Prepare network-free feedback checks

Use the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [UI acceptance](../E2E-Execution-Contracts.md#ui-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **UI obligation; synthetic feedback inputs using the existing
network-free component previews** for the sending allocations below.

Required tasks (queue IDs): **Baseline**.

Reuse existing component coverage; installed draft/attachment/collection
qualifications are not host UI acceptance gates. No real service profile,
dedicated recipient, external-send authorization, VM Internet isolation or public
cooldown trigger is required.

## Implementation

Bootstrap this task in a normal repository coding-agent session using the
prompt `Implement task 150a in docs/TestAutomation/E2E-Execution-PlanB.md`.
Read the queue and this brief directly; do not invoke the current
`tools/write-e2e` to start this first host-only change. Its unconditional VM
selection and supervisor admission happen before the implementing session and
cannot be repaired from a session that never starts. No VM configuration,
preparation, observation or execution is needed for this bootstrap.

Complete this task's host implementation/checks and normal documentation
close-out in that session. Start or resume the updated launcher only afterwards;
preserve any existing checkpoint and its ownership/close-out guards through the
normal restart route. This is a one-time implementation route, not a request for
a developer choice, another launcher or permission to fake installed evidence.

First make the existing write-e2e launcher honor the explicit **UI obligation**
queue marker through its normal host-only branch. This is missing implementation,
not an already-qualified route: `session_prompt` currently requires VM acceptance,
`accept_result` permits host-only completion only for historical task 192, queue
parsing drops scope, and launch selection constructs a VM selection unconditionally.
Use the existing [launcher](../../../tools/write_e2e.py),
[queue parser](../../../tools/execution_plan.py) and
[selection owner](../../../tools/vm_selection.py); do not add another launcher
or a blanket no-VM bypass.

Carry the validated task marker into prompt, selection and completion handling.
Marked UI tasks, including this task, must need no VM configuration/selection,
package preparation, VM operations or installed acceptance evidence. Permit
`task_complete` with `live_result=not_run` only after their focused host acceptance,
normal checks, owned cleanup and queue close-out. Preserve task 192, all ordinary
installed-task requirements, dependency/order/ownership checks, incomplete-result
and outstanding-failure guards. Keep the existing response/check schema where
already sufficient. Inspect existing launcher/parser coverage and
[write-e2e fixtures](../../../tests/support/write_e2e_fixtures.py) first; cover the
affected host/installed distinction in the existing unit owner. No test-tool UI
test or new framework. Do not claim an orphaned helper is executable coverage.

Then reconcile allocation metadata for former cases **156, 157, 213, 216, 218,
219, 220 and 221** with their UI owners. Keep IDs as allocation references and
retain every finite assertion; do not mark installed readiness, register host
checks as E2E executables or claim live-delivery credit. Existing source/inventory
consistency checks must agree with that allocation before later UI tasks run.
This brief records future implementation; the present review changes docs only.

Developer decision: routine feedback sending checks use the existing working
mocks. Reuse [Parent component preview](../../../tests/ui/parent_component_preview.py)
and [request component preview](../../../tests/ui/request_component_preview.py).
Both replace `feedback_transport.requests.Session` with a fake HTTP session;
the actual editor, multipart encoder, submission/retry controller, result
handling and dialog handlers remain production code. Keep that replacement
unconditional for these previews so no test Send can reach the network. Extend
only the existing test-local response/release controls needed for missing app
behavior; never change the shipped transport or introduce an endpoint override.

Use the existing [Parent feedback owner](../../../tests/ui/test_parent_feedback.py)
and [error-report owner](../../../tests/ui/test_error_feedback.py), with their
shared [feedback helpers](../../../tests/support/feedback.py) and
[request helpers](../../../tests/support/request_form.py). Existing outcome,
confirmation and report callback checks supply their delivered coverage; do not
repeat them under new tests or build a new framework. Pure backoff, expiry,
response and immutable-submission assertions stay in the existing
[transport unit owner](../../../tests/unit/test_feedback_transport.py).

Prepare finite synthetic drafts/files for allocations **150, 151, 152, 153,
258, 262, 263, 189k, 255, 190a, 190o, 260, 190b, 190k and 261**. Reuse declared
text/file fixtures, an empty reply for ordinary anonymous success and
`first@example.invalid` for the reply-note branch. Diagnostic data comes from
the existing test-local collector. No recipient or inbox is contacted. Preserve
one explicit Send per declared submission; retries use its original frozen
content/identity. Do not replay uncertain input.

Host checks observe actual dialog closure and callback ordering. Request
previews record `close_overlay`/`logout` callbacks; those records do not prove
an installed child desktop or GDM destination. Installed return behavior remains
with the public [request-exit owners](../E2E-Building-Blocks.md#kiosk-child-overlay-and-the-shared-request-form).

This is a **UI obligation** under the developer's mock-sending decision.
Production code and endpoint remain unchanged. Tests must make no real network request.
Numeric case IDs are allocation references only: no installed E2E pass,
real-service acceptance or delivery credit. A real-send check is separate and
optional, never a prerequisite here.

## UI acceptance

Inspect existing coverage first; fill only missing product assertions in the
named owner and reuse its shared Application UI API helpers. Do not add a
parallel fixture, mock server, portal, inbox or production mock switch.
For the launcher change, discover its actual existing test owner before choosing
the narrow affected unit selection; `tests/unit/test_test_launchers.py` is the
existing launcher category owner, not proof that it currently covers write-e2e.
Do not invent a missing test filename or run the whole host category.

Run the focused maintained component selection after implementation:

```sh
tools/run-tests ui 'tests/ui/test_parent_feedback.py' 'tests/ui/test_error_feedback.py' --timeout 1800s
```

Reuse existing deterministic transport timing/error coverage in
[the transport unit owner](../../../tests/unit/test_feedback_transport.py);
run its affected selection only if transport test coverage changes. This
brief's documentation update executes no tests or acceptance.
