# 15A pre-exec admission design — 2026-09-11

Task 15A remains earliest ready; none bypassed. Actual settings
`gpt-6-astra/high`, Standard. All-task VM clearance persists. No Task 20 R1
recovery portion or new installed attempt; activation attempts remain two.

## Result and source checks

Selected the [owning pre-exec admission contract](../../SystemDesign/Applications.md#pre-exec-admission-for-a-causal-witness).
It binds the target's invocation before authorizing exec, using a connection
created by the waiting helper and retained across its exec. It does not recover
the first wrapper invocation from a mutable systemd job. This is a design
result, not implementation or live qualification. Existing staged/untracked
implementation and tests were preserved.

New discriminating checks, against upstream v259 rather than an assumed guest
version:

- [systemd.unit](https://github.com/systemd/systemd/blob/v259/man/systemd.unit.xml):
  `RefuseManualStop` still permits dependency-driven stops. A start limit of one
  with an infinite interval covers manual starts, but `reset-failed` flushes
  its counter. Neither alone proves immutable first execution under the existing
  replacement model. No new systemd property guard is selected.
- [systemd.exec](https://github.com/systemd/systemd/blob/v259/man/systemd.exec.xml):
  `INVOCATION_ID` identifies a runtime cycle; output append/truncate modes do
  not establish which attempt first tried exec. A fresh target's self-written
  marker is insufficient: an initial denied exec writes nothing, and a later
  successful restart can create the first marker. An exclusive marker inside
  the target has the same counterexample. These are design deductions, not
  executed regressions.
- [systemd.service](https://github.com/systemd/systemd/blob/v259/man/systemd.service.xml)
  and [service_start](https://github.com/systemd/systemd/blob/v259/src/core/service.c):
  `Type=exec` tracks the initial gate exec; it is not success of a later target
  exec in that process. `service_start` acquires a new invocation ID. The
  broker must validate the gate while it waits, and independently require the
  target frame and matching final invocation/status.
- [unix(7)](https://www.man7.org/linux/man-pages/man7/unix.7.html) documents
  connection-time `SO_PEERCRED`; it is not a live PID ownership handle.
  [execve(2)](https://www.man7.org/linux/man-pages/man2/execve.2.html) documents
  preserved PID and non-close-on-exec descriptors. Therefore a gate-created
  stream endpoint can remain with the same process across target exec, without
  putting that endpoint in systemd's reusable unit configuration. This is the
  causal capability selected by the contract, not permission to signal by PID.

The existing fixed canary is a shell script containing only the exit marker;
it has no admission/result channel. Leave its boot behavior intact. The missing
native payload and broker adapter are narrowly scoped to this probe. No new
privilege grants, general launcher or process-discovery implementation is needed.
The peer credential/manager/hello checks and one-use admission are all required;
none is sufficient alone. The existing trusted-manager/root-payload boundary
cannot defend against a privileged actor forging the payload or stealing FDs;
the protocol must still reject ordinary replacement and never infer ownership
from a name, PID or token alone.

## Next executable qualification

Implement the gate/witness and bounded channel adapter with these focused
checks before integrating positive results into `ExecutionProbe`:

| Case ID | Required observation |
| --- | --- |
| ADMIT-01 | Waiting helper cannot reach target before the one admission; real admitted exec emits a frame on that same connection. |
| ADMIT-02 | Gate replaced after hello but before binding/admission: fail, no second peer selected. |
| ADMIT-03 | Gate replaced after binding, including a same-job rerun: only the old endpoint was admitted; new helper cannot exec the target. |
| ADMIT-04 | Admitted target exec fails, then replacement starts: preserve original failure; no replacement admission or success. |
| ADMIT-05 | Fast target exit retains the frame and the bound invocation before collection; a replaced terminal snapshot fails. |
| ADMIT-06 | Partial/interrupted admission send consumes admission; recovery cannot send it again. |
| ADMIT-07 | Foreign UID/unit, mismatched hello/MainPID/invocation, stale PID or duplicate peer: no admission. |
| ADMIT-08 | Wrong-stage, oversized, extra, truncated frames or ancillary FDs: fail without leaking descriptors or raw data. |
| ADMIT-09 | Gate or target timeout, EOF and lost creation reply: no success; existing owned unit/client recovery remains necessary. |
| ADMIT-10 | Socket/path replacement during cleanup: do not remove the replacement; retained owned descriptors close once. |
| ADMIT-11 | Positive frame but bad exit, manager/invocation change, collection failure or client-close failure: no receipt. |
| ADMIT-12 | No initial hello or broker restart: no target admission replay; cleanup uncertainty remains explicit. |

These IDs are **planned**, not registered or passed tests. Reuse the existing
probe/client cleanup suites and their private-bus fixtures; add actual socket
and native-process tests at the cheapest supported layer. Identity-record and
join spawned processes, run the cleanup-safety prerequisites before integration,
and qualify real systemd success/failure/cleanup in the guarded guest before
the launch matrix. Capture actual dependency identities there. No host systemd
probe or broad host process cleanup is authorized by this design.

## Verification and cleanup

This documentation-only slice checked the relevant source and maintained
contracts. No runtime tests, build, systemd or VM attempt ran, and no previous
test count is presented as fresh verification. The earlier `identity-unproven`
regressions remain unchanged. Full generation receipt sufficiency and Task 15A
acceptance remain open.

Public freedesktop browser reads returned HTTP 403; direct upstream source
reads succeeded. One guessed `.c` path was absent; file discovery located the
existing extensionless shell canary. An overbroad source output was narrowed
to the relevant definitions. No execution-policy or Polkit denial occurred.
All commands exited; no processes, sockets, units, leases, VM operations,
temporary artifacts or screenshots were created. No logs were modified/deleted.
Changed-document links and scoped whitespace checks are recorded in the active
[handoff](../Task-15.md#task-15a-continuation--2026-09-08).
