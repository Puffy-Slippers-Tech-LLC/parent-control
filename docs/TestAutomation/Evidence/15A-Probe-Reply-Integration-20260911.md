# 15A retained-reply run/recovery integration — 2026-09-11

Task 15A remains the earliest ready unchecked entry; none bypassed. Actual
settings `gpt-5.6-sol/high`, Standard. All-task guarded VM clearance persists.
No Task 20 R1 recovery work or charge. Earlier uncommitted work was preserved.

## Result and qualification limit

`ExecutionProbe.run` now submits its fixed canary through the existing retained
`ProbeBusClient.start_create` request; `recover` polls only that callback.
`ProbeResult.create_outcome` separates request state from the overall attempt,
terminal evidence and reference/client cleanup. Pending requests retain the
sender and recovery coordinates. A late job is copied before release, collision
closes only the owned sender, uncertain results cannot use absence as cleanup,
and late replies never replay creation or promote an earlier failure.

This locally qualifies the state-machine gates and qualifies the integrated
collision/owned-client route on a real private bus. The fake private-bus manager
launches no unit, so it does not qualify systemd dispatch, reference lifetime,
original-job identity or installed execution. Permanent reply loss and sender
loss remain unresolved resources under the
[owning contract](../../SystemDesign/Applications.md#bounded-probe-transport-and-open-limits).

## Verification and first-run correction

Focused unit selection:
`tests/unit/test_execution_probe_cleanup_safety.py` and
`tests/unit/test_probe_bus_client_cleanup_safety.py`.

- First integration run: **71 passed, 8 failed**. Recovery re-entered unit
  release after settlement, causing duplicate manager calls and preventing
  pre-dispatch/collision client closure. An absent uncertain unit also consumed
  the full initial observation window instead of returning to retained recovery.
- Corrected run and final source/test run: **79 passed** each. Settlement is now
  monotonic across client-close recovery; after one bounded reply poll, absence
  remains unresolved without extending the initial wait or authorizing cleanup.
- Added behavior IDs:
  `test_late_job_reply_is_copied_before_release_without_outcome_promotion`
  (executed and execution-failed),
  `test_late_collision_closes_sender_without_unit_inspection_or_promotion`, and
  `test_interrupted_create_poll_retains_same_request_for_recovery`.

Component selection: `tests/component/test_probe_bus_client.py` through the
guarded component launcher.

- Two final runs each passed **792 cleanup prerequisites / 3 subtests** and
  **10 component tests**.
- `test_execution_probe_collects_collision_reply_before_closing_owned_sender`
  proves the integrated asynchronous callback, separate owned sender, collision
  retention, sender closure and observer survival over a real private bus.

Tested SHA-256 inputs:

| Input | SHA-256 |
| --- | --- |
| `broker/oh_no_parent_control/execution_probe.py` | `fef6654aeb68c3f6b37862a66445243584fc60688a0f33390bea519a07ad0920` |
| `tests/unit/test_execution_probe_cleanup_safety.py` | `c94b1c04fe86ba7e5d05f3f1e84d4ce25e113dfaac0b272513d5c637763e6772` |
| `tests/unit/test_probe_bus_client_cleanup_safety.py` | `abbb7ff40bb0c444af968c0cd436506d145932932ec45ffcf3d1b25ff0e1d2f3` |
| `tests/component/test_probe_bus_client.py` | `7a562a9555ffd3685a7545658bb429c189b11a93a89807658416aa50beb0cc28` |

Scoped source/document whitespace passed, and all changed-document links
resolved. No full `make check`, build, installed run or Task 15A acceptance is
claimed.

All commands exited and results were collected. The failed unit subprocess
exited; final unit executors joined. Component executor threads joined,
registered objects were removed, and fixture-owned private buses and connections
were closed. No VM, lease, host systemd probe, screenshot or process remains.
No approval or Polkit denial occurred; logs were not modified or deleted.

Next: resolve original-job/invocation binding against privileged replacement,
then qualify real systemd success/failure/cleanup. Next settings
`gpt-6-astra/high`, Standard, because the next boundary is unresolved security
and ownership reasoning rather than settled adapter integration.
