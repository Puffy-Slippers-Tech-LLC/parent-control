# 15A probe evidence retention — 2026-09-11

Development/host scope; actual settings `gpt-6-astra/high`, Standard. Task 15A
remains the earliest ready unchecked entry; none was bypassed. All-task guarded
VM clearance persists. No Task 20 R1 recovery was performed or charged.
Existing owned-client implementation and unrelated edits were preserved.

## Discriminating finding and fix

The [integrated client](15A-Probe-Client-Integration-20260911.md) retained its
sender across uncertain dispatch, but `ExecutionProbe._release` still called
`UnrefUnit` without terminal evidence. Keeping the connection open did not
keep the unit pinned. Three uncovered timings could permanently lose evidence:

- A still-running unit completes after the observation deadline and is collected
  before recovery reads its status (startup, running and stopping phases).
- Delayed creation arrives between the last absence read and reference release;
  the release immediately collects the fast-exit unit.
- A terminal unit's property read fails; unconditional release discards the
  status that a later successful read could have recovered.

All five new parametrized cases failed on the prior implementation with the
modeled unit already collected. `_release` now retains the sender's reference
until `terminal_observed` is true, on both initial and recovery paths. Its
role-neutral log records this pending state without transport payloads.
Repeated nonterminal recovery remains bounded and cannot start another probe.
Once evidence is copied, the existing release/collection/client-close path
settles cleanup while preserving the original failed outcome. No extra reference,
new helper, observer mutation or signaling route was added.

This corrects the qualification limit of the earlier local recovery evidence;
the old passing cases did not exercise GC between attempts or the final
absence/release race. The durable rule and limitation are in the
[owning contract](../../SystemDesign/Applications.md#bounded-probe-transport-and-open-limits).

## Disconnect audit and remaining boundary

Read the tagged upstream **v259** implementations; this does not identify the
installed guest version or qualify actual systemd behavior:

- [Tracking](https://github.com/systemd/systemd/blob/v259/src/libsystemd/sd-bus/bus-track.c):
  `sd_bus_track_add_name` subscribes to disappearance before checking current
  credentials; `on_name_owner_changed` removes the tracked name.
- [Transient creation](https://github.com/systemd/systemd/blob/v259/src/core/dbus-manager.c):
  `transient_unit_from_message` adds the requested reference before job queueing;
  an add-reference error aborts that path. Properties may already be set.
- [Unit tracking](https://github.com/systemd/systemd/blob/v259/src/core/dbus-unit.c):
  `bus_unit_track_handler` queues garbage collection after reference loss. It
  neither cancels a queued job nor certifies process termination.

Inference: disconnect before successful reference establishment and disconnect
after it have distinct possible outcomes. An observer seeing sender absence
does not itself bind those events to manager dispatch completion. Disconnection
can also remove the only pin retaining a fast-exit result. No automatic
disconnect, dispatch barrier or evidence-transfer protocol was implemented or
qualified here. The web tracking-source fetch returned an internal retrieval
error; the direct quoted public read succeeded. No approval/Polkit denial.

Next, settle the manager-dispatch/evidence-retention protocol, using these
existing helpers and audited paths, before testing deliberate sender loss.
Keep missing/late dispatch and stuck-process cleanup explicitly uncertain;
never replay creation or close the shared observer. Once that contract supports
owned cleanup, qualify real success/failure/cleanup through a guarded installed
selection and capture installed dependency identity with `record_execution_backend`.
Original-job binding and policy-generation receipts remain open.

## Verification and cleanup

Exact selections:

```sh
tools/run-unit-tests tests/unit/test_execution_probe_cleanup_safety.py -q -k 'late_exit_keeps or create_after_last_absence or failed_snapshot_keeps'
tools/run-unit-tests tests/unit/test_execution_probe_cleanup_safety.py tests/unit/test_probe_bus_client_cleanup_safety.py tests/unit/test_execution_policy.py tests/unit/test_adapters.py -q
```

The first selection intentionally reproduced **5 failures / 45 deselections**
before the fix. The final selection passed **96 tests / 24 subtests**, including
all 50 probe cases. New regression IDs in the cleanup-safety module are
`test_late_exit_keeps_evidence_until_recovery` (three phases),
`test_create_after_last_absence_keeps_evidence_until_recovery` and
`test_failed_snapshot_keeps_terminal_evidence_for_later_recovery`.
Existing identity-refusal and stalled-process cases now require reference
retention. Late-exit cases also exercise a still-pending recovery before exit.
These are deterministic doubles, not installed or process-cleanup evidence.
The unchanged real Gio lifecycle checks retain their prior evidence; no component
rerun, build, VM attempt, full `make check` or task acceptance was claimed.
Activation attempt count remains two. Native/Snap/Flatpak and other-user
acceptance remain unfinished.

SHA-256 identities of the changed implementation and regression inputs tested:

| Input | SHA-256 |
| --- | --- |
| `broker/oh_no_parent_control/execution_probe.py` | `e7101a2dc7e6adec1b160aebe0896e13c89e2f862ca3e1223d3cc5bab0dc48c0` |
| `tests/unit/test_execution_probe_cleanup_safety.py` | `009b2b38b1362a35d74fd5c53996bd64c2f48b73fc9527183595a73b62ec878f` |

Changed-document links and scoped whitespace checks passed. All commands
exited and their results were collected. Tests used doubles and a joined test
executor; no VM, lease, private-bus process, systemd unit, probe process,
screenshot or separate worker was started. Simulated pending resources are not
live leftovers. No operational cleanup, recovery or denial remains.

Next settings: `gpt-6-astra/high`, Standard. Reference retention is now locally
proven; dispatch completion and evidence ownership across sender loss still
require unresolved concurrency/ownership reasoning.
