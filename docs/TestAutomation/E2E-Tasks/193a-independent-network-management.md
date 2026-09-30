# 193a — Qualify simple VM Internet isolation

Estimate: 45–75 minutes. Follow the
[session contract](../E2E-Execution-Plan.md#task-size-and-order).

Session exception: One live isolation/recovery cycle, interruption cleanup and affected shared-infrastructure regressions must qualify the chosen mechanism together. The estimate is provisional until that mechanism is confirmed; it does not authorize broader networking work.

## Scope and prerequisites

Deliver the simplest reliable way to make the owned VM unable to access the
Internet while preserving existing test commands, public UI observations and
watch visibility. Use one shared, supported VM-level mechanism independent of
guest distribution: Ubuntu, Fedora and other guests use the same operation.
Offline means Internet unavailable; the guest's local network link may remain up.
This is a small harness prerequisite; task 193 then qualifies app usability.

Required tasks: none (Baseline).

## Read only this context

- [System design](../../System-Design.md): overview and trust boundaries.
- [VM mandate](../../Mandates/VM-Mandate.MD),
  [approval contract](../../Approval-Tools.md) and the system-operation rule in
  the [UI mandate](../../Mandates/UI-Automation-Mandate.MD).
- [Shared live and capability acceptance](../E2E-Execution-Contracts.md#live-verification-contract),
  [composition preflight](../E2E-Building-Blocks.md#composition-preflight),
  LIFE06 and the guarded transport/watch/cleanup contracts for affected routes.
- `config/test-vm.json`; the network and ownership boundaries in
  `tests/integration/Environment.md` and `tests/integration/system_runner.py`;
  the existing guarded transport and owned cleanup entry points. Follow complete
  affected functions and dependencies for the chosen mechanism only.

## Implementation

The current single guest network connection also carries SSH commands and public
UI observations. Keep that connection usable. Select one supported operation at
the host's virtualization boundary that isolates only the owned VM's Internet
traffic while retaining the existing controller access. Invoke it through the
maintained guarded harness, with explicit VM/network identity and owned reversal.
Use the same implementation across VMs; configuration may supply VM identities,
but must not select distro-specific commands or guest networking services.

Qualify only enter-offline, restore-online and interruption cleanup. Do not add
network adapters, a new management transport, guest NetworkManager/firewall
backends, or a general network-management framework. If a simple supported route
cannot preserve control within existing authority, report the concrete blocker
before expanding the design. Do not disconnect the sole test-control connection.

Preserve the existing lease, command transcript, public observations and display
collector. Refuse wrong ownership and uncertain replay. Internet isolation must
cover IPv4 and IPv6 where available, with no alternate Internet path through the
retained controller connection. Limit changes to the owned VM; preserve unrelated
host and VM networking. Use no product fault injection or broader grants.

## Host and live acceptance

Run focused regressions for the selected operation's ownership refusal, Internet
isolation, preserved controller access and restoration after interruption. Review
new host modules for parallel scheduling and run affected cleanup/ownership
checks in isolation first. Broaden validation only for boundaries actually changed.

Implement and register this planned argument-free qualification and cleanup
coverage before invoking it (the selector is currently unimplemented):

```sh
tools/run-tests integration check_e2e_independent_network_management
```

Through the guarded installed envelope on every enabled VM, use the same shared
operation and fixed online → offline → online sequence. Independently establish
Internet access before isolation, its absence during isolation, and its return
after restoration; a command's success or one failed website request is not
proof. Confirm commands, public semantic UI reads and watch remain usable while
offline. Refuse wrong VM/network ownership before mutation and uncertain replay.
Collection, owned interruption cleanup and baseline restoration must pass.
Use fixed outcomes without sending feedback. Once this minimal capability is
qualified, move to task 193's app assertion; do not add network-feature coverage.

Prepare snapshots through the maintained explicit `--vm NAME --y` route and
release maintenance ownership before acceptance; run acceptance through
`tools/run-tests` without `--vm`. Apply the session's first-live-failure handoff
boundary without repairing or retrying that failure in the same session.

## Close out

Follow the [master close-out](../E2E-Execution-Plan.md#completion-and-document-cleanup).
Record the qualified shared callable, VM isolation scope, selector and
artifact in maintained contracts. Close only 193a after live acceptance and
cleanup, remove its resolved blocker from task 193 and the plan, and advance to
193. Update 193's reading route with proven callables, preserving its full
acceptance. Delete this brief after its enduring contract is recorded.
