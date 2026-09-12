# 15A broker admission channel — 2026-09-11

Task 15A remains earliest ready; none bypassed. Actual settings
`gpt-6-astra/high`, Standard. All-task VM clearance persists. No Task 20 R1
recovery work or installed attempt; activation attempts remain two.

## Verified result and limits

`broker/oh_no_parent_control/probe_channel.py` implements `ProbeChannel`, a
serialized, single-use socket adapter under the
[owning admission contract](../../SystemDesign/Applications.md#pre-exec-admission-for-a-causal-witness).
It reuses the native protocol and `tests.support.terminal.capture`; no process
scheduler, host systemd operation, privilege grant or setup change was added.

The adapter accepts one candidate, captures kernel credentials and the bounded
hello, and closes the listener. It retains the caller-supplied `AdmissionBinding`
before consuming admission and sending any byte. Partial sends continue only
within that operation; failures and interruptions close the peer and cannot
replay admission. Exact result plus EOF becomes a retained `executed` or
`exec-failed` frame outcome, never a policy or terminal-exit receipt.

The generation owner supplies a caller-owned 0700 directory. The adapter pins
it with a directory descriptor, binds through Linux procfs's descriptor path,
and records the socket inode. Cleanup closes its own sockets and unlinks only
the matching inode relative to that directory. It never removes a witness or
directory. Replacement or failed inode capture retains cleanup uncertainty and
the directory descriptor; it never adopts an unrecorded socket. This protects
against observed replacement, not an atomic unlink race with hostile root.

Manager/job/unit strings in these tests are synthetic coordinates. The adapter
compares supplied peer credentials and invocation with the selected hello; the
future caller must authenticate the manager, job, exact unit/command, MainPID,
stable invocation and immutable generation path/digest before admission. Native
hello or positive output alone cannot authenticate these. The existing
`ExecutionProbe` and its `identity-unproven` refusal remain unchanged.

## Qualification

| Boundary | Executable coverage |
| --- | --- |
| ADMIT-01/04/05, channel portion | `test_broker_channel_admits_native_once_and_retains_result`: real waiting gate, actual pathname exec or denied exec, retained bound invocation and result after native exit; second admission refused. |
| ADMIT-02/03/07, channel portion | `test_broker_candidate_loss_or_duplicate_never_selects_replacement`, `test_broker_drops_already_queued_duplicate_without_admission`, and unit `test_wrong_or_stale_identity_closes_candidate_without_sending`: selected endpoint loss, queued/new duplicates, supplied UID/PID/invocation mismatch. These do not establish systemd replacement or PID-reuse qualification. |
| ADMIT-06 | `test_interrupted_admission_is_bound_consumed_and_never_replayed`: interruption/error before bytes, after a prefix, and after the full frame. `test_partial_send_continues_offset_and_half_closes_once`: correct offset through EINTR, one half-close. |
| ADMIT-08/09/12, channel portion | Malformed hello/result, wrong stage/invocation, empty/truncated/extra/oversized data, SCM_RIGHTS including control truncation, and select/hello/admission/result deadlines. Received descriptors close; repeated collection cannot promote a failure. Broker restart and lost manager replies remain outside this scope. |
| ADMIT-10, socket portion | Replacement socket survives; restoring the original permits cleanup retry. Renamed directory cleanup uses its pinned descriptor and leaves the replacement directory untouched. Existing socket is never claimed; inode-capture/unlink failure remains uncertain. Concurrent operations refuse without disturbing the owner. |

Verification commands and results, all exit 0:

- `tools/run-unit-tests tests/unit/test_probe_channel_cleanup_safety.py tests/unit/test_terminal_cleanup_safety.py -q`:
  **17 passed**, isolated before each focused component launch.
- `tools/run-tests component tests/component/test_execution_probe_native.py -q`:
  initial **62 passed**; final **66 passed** after inode-capture, unsafe-directory
  and queued-duplicate cases. Each launch's isolated safety closure passed
  **806 tests / 3 subtests**. Normal helper escalation supplied local sockets.
- `make check`: source/stage traceability checks, **7589 unit tests** and
  **134 component tests** passed on the final code. No skipped or failed cases.
- Changed-document links and scoped whitespace checks passed after handoff edits.

No runtime test failure or approval/Polkit denial occurred. A nested-instruction
file discovery returned no matched files; supplied project instructions applied.
No build, VM/systemd run, installed launch matrix or Task 15A acceptance.

Verified source SHA-256:

| File | SHA-256 |
| --- | --- |
| `broker/oh_no_parent_control/probe_channel.py` | `0aa9e07418d9a4fea7566497b793f0ffca8cc131be08ef7411978af185879724` |
| `tests/unit/test_probe_channel_cleanup_safety.py` | `267711bb0e6a07aad00b02bb71e02b2de4909bdfe4925b1b0c04f4b8dcb38e32` |
| `tests/component/test_execution_probe_native.py` | `700fdc7c964939282535f70a367c600afc394298b817867f4dc68a62a3913824` |

## Cleanup and next boundary

All commands exited and results were collected. Native capture joined compiler,
gate/witness children; executor/socket/pipe contexts and temporary fixtures
closed. Replacement/uncertain-cleanup tests explicitly reconciled their owned
fixtures and closed retained directory descriptors. Common-suite fixture teardown
passed. No VM, lease, host units, screenshots or background operation remains;
no logs were modified. Existing work was preserved.

Next integrate manager/unit/command/generation validation and terminal evidence
with the retained `ExecutionProbe` lifecycle. The directory/witness owner,
packaging/removal and guarded systemd qualification remain required. ADMIT-11,
full generation receipts, permanent transport-loss settlement and the installed
native/Snap/Flatpak matrix remain open. Next settings `gpt-6-astra/high`, Standard:
the channel is locally proven, but manager/invocation authentication, replacement
races and lifecycle ownership still require Astra before settled implementation.
