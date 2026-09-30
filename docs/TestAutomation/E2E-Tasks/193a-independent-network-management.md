# 193a — Qualify independent management during guest network loss

Estimate: 45–75 minutes. Follow the
[session contract](../E2E-Execution-Plan.md#task-size-and-order).

Session exception: The guarded transport, network ownership, snapshot restoration and public observation changes require one coherent installed qualification with affected shared-infrastructure regressions; host-only preparation cannot establish this capability.

## Scope and prerequisites

Deliver a shared guarded management route independent of the guest's declared
NetworkManager test connection, with public semantic observations and watch
visibility throughout real loss and recovery of that connection. This is a
harness prerequisite, not LIFE06 qualification or a complete customer scenario.

Required tasks: none (Baseline).

## Read only this context

- [System design](../../System-Design.md): overview and trust boundaries.
- [VM mandate](../../Mandates/VM-Mandate.MD),
  [approval contract](../../Approval-Tools.md) and the system-operation rule in
  the [UI mandate](../../Mandates/UI-Automation-Mandate.MD).
- [Shared live and capability acceptance](../E2E-Execution-Contracts.md#live-verification-contract),
  [composition preflight](../E2E-Building-Blocks.md#composition-preflight),
  LIFE06 and the guarded transport/watch/cleanup contracts for affected routes.
- `config/test-vm.json`; `tests/integration/Environment.md`, Resources and
  baseline preparation; `tests/integration/prepare_baseline.py::domain_layout`;
  `tests/integration/system_runner.py::isolated_xml`, `address`, lease acquisition
  and restoration; `tests/integration/online_snapshot.py::network_link`,
  `disconnected_network`, `reconnect_network` and saved transport.
- `tests/integration/vm_transport.py::Transport`, its ownership guard and SSH
  command construction; `tests/e2e/installed_journey.py::InstalledJourney`;
  `tests/e2e/ui_observations.py::UiObservations.call`;
  `tests/integration/graphical_lease.py::open_display` and shared watch transport.
- Relevant checks: `tests/unit/test_system_runner.py`,
  `test_system_runner_cleanup_safety.py`, `test_prepare_baseline.py`,
  `test_prepare_baseline_cleanup_safety.py`, `test_system_snapshots.py`,
  `test_appsnapshot_cleanup_safety.py`, `test_vm_transport.py`,
  `test_e2e_observation_transport.py`, `test_graphical_lease.py`,
  `test_e2e_watch.py` and affected worker/transport cleanup tests, all under
  `tests/unit/`. Follow complete affected functions and dependencies.

## Implementation

The current envelope admits one libvirt default-network NIC and selects one
DHCP address; the same SSH transport carries commands and public UI observations.
The display FD is independent but cannot replace semantic result readback.
Snapshot carrier handling also assumes one NIC. Do not disconnect that sole
connection to discover whether the harness survives.

Consult bounded read-only Astra High advice before implementing an unresolved
network/ownership design. Choose a maintained public route within the existing
authority; bind management and test identities explicitly and validate ownership
before any change. An independent management route must not provide alternate
Internet access that invalidates the offline assertion. Update transport/address
selection, baseline preparation and snapshot restoration consistently wherever
the chosen route crosses those boundaries. Preserve default-deny guards rather
than merely allowing another NIC or channel.

Use shared commands and observations, the existing lease and watch intention,
command transcript and display collector. Preserve single-use command handling,
wrong-role/connection refusal and uncertain-input refusal without replay. Keep
sanitized evidence and owned restoration on failure/cancellation. No direct
libvirt workaround, unrelated host network changes, alternate viewer, product
fault injection or broadened grant is authorized. If maintained setup cannot
establish the chosen route within current authority, report the specific external
prerequisite rather than bypassing it.

## Host and live acceptance

Regress network-role/ownership rejection, ambiguous address selection, guarded
SSH and public-observation routing, snapshot restore and owned interruption
cleanup. Review any new host modules for parallel scheduling and run affected
cleanup/ownership checks in isolation before other host validation.

Implement and register this planned argument-free qualification and cleanup
coverage before invoking it (the selector is currently unimplemented):

```sh
tools/run-tests integration check_e2e_independent_network_management
```

Through the guarded installed envelope on every enabled VM, establish independent
valid entry, refuse wrong roles/connections before mutation, then change the
declared test connection with one fixed NetworkManager operation. Independently
observe real offline state while management commands, public semantic UI reads
and shared watch remain usable. Reconnect and independently observe recovery.
Prove management supplies no alternate Internet route, and preserve uncertain
replay refusal. Collection, owned cleanup and baseline restoration must pass.
Use declared fixed outcomes without sending feedback or qualifying a customer
case. Task 193 separately owns Parent usability across this transition.

Prepare snapshots through the maintained explicit `--vm NAME --y` route and
release maintenance ownership before acceptance; run acceptance through
`tools/run-tests` without `--vm`. Apply the session's first-live-failure handoff
boundary without repairing or retrying that failure in the same session.

## Close out

Follow the [master close-out](../E2E-Execution-Plan.md#completion-and-document-cleanup).
Record the qualified shared callable, ownership/routing scope, selector and
artifact in maintained contracts. Close only 193a after live acceptance and
cleanup, remove its resolved blocker from task 193 and the plan, and advance to
193. Update 193's reading route with proven callables, preserving its full
acceptance. Delete this brief after its enduring contract is recorded.
