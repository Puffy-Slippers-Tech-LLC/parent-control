# F28 — Integrate Fedora recorded serial preparation

Acceptance: installed
Targets: onpc-Fedora44
Requires: F27

Apply the master's [mandate routes](../Fixture-Execution-Plan.md#applicable-mandates)
and [close-out contract](../Fixture-Execution-Plan.md#close-out) throughout this task.

## Scope and implementation

Use the [runner matrix](../Fixture-Design.md#runner-acceptance-matrix) and its
[source-backed alias map](../Fixture-Design.md#source-backed-consumer-and-alias-disposition).
Qualify F27's `serial_harness.record_serial_journey` preparation under
`execution.ScenarioContext` and its recorder. Reuse its helper, selector and
history; change only target gates and evidenced Fedora differences. Read complete
affected functions and necessary worker/recorder/credential/getty/provisioning
callers. Preserve setup/start ordering, private seals,
HAR09/HAR10 stage completion, durable observations before replies, boot continuity,
logout/session absence and owned worker shutdown. This is a distinct preparation
caller from standalone Smoke.
Qualify the same Smoke readiness step and recorder input binding on Fedora;
keep recorder-specific setup/start ordering and cleanup in this caller.

Apply [shared runner integration and qualification](../Fixture-Design.md#runner-integration-and-qualification).
Preserve enforcing SELinux, exact native admissions and labels. Renew Ubuntu proof
only where invalidated under the design's [validation rule](../Fixture-Design.md#validation-reuse-and-invalidation).

## Acceptance and cleanup

Confirm F27's existing `check_fixture_recorded_serial` binding lists Fedora before invoking:

```sh
tools/run-tests integration --vm 'onpc-Fedora44' check_fixture_recorded_serial
```

Invoke the actual recorded harness preparation once through shared readiness and
harmless native use. Stop before serial worker input or product assertions.
Host composition preserves serial/secret guards; recorder provenance binds the
same immutable fixture input. Finish recorder cleanup as well as VM/transport.
Reuse F27/shared recording and readiness safety proof. Do not requalify the
complete recorder or run HAR09/HAR10, login/logout or product scenarios for
fixture acceptance.
Complete shared qualification and the master's close-out.
