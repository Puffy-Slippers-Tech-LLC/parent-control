# 193 — Verify Parent usability without Internet access

Estimate: 20–30 minutes. Follow the
[session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Scope and prerequisites

Deliver **LIFE06**.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **003d** — DESK04 direct logout command and independent GDM result.
- **010** — UI17 Parent Screen time limit binding; installed qualification and owned cleanup passed.
- **044a** — DESK10 same-desktop window switching.
- **193a** — shared distro-independent VM Internet isolation with test control and public observations preserved.

## Session boundary

Task 193a qualified the minimal shared offline mechanism. Reuse its
enter-offline, restore-online and cleanup operations without adding networking
infrastructure. No live acceptance has been attempted for this task. This task owns LIFE06's composition
and the Parent usability assertion below.

## Read only this context

Read LIFE06 and the qualified shared isolation, observation and cleanup callables.
Apply the [system-operation rule](../../Mandates/UI-Automation-Mandate.MD).

- [Owned VM Internet contract](../E2E-Building-Blocks.md#owned-vm-internet-isolation)
  and LIFE06; UI17's Parent binding and its shared control/readback operations.
- `tests/integration/vm_internet.py`: `InternetIsolation.enter`, context-manager
  unwind and `restore`; `tests/integration/vm_internet_qualification.py`:
  `internet_result` for independent Internet observations. The finite
  `online_offline_online` sequence is helper qualification, not the app recipe.
- `tests/integration/system_runner.py`: `Lease.stop_by_restore`, `finish` and
  `_recover_recorded_cleanup`; retain fresh pinned-domain handles and exact
  configuration identity except the network's read-only connection count.
- `tests/unit/test_vm_internet_cleanup_safety.py` and affected recorder/worker
  cleanup tests. Helper qualification and final cleanup passed in
  `output/test-runs/host/reports/20260930T225447Z-420cdcde/report.md`.

## Implementation

Compose 193a's same VM-level operation on every guest, with no distro-specific
commands. Offline means Internet unavailable while test control remains usable;
it does not require the local link to be down. Keep the work focused on public
app behavior, using the existing Parent control and observation bindings.

## Live VM acceptance

Remove Internet access through the qualified helper and independently confirm
the offline condition. In the existing Parent window, perform a declared normal
control action through the qualified UI17 binding and read its expected public
result; a visible window alone does not prove usability. Restore Internet access
and independently confirm recovery. Preserve the helper's ownership and uncertain
replay guards and owned cleanup. Complete local approval/enforcement scenarios
remain in their separate customer tasks.

Implement and register this planned fixed qualification and its cleanup coverage before invoking it:

```sh
tools/run-tests integration check_e2e_operate_public_connectivity_controls
```

Use the shared watch intent, display and guarded command transport. Pass
applicable cleanup/ownership checks in isolation first. Require independent
result readback, sanitized evidence and owned cleanup. Host tests alone do not
qualify a live route or complete a customer scenario.

## Close out

Follow the [master close-out](../E2E-Execution-Plan.md#completion-and-document-cleanup).
Record the proven callable/scope and existing artifact, check **193** only after
acceptance and cleanup, and advance the sole pointer in queue order. Keep an
unmet requirement pending with its return condition. Delete this brief after
its enduring contract is recorded in the catalogue/source.
