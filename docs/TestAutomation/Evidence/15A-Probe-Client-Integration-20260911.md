# 15A owned probe client integration — 2026-09-11

Development/host scope; actual settings `gpt-6-astra/high`, Standard. Task 15A
was and remains the earliest ready unchecked entry; none was bypassed. All-task
guarded VM clearance persists. No Task 20 R1 recovery was performed or charged.
The existing uncommitted lifecycle implementation and documentation were
preserved and extended; unrelated work was not edited.

## Result and qualification boundary

Reuse the [owned lifecycle](15A-Probe-Client-Lifecycle-20260911.md) and
[bounded transport/recovery contract](../../SystemDesign/Applications.md#bounded-probe-transport-and-open-limits).
The missing integration was separation of the observer from the sender and
retention of client cleanup state alongside unit recovery coordinates.

`ExecutionProbe` now owns a fresh sender for each settled run. Only that sender
creates/releases units; all evidence reads use the supplied observer. The
public SYSTEM address resolver and the existing Unix transport guard select
the sending bus; matching `GetId` replies prevent dispatch on a different bus.
No missing-sender path falls back to observer mutation or closes that observer.

Cleanup requires unit settlement and client closure. Failed/interrupted close
retains the adapter and original evidence; close-only recovery does not query a
collected unit or replay creation. Pre-dispatch failure also retains pending
client cleanup. Recovery preserves failure, including a previously executed
canary whose cleanup failed. The result exposes a separate `client_closed` flag.

Ambiguous dispatch keeps the sender available to release a late reference.
It does not close that client to assert finite dispatch settlement: sender
disappearance can also remove the reference preserving terminal evidence.
This slice settles lifecycle integration, **not systemd dispatch before/during/
after disconnect, original-job binding, installed execution, or generation
acknowledgement**. The adapter remains dormant. Closing a client never certifies
process termination; persistent absence or a stuck process remains uncertain.

Public source audit: [GLib 2.86.0 system address resolution](https://github.com/GNOME/glib/blob/2.86.0/gio/gdbusaddress.c#L1246)
selects the system address from trusted process configuration or the compiled
Unix socket default without session autolaunch. The public API documentation
fetch timed out; the tagged source includes its API documentation. This source
inspection does not identify or qualify the installed guest's GLib version.

## Verification

Exact final selections:

```sh
tools/run-unit-tests tests/unit/test_execution_probe_cleanup_safety.py tests/unit/test_probe_bus_client_cleanup_safety.py tests/unit/test_execution_policy.py tests/unit/test_adapters.py -q
tools/run-tests component tests/component/test_probe_bus_client.py -q
```

- Final focused selection: **91 tests and 24 subtests passed**. The probe
  module now has 45 cases; the owned lifecycle module has 19. An initial focused
  run of those two modules passed all 64 before the component additions.
- Component launcher: **777 isolated cleanup prerequisites and 3 subtests
  passed**, then **6 private-bus/socket cases passed**. It used the approved
  escalation route for local sockets; no approval or Polkit denial occurred.
- `test_client_close_recovery_preserves_collected_evidence` covers failed and
  interrupted close without replay, resnapshot or success promotion.
  `test_pre_dispatch_failure_retains_failed_close_without_systemd_calls`
  covers open/resolver failure and mismatched buses. Additional cases cover
  late dispatch, fresh senders and unavailable-sender refusal.
- `test_probe_pre_dispatch_failure_closes_owned_client_and_preserves_observer`
  uses the real Gio resolver and private buses for missing-manager, wrong-bus
  and refused-socket cases. It confirms completed lifecycle cleanup, sender
  disappearance and continued observer access. Existing real lifecycle tests
  still pass. No component double is presented as systemd qualification.
- No test failed in this slice. Changed-document links and scoped whitespace
  checks passed. No full `make check`, build, VM or installed attempt ran;
  activation attempts remain two and Task 15A acceptance remains unfinished.

## Cleanup and next action

All commands exited and results were collected. Component fixture teardown
completed; each real owned client closed, sender disappearance was observed,
test-owned sockets closed and observers were closed only by test teardown.
No VM, lease, host systemd probe, screenshot or separate worker was started.
No live recovery state or denial remains. Simulated pending callbacks/units in
unit doubles are not live resources.

Qualify systemd dispatch/reference behavior before/during/after sender closure,
with the observer retaining enough evidence to distinguish late creation,
reference release and real process cleanup. Preserve uncertain outcomes and
never replay creation. Then resolve original-job binding and qualify installed
success/failure/cleanup with `record_execution_backend`; use the existing
guarded VM when ready. Full receipts and the native/Snap/Flatpak route and
other-user matrix remain required.

Next settings: `gpt-6-astra/high`, Standard. Lifecycle integration now passes
focused checks; disconnect settlement still requires systemd dispatch and
reference-lifetime reasoning before the contract is settled for Sol high.
