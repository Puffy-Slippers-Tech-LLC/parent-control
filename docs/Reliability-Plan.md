# Unattended VM reliability execution plan

Task queue: [Ordered task queue](Reliability-Task-Queue.md).
Next task: **001a — [Broker usage-query retry budgets](Reliability-Tasks/001a-usage-query-budgets.md)**.

## Outcome

Improve the product and its unattended regressions for the machine state,
event ordering and accumulated history exposed by the October 16–17 stability
fixes, especially `5b15f17d`. Passing fresh-install tests on one default machine
configuration does not establish recovery after contention, denied admission,
exhaustion, retained-session activity or unrelated package installation.

Each task must reproduce its finite missing condition, preserve the expected
versus actual result, fix any demonstrated product root cause and retain a
regression in the lowest effective maintained layer. Existing correct behavior
needs evidence and coverage of the missing composition, not a speculative
rewrite. The [specification](Specification.md) owns behavior; the
[system design](System-Design.md) owns component and lifecycle boundaries.
Behavior decisions and unexpected regressions follow
[failure handling](../tests/README.md#handling-test-failures).

All rows start unfinished. This plan itself supplies no test pass. Installed
acceptance requires both `onpc-Ubuntu26.04` and `onpc-Fedora44`, with exact package,
baseline and test-source identities. VM graphics evidence is limited to the
renderer/device paths actually exercised; policy checks never establish an
unexercised native mapping. Task 007b owns renderer qualification; task 007
owns crash/reentry on those qualified paths.

## Task boundaries after audit

The original tasks bundled independent error engines, storage authorities and
native fault branches into 30–60 minute estimates. The queue now extracts those
deliverables before their consumers. Original IDs and queue Scope cells retain
their cumulative obligations; each original brief's **Session boundary** names
the remaining slice and extracted task IDs. The ordered queue is authoritative;
suffixes identify extracted work, not numeric execution order. All rows remain
unchecked, and this audit grants no implementation or acceptance credit.

Host tasks deliver deterministic product regressions at their actual ownership
boundary. Each installed task still owns implementation, affected host checks,
both VM targets, its complete native result and cleanup. There is no separate
implementation/verification queue. Prerequisites supply maintained callables and
matching evidence, never a predecessor's saved VM state or temporary brief.

Busy and owner loss, daily-only and combined accounting, filesystem trust
variants, renderer function and crash recovery, and the two diagnostic exports
now have separate acceptance boundaries. Preference durability and selector
fallback are separate host tasks; agent-locale failure ordering belongs once in
008a alongside Request readiness. Task 011a supplies and qualifies the bounded
guest workload interface that the repeated history previously assumed existed.

Keep natural exhaustion/approval/single-authentication return in 004, the real
package trigger history in 005, all eight paired inventory samples in 008 and
all three uninterrupted loaded cycles in 011. Their briefs explain session
exceptions and larger estimates. These estimates include ordinary preparation,
acceptance on both targets and cleanup; they are not reduced operation deadlines.
If an extracted capability still contains independent work beyond its estimate,
split it through the existing prerequisite route before implementing it.

The explicit replan changes unfinished briefs and adds prerequisites. A retained
launcher checkpoint is not automatically reconciled by `--check`; use the
[manual replan route](Execution-Plans.md#common-launcher-interface) before
resuming an incompatible inactive run. Do not edit checkpoint records or reset
evidence. This documentation audit does not run that reconciliation or a task.

## Run and resume

```sh
tools/reliability-plan --check
tools/reliability-plan
tools/reliability-plan --tasks 0
tools/reliability-plan --stop
```

The thin [launcher](../tools/reliability-plan) uses the shared
[execution-plan driver](Execution-Plans.md), GPT-6.1 Sol High, five coordinator
sessions per task and the common task limits, attachment, cancellation,
checkpoint recovery and per-task Git close-out. An explicit `--vm` uses registered
selectors; the default uses the enabled queue. Narrowed diagnostics never remove
a brief's required targets. The generic entry shares the same owner:

```sh
tools/execute-plan --plan 'docs/Reliability-Plan.md' --check
```

Use GPT-6.1 Sol Medium workers for settled disjoint implementation and High or
above for concurrency, authorization and diagnosis; Low may monitor read-only
results. Keep one editor for shared state and join workers before acceptance or
cleanup. Do not start another workflow launcher inside a task coordinator.

## Coverage ownership

The queue schedules missing engineering conditions, not a second customer E2E
catalogue. Extend canonical helpers and register each executable case once.
Where an existing selector already covers an assertion, reuse it and document
the exact added condition. Matching results may be consumed by the original
owner after its applicability review; this launcher closes only its own row.

| Existing owner | Relationship to this plan |
| --- | --- |
| [Core installation queue](TestAutomation/Core-Installation-Task-Queue.md) | Optional PAM variants, first-configuration recovery and trusted native fixtures already have acceptance. Earlier-package upgrade 003 and live dependency transaction 004 stay there; do not recreate those histories here. |
| [E2E queue](TestAutomation/E2E-Task-Queue.md) and [scenario inventory](../tests/e2e/scenarios.json) | Customer natural exhaustion/recovery, approved entry, countdown and suspend/wake cases keep their existing order and acceptance. New engineering qualifications do not complete those journeys. |
| [Usage-read obligation 143](TestAutomation/E2E-Building-Blocks.md#inventory-reconciliation), queued as task 172 | Tasks 002a/002 extend the same session owner with timer contention/owner-loss compositions. Keep one canonical executable per condition; retain the original obligation's wider assertions and pending status. |
| [Startup obligations](TestAutomation/E2E-Scenario-Recipes.md#coverage-ownership-and-remaining-limits) | Startup-enforcement and broker-reconciliation tasks 169–170 stay under their existing owner. This plan does not duplicate their fault matrices. |
| [UI/E2E allocation](TestAutomation/UI-and-E2E-Coverage.md) | Value/control matrices stay in host UI or unit coverage. Native services, actual policy effects and recovery require installed evidence. |

Completed task briefs may be removed, so keep enduring findings, actual selector
bindings and evidence in the queue and their existing design/test owners.
Do not copy an existing owner's procedure or create a repository evidence archive.

## Execution and acceptance

Follow [test maintenance](../tests/README.md#coverage-maintenance-workflow),
[shared support](../tests/support/README.md), the
[VM mandate](Mandates/VM-Mandate.MD),
[UI mandate](Mandates/UI-Automation-Mandate.MD) and
[storage mandate](Mandates/Test-Storage-Mandate.md).
Cases own finite inputs, order and independent assertions; shared helpers own
transport, observation and cleanup. Baseline preparation owns reusable fixtures;
deliberate scenario mutations remain attempt-owned. No private usage, grant,
clock or Shell-state edits may manufacture a successful time/access result.
Engineering faults must be explicit and separate from customer acceptance.

For every installed brief, discover actual selectors first:

```sh
tools/run-tests system --list --area 'session'
tools/run-tests system --list --area 'enforcement'
```

Names in unfinished briefs are planned and unimplemented until registered and
listed. Add only the missing bounded case through the existing runner; an
engineering graphical qualification must retain the same guards and evidence
as its maintained owner. Follow [system acceptance](TestAutomation/E2E-Execution-Contracts.md#system-acceptance)
for per-target verified artifacts, complete failure/recovery histories and
independent unrelated-user controls. A fake D-Bus error establishes host behavior;
it does not prove daemon reactivation, native contention or installed accounting.

Preserve the first failure and observe each intermediate result before recovery
can hide it. Retry only supported safe operations within original deadlines;
never repeat uncertain credentials, approvals or other mutations. Confirm usable
access/denial, original deadlines and retained work independently of success
callbacks, authentication completion, process exit or painted frames.

Review every added host module/resource under the
[parallelism contract](../tests/README.md#host-test-parallelism-review).
Run affected host checks before installed acceptance. Run `make build` after
the final product/build-input edit; update all supported languages if product
strings change. Apply the existing
[bounded supporting-work contract](TestAutomation/E2E-Building-Blocks.md#keep-supporting-work-bounded)
before adding a harness prerequisite: use a supported engineering route that
preserves the required product result, rather than inheriting a deferred
customer capability. A necessary finite prerequisite uses the shared driver,
preserving the consumer's scope and dependencies. An unsupported required VM
capability remains a concrete blocker, never a skipped passing branch.

At close-out, retain package/baseline/source identities, exact selectors,
expected/actual results, collection and owned-cleanup receipts for every required
target. Plan their lifetime before starting installed acceptance: later tasks
can rotate the three-run journals before task 012. Preserve required proof
through the existing
[cumulative qualification-bundle route](../tests/README.md#complete-qualification-evidence-bundles)
before that rotation, carrying forward verified receipts and both targets'
evidence within its existing limits. Reuse retained exports and verify the
newest required bundles after later publication; never copy attempt roots or
credentials. Task 012 may consume these verified receipts after their original
reports rotate. Missing proof requires the affected history again, not a
remembered pass. Refresh authoritative inventories and generated coverage when executable
coverage changes; check Markdown links. Advance only the accepted row and the
sole Next task pointer. Task 012 reconciles final-candidate evidence and any
affected reruns; earlier passing revisions are not blanket evidence for later
product changes.
