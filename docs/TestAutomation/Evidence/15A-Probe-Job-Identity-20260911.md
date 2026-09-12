# 15A original-job identity refusal — 2026-09-11

Task 15A remains the earliest ready unchecked entry; none bypassed. Actual
settings `gpt-6-astra/high`, Standard. All-task guarded VM clearance persists.
No Task 20 R1 recovery work or charge. Existing edits were preserved.

## Discriminating audit

The proposed running-job/InvocationID bracket is insufficient, even with a
trusted manager and no manager replacement. The upstream **v259** source audit
establishes these constraints; it does not identify the installed guest version:

- [job.c](https://github.com/systemd/systemd/blob/v259/src/core/job.c),
  `job_install` / `job_merge_into_installed`: a mergeable restart can change and
  rerun the installed job while preserving its ID. Restart becomes start after
  its stop phase. Therefore observing the returned job as running/start cannot
  prove that the first invocation still owns the observed status. This rejects
  an additional job-property polling adapter as the proposed solution.
- [service.c](https://github.com/systemd/systemd/blob/v259/src/core/service.c),
  `service_start`: a new start acquires an invocation ID and resets main-command
  status. Matching name, description and command do not retain the earlier exit.
- [dbus-job.c](https://github.com/systemd/systemd/blob/v259/src/core/dbus-job.c),
  `bus_job_vtable`: job properties expose identity, unit, type and state, without
  an invocation ID. The [public interface](https://github.com/systemd/systemd/blob/v259/man/org.freedesktop.systemd1.xml)
  prescribes subscribing before submission for the job result. `JobRemoved`
  carries no invocation ID; its result alone cannot bind a later status read.
- [dbus-manager.c](https://github.com/systemd/systemd/blob/v259/src/core/dbus-manager.c),
  `method_start_transient_unit`, queues through `bus_unit_queue_job`.
  [dbus-unit.c](https://github.com/systemd/systemd/blob/v259/src/core/dbus-unit.c),
  `bus_unit_queue_job_one`, refuses start when `RefuseManualStart` is set.
  Setting that transient property also refuses the initial direct create/start;
  it is not a drop-in restart guard. `InvocationID` is exposed read-only.

The minimum still-missing evidence is a causal connection between the submitted
execution and its terminal result that survives pre-observation restart/merge,
or a supported prevention mechanism covering those transitions. A job path,
current invocation, timestamps and matching metadata do not supply it. Any
signal-based candidate must prove capture before dispatch, retention despite
coalescing/loss, and invocation association; subscribing alone is insufficient.
The next design step should evaluate one bounded witness integrated with the
[fresh-generation receipt contract](../../SystemDesign/Applications.md#generation-witness-design-gate),
rather than add another polling layer. No witness design is accepted here.

## Implemented guard and scope

`ExecutionProbe._snapshot` now labels a matching canary exit `identity-unproven`
instead of `executed`. All current positive snapshots have this limitation,
including ordinary fast exit. The dormant adapter therefore cannot currently
return `executed=True`; it retains the property for a future qualified result.
This is an intentional availability limitation, not completed positive binding.
Observed failure status remains `execution-failed`, not a policy-denial receipt.

Terminal status, manager/job/observed-invocation coordinates and owned-reference
cleanup remain available. Release drops only the original sender's reference;
it does not assert that this terminal observation belongs to the first invocation
and never signals a replacement. Pending replies still retain the sender and
reference; late replies and cleanup recovery preserve the unproven result.
The [owning transport contract](../../SystemDesign/Applications.md#bounded-probe-transport-and-open-limits)
publishes these limits for all consumers.

## Verification

New regression:
`test_original_job_cannot_certify_a_preobserved_replacement`, variants
`before-first-read` and `same-job-rerun`, in
`tests/unit/test_execution_probe_cleanup_safety.py`.

- First test construction run: two failures from a test hook modifying the
  simulated unit after GC. Guarded the hook against an absent unit.
- Corrected reproducer before production change: both variants failed because
  `executed` was incorrectly true. The same-job variant presents the returned
  job during activation, then a terminal replacement with unchanged metadata.
- Final focused selection: **108 tests / 24 subtests passed**, covering the
  execution-probe and owned-client cleanup modules plus
  `tests/unit/test_execution_policy.py` and `tests/unit/test_adapters.py`.
  Existing fast-exit, transition, late-reply, concurrency, interrupted release
  and close-recovery checks now require the unproven result without losing
  cleanup or evidence. No required case was removed.

Reproduction: `tools/run-unit-tests tests/unit/test_execution_probe_cleanup_safety.py tests/unit/test_probe_bus_client_cleanup_safety.py tests/unit/test_execution_policy.py tests/unit/test_adapters.py -q --tb=short`.

Tested source SHA-256:

| Input | SHA-256 |
| --- | --- |
| `broker/oh_no_parent_control/execution_probe.py` | `b2f5fa321fd61d0851cd228f38d9ca95fe8c1a002a30c642e4caaeb2a47b9e06` |
| `tests/unit/test_execution_probe_cleanup_safety.py` | `afeeaef91f7a80add46e38edc5cdfcc0e8e20fea49335d7d00d4e5562cb521db` |
| `tests/unit/test_probe_bus_client_cleanup_safety.py` | `abbb7ff40bb0c444af968c0cd436506d145932932ec45ffcf3d1b25ff0e1d2f3` |
| `tests/unit/test_execution_policy.py` | `3fa7bd1e96f9cecdb81c063f9d8b514d3db36e9ba0a4a7eb29ea728c6297e2ff` |
| `tests/unit/test_adapters.py` | `0fe35ec60bf356b33d53b02ed7765d20d1041d20324a43a240288716031b8d12` |

This qualifies a local refusal, not positive binding or systemd behavior.
Private-bus lifecycle code was unchanged; its retained qualification was not
rerun. No build, full `make check`, installed/VM run or acceptance is claimed.
Scoped whitespace and changed-document link checks passed.

All commands exited and results were collected; unit executors joined. No
live bus, systemd unit, VM, lease, screenshot or background operation was
started. The simulated pending resources are test data, not live leftovers.
No approval/Polkit denial occurred; no logs were modified or deleted.
Activation attempts remain two; Task 15A stays unchecked.
