# Extension recovery VM test plan

Task queue: [Ordered task queue](Extension-Task-Queue.md).
Next task: **002 — [Keep recovery safe across session and broker changes](Extension-Tasks/002-session-lifecycle.md)**.

## Scope

Implement and qualify standalone **system** regressions for extension
disablement, deliberate interference, startup recovery and failure handling on
Ubuntu 26.04/GNOME 50 and Fedora Workstation 44/GNOME 50. These engineering
histories are not customer E2E journeys and add no E2E case IDs or dependencies.
The queue starts with the newly added monitor, followed by its lifecycle/failure
boundaries and the v1.5 recovery entry points.

The queue records completed native qualification. Passing host tests or building
packages alone does not qualify native user-bus access, Fedora SELinux, actual
GNOME activation, the reporter's graphical launch or recovery timing. Unchecked
rows remain unqualified on VMs.

Expected behavior belongs to [screen-time monitoring](SystemDesign/Screen-Time.md#extension-enablement-monitoring),
[v1.5 recovery](SystemDesign/Screen-Time.md#screen-time-model),
[broker authority](SystemDesign/Broker.md#accounts-and-roles) and
[the specification](Specification.md). Follow those owners rather than inventing
administrator-only GNOME locks or attributing every Shell crash to our extension.

## Execution

`tools/extension` is only a `PlanWorkflow` adapter to the
[shared execution-plan infrastructure](Execution-Plans.md#extension-boundary).
It uses the existing namespace, checkpoints, task budgets, VM selection,
review, Git close-out and cleanup. It adds no controller or scheduler.

```sh
tools/extension --check
tools/extension --tasks 1
tools/extension --tasks 0
```

The first command validates documents only. The others execute queued work;
they are not part of this plan's creation. Default execution uses the registered
enabled VM queue; every installed brief requires results for both named targets.
`--vm`, `--stop`, `--reload` and attachment follow the shared launcher contract.
`tools/execute-plan --plan 'docs/Extension-Plan.md'` shares the same plan identity.

Apply [repository instructions](../AGENTS.md), [test maintenance](../tests/README.md#all-established-regressions),
[VM ownership/timing](Mandates/VM-Mandate.MD),
[UI route selection](Mandates/UI-Automation-Mandate.MD#route-selection) when
observing a product dialog, and [test storage](Mandates/Test-Storage-Mandate.md).
Use the registered system runner and its installed package route;
never install on the development host. Select the first unchecked row, implement
only its missing assertions, verify both targets, finish owned cleanup and then
close that row. New selectors remain **unimplemented** until registered.

## Reuse and duplicate avoidance

| Existing owner | Reuse; do not create a second copy | Missing installed scope owned here |
| --- | --- | --- |
| `tests/unit/test_core.py`, `test_extension_manager.py`, `test_service_contract.py`; `tests/component/test_private_dbus_service.py` | Policy/role/lock guards, commands/rollback, real private-bus callbacks, indefinite retry/backoff, normal-logout and error latches | Actual cross-UID session bus, enforcing distro policy, native GNOME behavior and reporter display |
| System 281: `test_enforcement.test_kiosk_expiry_installed_runtime` / `system_session_expiry.verify_offline_recovery` | Offline lists/global switch, real adapter rollback and unavailable payload | Task 004 adds only missing boot/startup recovery assertions |
| System 282: `test_session_expiry.test_kiosk_expiry_graphical_runtime` / `system_graphical_expiry.verify` | Retained session, live recovery, actual PAM authentication and genuine kiosk approval | Tasks 001, 006 and 007 extend the relevant recovery boundaries without repeating natural-expiry/gameplay histories |
| `system_session_expiry.verify_runtime_rollback` | Three existing write-response/readback/activation faults and owned broker isolation | Task 003 adds only missing actual extension-error/reporter behavior; no second rollback matrix |
| `tests/unit/test_parent_main.py`, `Broker.recover_child_extension` | Initial selection/child change call path, saved-off and authorization guards | Task 005 qualifies actual installed Parent entry points under deliberate disablement |
| Existing E2E engineering task 174 | Broker time/app-policy save fault/retry, explicitly separate from extension rollback | Remains in its original queue; this plan neither duplicates nor closes it |

The standalone allocation follows [system ownership](TestAutomation/UI-and-E2E-Coverage.md#reuse-of-system-coverage).
Extend existing registered owners when their assertions fit; register a distinct
new selector only for a genuinely new engineering history. Reuse unchanged
fixture mechanics rather than rerunning their qualification matrices. Checked
tasks stay checked under [task completion](Execution-Plans.md#accepted-evidence-lifetime-and-historical-recovery).

## Common acceptance boundary

Each brief owns a finite fault, observation, restoration and recovery sequence,
with current installed product and test sources on both targets. Verify actual
Shell configured/active state and durable settings independently of command
success. Keep selected-child policy, grants, other extensions and other users
unchanged except for the named public operation's specified effects.

Keep monitor recovery and explicit v1.5 action coverage distinct. A healthy final
extension alone cannot prove which path repaired it. Use bounded engineering
observation or isolation through maintained helpers; do not race a short disabled
window or add a production monitor-disable switch for tests. A shared test helper
owns mechanics; cases own finite inputs and assertions. Reuse supported public
APIs, genuine authentication where required and the product UI API for dialogs.
No feedback is sent. Cleanup restores only identity-verified owned faults and
finishes the runner's normal VM recovery. Record actual selectors and remaining
gaps in the owning brief/queue; no separate proof archive is required.
