# Save approved time for later execution plan

Task queue: [Ordered task queue](Save-For-Later-Task-Queue.md).
Next task: **011 — [Build the request and approved-time tabs](Save-For-Later-Tasks/011.md)**.

Implement deferred parent approval, manual pause, and use of saved time in the
kiosk and child overlay. The [feature design](Save-For-Later-Design.md) retains
the agreed behavior, visual drafts, transaction rules, and test obligations.
The [native qualification](Save-For-Later-Design.md#native-qualification-gate)
is the starting baseline. Product implementation and installed acceptance are
pending.

Start at the [system design](System-Design.md) and follow the
[execution-plan contract](Execution-Plans.md#plan-format). Each brief owns its
applicable checks and cleanup. Use the
[test maintenance route](../tests/README.md#all-established-regressions) and the
[queued package builder](Approval-Tools.md#category-coverage-and-future-additions)
for changes affecting packaging. Apply the backend review mandate in
[AGENTS.md](../AGENTS.md) to core backend changes. Use the owning
[UI automation](Mandates/UI-Automation-Mandate.MD),
[VM](Mandates/VM-Mandate.MD), and [test storage](Mandates/Test-Storage-Mandate.md)
contracts when those tasks begin.

Installed tasks use one registered general VM per supported family in the
[VM registry](../config/environment.json). Engineering checks own fault
injection and private state. Customer acceptance uses public results from the
[three journeys](Save-For-Later-Design.md#customer-scenarios), including both
kiosk return paths, overlay locking, conservation, saved-only revocation, and
reboot persistence. Keep the existing E2E queue's progress independent.

Inspect this plan without running tasks:

```sh
tools/execute-plan 'docs/Save-For-Later.md' --check
```
