# 15A retained creation reply — 2026-09-11

Task 15A remains the earliest ready unchecked entry; none bypassed. Actual
settings `gpt-6-astra/high`, Standard. All-task guarded VM clearance persists.
No Task 20 R1 recovery work or charge. Earlier uncommitted work was preserved.

## Finding and bounded result

The existing synchronous creation timeout discards the eventual reply, losing
its job identity even while the owned sender preserves the unit pin. Closing
that sender cannot settle dispatch and can discard terminal evidence. Reuse
`ProbeBusClient`'s private context and extend it with retained asynchronous
creation, rather than introduce another connection, worker or cleanup route.

The public [Gio call contract](https://docs.gtk.org/gio/method.DBusConnection.call.html)
supports a no-timeout asynchronous request and delivery on the initiating
thread's default context. `start_create` submits exactly one fixed canary to
the supplied unique manager; `poll_create` bounds each local wait without
cancellation. The callback stores an immutable job/collision/uncertain result,
excluding raw error payloads. While the callback is pending, close refuses
without making the sender unusable. Interrupted dispatch and polling preserve
the callback. This is an extension to the existing helper, **not integrated
into ExecutionProbe yet**. Its current synchronous behavior is unchanged.

The [owning contract's outcome table](../../SystemDesign/Applications.md#bounded-probe-transport-and-open-limits)
defines the next integration: retain coordinates and callback during timeout,
copy the job before release, retain terminal evidence independently, preserve
failed outcomes, and keep uncertain errors pending under existing cleanup
gates. Callback completion alone is never a process-cleanup receipt. Unexpected
sender loss and permanently missing replies can still leave cleanup uncertain.
No automatic disconnection experiment or finite-cleanup guarantee is claimed.

## Verification and failures

Selections:

```sh
tools/run-unit-tests tests/unit/test_probe_bus_client_cleanup_safety.py tests/unit/test_execution_probe_cleanup_safety.py -q
tools/run-tests component tests/component/test_probe_bus_client.py -q
```

- Focused unit checks: **75 passed**. New lifecycle IDs:
  `test_late_create_reply_survives_deadline_without_disconnect_or_replay`
  (success/collision/error), `test_interrupted_create_keeps_reply_and_sender_owned`
  (dispatch/poll), and
  `test_create_poll_refuses_overlap_and_does_not_dispatch_default_context`.
- First component attempt: isolated prerequisites **788 passed / 3 subtests**;
  components **3 failed / 6 passed**. The new tests used deprecated
  `register_object`, rejected by warnings-as-errors before request submission.
  Replaced it with the broker's existing supported
  [register_object_with_closures2](https://docs.gtk.org/gio/method.DBusConnection.register_object_with_closures2.html)
  and put registration inside the cleanup guard. No warning suppression.
- Corrected component attempt: prerequisites **788 passed / 3 subtests**;
  components **9 passed**. New
  `test_late_create_reply_is_retained_on_real_owned_connection` covers all three
  reply types with a held real D-Bus invocation. It proves reply delivery after
  a local deadline, sender survival during close refusal, subsequent sender
  disappearance, observer survival and payload-free logs. The fake manager
  launches no unit and establishes no systemd dispatch/GC semantics.
- One exploratory source search named a nonexistent test module; corrected by
  searching the literal component directory. No approval or Polkit denial.

Tested SHA-256 inputs:

| Input | SHA-256 |
| --- | --- |
| `broker/oh_no_parent_control/execution_probe.py` | `192ab629ccc806f47a2c093f48583c195ae77c60b9b6428b6713390b83d76ae8` |
| `tests/unit/test_probe_bus_client_cleanup_safety.py` | `abbb7ff40bb0c444af968c0cd436506d145932932ec45ffcf3d1b25ff0e1d2f3` |
| `tests/component/test_probe_bus_client.py` | `998b73b54d3a7c29e6ae8f4f98623a9abaaa167a778b256b8b5193f001dc0ab7` |

All commands exited and results were collected. The failed test subprocess
exited and its fixture-owned private buses were torn down; the corrected tests
also explicitly close their connections and unregister objects. Joined unit
test executors and GLib sources were cleaned up. No host system-bus probe, VM,
lease, screenshot or separate worker remains. No logs were modified or deleted.
Scoped whitespace and changed-document link checks passed. No build, full
`make check`, installed run or Task 15A acceptance is claimed. Activation
attempt count remains two; native/Snap/Flatpak and cross-user acceptance remain
unfinished.

Next: integrate retained replies into `ExecutionProbe.run/recover` using the
published table and focused cleanup regressions. Next settings
`gpt-5.6-sol/high`, Standard: the bounded integration contract and transport
checks are now established. Original-job/invocation binding and live systemd
qualification are later unresolved boundaries requiring reassessment.
