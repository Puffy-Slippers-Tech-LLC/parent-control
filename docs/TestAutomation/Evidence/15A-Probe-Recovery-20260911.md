# 15A retained probe recovery — 2026-09-11

Development host; actual settings `gpt-6-astra/high`, Standard. Task 20's
source-preservation deferral was rechecked at entry and handoff: no new writer
completion/window evidence was available. No unchanged Task 20 experiment ran.
All-task guarded VM clearance persists; this is implementation readiness work.

## Verified result and limits

The [owning transport contract](../../SystemDesign/Applications.md#bounded-probe-transport-and-open-limits)
now includes `ExecutionProbe.pending` and `recover()`. The existing finite Gio
transport, pinned terminal evidence and sender-only reference release are reused.
The missing capability was cleanup after the original call returned: a delayed
create could acquire its client reference after the original release attempt.

One retained adapter now serializes run/recovery without blocking competing
threads, refuses another creation while cleanup is pending, and retains recovery
coordinates before dispatch and interrupted release. Bounded recovery collects
a unit that appears later without replaying creation or issuing process signals.
Lost release replies are recoverable through the public current-reference
absence errors followed by confirmed collection. Recovery preserves the original
failure; it does not retroactively promote an execution whose cleanup failed.

This closes eventual late-appearance recovery, **not finite settlement of a
request that remains indefinitely absent**. Such an attempt stays pending and
blocks another create. The caller must retain the same adapter and live
connection; there is no connection-wide registry or broker scheduler. The adapter
remains dormant. Original-job/invocation binding, dedicated connection lifetime,
installed qualification, generation receipts, rollback/removal and the remaining
native/Snap/Flatpak acceptance are unfinished.

## Supported-source findings and next discriminator

Direct tagged upstream **v259** reads, not guest-version qualification:

- [D-Bus error definitions](https://github.com/systemd/systemd/blob/v259/src/libsystemd/sd-bus/bus-common-errors.h)
  define `org.freedesktop.systemd1.NotReferenced`. The prior double's
  `UnitNotReferenced` spelling was incorrect and is corrected.
- [Unit reference handling](https://github.com/systemd/systemd/blob/v259/src/core/dbus-unit.c)
  removes the sending client's reference and queues collection when tracked
  clients disappear. It does not cancel pending creation or stop a process.
- [Tracking implementation](https://github.com/systemd/systemd/blob/v259/src/libsystemd/sd-bus/bus-track.c)
  subscribes to name disappearance, then checks current name credentials while
  adding a reference. [Transient creation](https://github.com/systemd/systemd/blob/v259/src/core/dbus-manager.c)
  adds the requested reference before continuing to load/queue the service.
  These support investigating an independently owned short-lived bus client:
  closing it could bound reference lifetime without disconnecting the broker.
  This is a candidate, not a complete cancellation or process-cleanup proof.

Web retrieval of the tracking source returned cache errors and web symbol
searches missed definitions; direct quoted public `curl` reads succeeded for
all relevant sources. No approval or Polkit denial occurred.

The next bounded result should establish cancellable private-client connection
creation/closure and distinguish dispatch before, during and after disconnect.
Keep process completion separate from reference lifetime: a stuck execution
must still report uncertain cleanup. Do not replace these guards with a name
lookup, sleep, disconnect of the broker's shared bus, or repeated creation.
Only then address original-job binding and qualify real success/failure/cleanup
with installed dependency capture through the existing guarded runner.

## Verification and cleanup

Final focused selection:

```sh
tools/run-unit-tests tests/unit/test_execution_probe_cleanup_safety.py tests/unit/test_execution_policy.py tests/unit/test_adapters.py -q
```

**64 tests and 24 subtests passed**, including 37 probe cases (12 added here).
An earlier 35-case probe selection passed before the final interruption and
foreign-unit cases were added. No test failed. New discriminators include
`test_delayed_dispatch_is_recovered_without_another_create`,
`test_absent_delayed_create_stays_pending_through_bounded_recovery`,
`test_create_arriving_during_recovery_is_observed_and_released`,
`test_lost_unref_reply_recovers_current_absence_without_promoting_success`,
`test_concurrent_operations_refuse_without_blocking_or_extra_dispatch`, and
the interrupted-dispatch/release and delayed-foreign-unit tests in
[the cleanup-safety module](../../../tests/unit/test_execution_probe_cleanup_safety.py).

Tests use doubles and a joined, session-owned thread executor. No host/guest
systemd unit, VM, lease, worker, screenshot or process fixture was started.
All commands exited and results were collected; simulated uncertain cleanup
does not represent a live leftover. No recovery or denied action remains.
Scoped whitespace and changed-document link checks are recorded at handoff.
Existing unrelated edits were preserved. No build, full `make check` or live
qualification ran; activation attempts remain two and Task 20 attempts twelve.
