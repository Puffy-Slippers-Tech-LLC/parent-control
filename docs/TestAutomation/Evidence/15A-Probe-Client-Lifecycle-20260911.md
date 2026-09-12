# 15A independently owned probe client — 2026-09-11

Development/host scope; actual settings `gpt-6-astra/high`, Standard. The
earliest ready unchecked entry was and remains Task 15A; no earlier task was
bypassed. All-task guarded VM clearance persists. No Task 20 R1 recovery work
was performed or charged; its retained ledger is unchanged.

## Result and qualification boundary

Reuse the [bounded transport/recovery contract](../../SystemDesign/Applications.md#bounded-probe-transport-and-open-limits)
and existing finite `ExecutionProbe` calls. The missing capability was a bus
client whose lifetime could be ended without disconnecting the broker, including
when construction or closure completes after the caller's deadline.

`execution_probe.ProbeBusClient` owns one new Gio connection, a private main
context and retained asynchronous completion state. Open/close waits have finite
deadlines and request cancellation on timeout/interruption. Late successful
construction is retained for closure; a pending close is collected before any
retry. It refuses reuse and overlapping operations, never dispatches the default
broker context, and rejects non-Unix, fallback and autolaunch transports. Safe
logs omit addresses and raw errors. Cancellation is never cleanup proof.

The result is **connection lifecycle qualification**, not complete finite
settlement of a systemd request. The helper is deliberately still separate from
`ExecutionProbe`, which continues to use its supplied connection. This slice's
scope stopped at the independently testable Gio boundary because cancellation
does not guarantee callback completion. The original proposed systemd
dispatch-before/during/after-close check remains the next integration boundary;
the late **connection-constructor** arrival tests do not substitute for it.

Public sources checked:

- [Gio asynchronous construction](https://docs.gtk.org/gio/ctor.DBusConnection.new_for_address_sync.html)
  documents independent client construction and points to its asynchronous API.
- [Gio close](https://docs.gtk.org/gio/method.DBusConnection.close.html)
  documents asynchronous completion in the caller's thread-default context,
  failure on an already closed connection, and no automatic message flush.
- [GLib 2.86.0 close implementation](https://github.com/GNOME/glib/blob/2.86.0/gio/gdbusconnection.c)
  shows the synchronous wrapper waiting for the async callback. Merely adding a
  cancellation timer to that wrapper would not establish our finite wait and
  retained-completion contract. This tag inspection is not a claim about the
  installed guest's dependency version. The public address-resolver page timed
  out; address resolution was not implemented or qualified here.

## Verification

Final source selections:

```sh
tools/run-unit-tests tests/unit/test_probe_bus_client_cleanup_safety.py tests/unit/test_execution_probe_cleanup_safety.py tests/unit/test_execution_policy.py tests/unit/test_adapters.py -q
tools/run-tests component tests/component/test_probe_bus_client.py -q
```

- **83 tests and 24 subtests passed** in the final focused unit selection,
  including 19 new lifecycle cases and the existing 37 probe cases.
- The final component launcher first passed **769 isolated cleanup-prerequisite
  tests and 3 subtests**, then **3 real private-bus/socket cases**. It ran via the
  approved escalation route for local sockets; no approval or Polkit denial.
- `test_owned_connection_disappears_without_closing_observer` observed separate
  sender identities, disappearance of the closed sender and continued observer
  access. `test_connection_refusal_finishes_without_exposing_address` exercised
  real connection failure. `test_stalled_authentication_is_cancelled_and_socket_is_closed`
  observed a bounded failed open, collected completion and actual socket EOF.
- Lifecycle regressions cover late construction before/during/after a close
  timeout, never-completing operations, cancellation, lost/failed closure,
  interruption during both dispatch and waits, non-replay, concurrency,
  forbidden transports and isolation from the broker's default context.
- The first unit run failed **10 cases** (39 passed): the test double's idle
  callback incorrectly required a user-data argument. Fixing its zero-argument
  signature yielded 49 passes. Later interruption/transport/context additions
  passed in the final selection above. This was a test-double defect; it did
  not exercise a host systemd unit or leave a live client. An intermediate
  component run passed 762 prerequisite tests/3 subtests and all 3 cases before
  the final additions; final evidence supersedes that source scope.

No build, VM/systemd activation attempt, full `make check` or task acceptance
run occurred. Activation attempts remain two. No installed dependency identity,
original-job binding, generation witness or policy matrix acceptance is claimed.
Changed-document validation passed: 171 local links across five documents,
with none missing; scoped `git diff --check` passed.

## Cleanup and next action

All commands exited and their results were collected. Private-bus fixture
teardown completed; test-owned listener/accepted sockets reached closure, all
client owners reported completed cleanup, idle sources were destroyed and the
test executor joined. Doubles retaining simulated unfinished callbacks are not
live leftovers. No VM, lease, systemd probe, screenshot or independently running
worker was started. No recovery or denial remains.

Integrate `ProbeBusClient` into `ExecutionProbe` creation/release without closing
the broker's shared observer or losing immutable recovery coordinates. Resolve
the trusted system-bus address through supported APIs, retaining the single
Unix transport guard. Prove delayed systemd dispatch before/during/after sender
disconnect and distinguish client closure, manager reference release and actual
process cleanup. Missing terminal evidence and stuck processes must still fail
closed. Then bind the original job and qualify real success/failure/cleanup with
`record_execution_backend` under the guarded installed runner. Existing all-task
VM clearance requires no further coordination confirmation when that boundary
is ready.

Next settings: `gpt-6-astra/high`, Standard. The lifecycle now has meaningful
checks; its integration still crosses unresolved sender/reference ownership and
systemd job identity, so this is not yet settled Sol implementation.
