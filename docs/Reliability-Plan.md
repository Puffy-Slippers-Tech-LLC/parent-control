# Real-world reliability execution plan

Task queue: [Ordered task queue](Reliability-Task-Queue.md).
Next task: **001a — [Broker usage-query retry budgets](Reliability-Tasks/001a-usage-query-budgets.md)**.

## Outcome

Learn from product failures found on user computers, repair demonstrated root
causes and make unattended regressions catch the same classes of failure.
Isolated passing tests and a fresh default machine miss native dependency
behavior, retained state, event ordering and unrelated installed software.

Keep an end-to-end journey when its uninterrupted history is necessary to
reproduce the failure and prove usable recovery. Stop after that result and
the safety controls relevant to the fix. General product/release acceptance
remains with its existing owners.

The [specification](Specification.md) owns expected behavior and the
[system design](System-Design.md) owns component, trust and lifecycle boundaries.
Behavior mismatches follow [failure handling](../tests/README.md#handling-test-failures).
This audit executes no task and supplies no product pass. Every active row
remains unfinished.

## Lessons from past commits

These findings come from commit changes and their tests; they do not establish
that every condition is still uncovered. Check current coverage before adding work.

| Commit evidence | Lesson and real-world condition to check | Queue owner |
| --- | --- | --- |
| `5b15f17d`, corrected by `9162f12d` | Retry tests and code agreed on an unregistered timer Busy name. The daemon registers separate `Child.Error.Busy` and `Parent.Error.Busy` domains. Real Gio construction alone did not validate the invented name. Preserve the correction, verify dependency contracts and exercise actual contention/owner loss with recorded usage. | 001 family; 002 family |
| `5b15f17d`, earlier accounting fix `d4df2187` | Healthy estimate reads can conceal a failing resume query/replay stage; cached deadlines and recorded-use estimates differ during activity/inactivity. Check original budgets, operation-specific incidents and real native accounting across those transitions. | 001, 003a/003 |
| `f0e4dc77` | Positive time after approval did not guarantee that one authentication returned the exhausted retained desktop. Native admission state, trusted Unlock ordering and preserved work must be observed together. | 004 family; 011 |
| `0690f1de`, `f0e4dc77` | Package triggers depend on previously denied kiosk admission and an exhausted user's surviving manager. The administrative bridge is not an ordinary login. Reuse existing denied-kiosk qualification and add only the retained zero-time trigger history. | 005a/005; existing core-installation owner |
| `83d502b3` | Unrelated packages can ship root-owned group-writable data directories. Entry must tolerate them and host replacement while preserving host data. Protect actually child-writable consumed inputs; unrelated mutable contents and trusted-administrator-only group write are not admission faults. | 006a/006b, after the kiosk R01 mapping |
| `4e08dcdb` | Generated policy checks missed an actual Fedora renderer device-mapping failure before the form appeared. Require native rendering with enforcing security and accurate device-path evidence; software rendering cannot qualify a GPU mapping. | 007a/007b/007; 010 |
| `6987d0ce`, `925438ba`, `75f608f6` | Inventory-dependent preparation and asynchronous warm-up/logout can make a real station slow or unusable. Immediately submitted requests and repeated entry/exit must preserve readiness, deadlines and owned resources. This plan does not inherit the performance-improvement objective. | 008 family |
| `75f608f6`, `5414b496` | Durable-write shortcuts after failure, stale locale completion and failed selector persistence need failure/retry coverage. Diagnostic failures must not change the operation, and later success must not erase its original cause. | 008c/008a, 009a/009, 010 family |

## Scope gate for every task

Before implementation, identify the motivating fix, the machine state or event
sequence that escaped automation, and the independent product result that would
expose recurrence. Compare complete affected call chains and current tests,
including later fixes such as `9162f12d`. Record the exact remaining gap in the
existing task/queue or test owner. Already-covered branches need matching
evidence, not duplicate tests or speculative product rewrites.

Use deterministic host tests for budgets, errors, cancellation, persistence and
callback ownership. Where the lesson concerns native services, installed policy,
renderers, package triggers or retained desktops, also reproduce that condition
in the installed product and observe its failure/recovery history. Mocks cannot
establish those results. Use finite supported fixtures for messy machine inputs,
preserve the first failure and retain regressions in the lowest effective layer.

Keep adjacent negative controls where they show the fix preserves its affected
authority or isolation boundary. Broader confinement qualification, all-role
native-device matrices, notification feature acceptance, performance campaigns,
synthetic CPU/disk stress infrastructure and complete customer catalogues are
outside this plan. A newly demonstrated causal gap may justify a bounded
prerequisite; incidental capabilities must not grow into a second project.

## Task boundaries after audit

The queue and active briefs describe the reduced scope. Earlier statements that
original IDs retain every cumulative obligation are superseded by this explicit
scope audit. [Scheduling exclusions](Reliability-Task-Queue.md#scheduling-exclusions)
retain removed IDs and existing coverage owners. Exclusion grants no pass and
creates no deferred implementation task.

Host prerequisites separate product owners: broker/child retry engines,
query/controller cancellation, unlock admission/authority lifetime, locale jobs/
Request composition and child/process diagnostic isolation. Installed timer
rows each retain a complete real fault, restoration and recovery history.
Daily accounting, retained unlock and package triggers keep the journeys needed
for their motivating state. Inventory work uses three functional entry/exit
cycles; repeated retained recovery uses two cycles without synthetic load.
Task 012 reconciles only active conditions and affected reruns.

The [kiosk resilience plan](Kiosk-Resilience-Plan.md#scope-reconciliation) owns
the replacement admission architecture. Reliability 006a/006b cannot execute
until its R01 maps the legacy assertions to the new behavioral contract.
Neither empty private views, identical retained managers nor mode-bit-only
refusal survives as an implicit requirement. Cases 290/291 and their receipts
retain their original historical scope until explicitly adapted; registration
alone is no successor acceptance. Reuse exact applicable results without
concurrent overlapping work or closing the other plan's tasks.

Each task owns implementation, affected checks and cleanup. Installed tasks
require both `onpc-Ubuntu26.04` and `onpc-Fedora44` with exact package, baseline
and test-source identities. Session exceptions keep indivisible histories
together. Prerequisites supply maintained callables and applicable evidence,
never a predecessor's saved VM state or temporary brief. Independent incident
families do not require unrelated journeys to finish first.

Changed scope/dependencies are not automatically compatible with a retained
launcher checkpoint. `--check` validates these documents only. Follow the
[shared reconciliation contract](Execution-Plans.md#common-launcher-interface)
for an inactive retained run; its guards may refuse these cuts because that
route preserves original scope. Do not edit checkpoints, silently resume old
briefs against the new queue or claim a weaker result. This audit changes no
runtime checkpoint or driver authority.

## Run and resume

```sh
tools/reliability-plan --check
tools/reliability-plan
tools/reliability-plan --tasks 0
tools/reliability-plan --stop
```

The thin [launcher](../tools/reliability-plan) uses the shared
[execution-plan driver](Execution-Plans.md), GPT-6.1 Sol High, five coordinator
sessions per task and common limits, attachment, cancellation, checkpoint
recovery and per-task Git close-out. An explicit `--vm` uses registered
selectors; the default uses the enabled queue. Narrowed diagnostics do not remove
required targets. The generic entry shares the same owner:

```sh
tools/execute-plan --plan 'docs/Reliability-Plan.md' --check
```

Use GPT-6.1 Sol Medium workers for settled disjoint implementation and High or
above for concurrency, authorization and diagnosis; Low may monitor read-only
results. Keep one editor for shared state and join workers before acceptance or
cleanup. Do not start another workflow launcher inside a task coordinator.

## Coverage ownership

Extend canonical helpers and register each executable condition once. Reuse
existing selectors and state the exact added condition. Matching results can
serve their original owner after applicability review; this launcher closes
only its own row. Completing this backlog establishes its recorded reliability
regressions, not general product acceptance or release qualification.

| Existing owner | Relationship to this plan |
| --- | --- |
| [Core installation coverage](../tests/README.md#core-installation-and-runtime-compatibility) | Existing installed histories own optional PAM, first-configuration/denied-kiosk recovery, earlier-package upgrades and live dependency transactions. Task 005 adds only the exhausted retained-user trigger composition. |
| [E2E queue](TestAutomation/E2E-Task-Queue.md) and [scenario inventory](../tests/e2e/scenarios.json) | Natural exhaustion/recovery, approved entry, countdown, long routines and suspend/wake retain their customer scope and status. Reuse necessary public operations without inheriting all their scenarios. |
| [Usage-read obligation 143](TestAutomation/E2E-Building-Blocks.md#inventory-reconciliation), queued as task 172 | Tasks 002a/002 extend the same session owner with native contention/owner-loss conditions. Preserve that obligation's wider assertions and pending status. |
| [Startup obligations](TestAutomation/E2E-Scenario-Recipes.md#coverage-ownership-and-remaining-limits) | Startup-enforcement and broker-reconciliation tasks 169–170 keep their own fault matrices. |
| [Confinement design and native proofs](SystemDesign/Kiosk-Confinement.md#verification-scope-and-evidence-limits) | Broader alias, executor, notification and resource-denial qualification remains here. Preserve existing tests; qualify only affected incident paths in this plan. |
| [UI/E2E allocation](TestAutomation/UI-and-E2E-Coverage.md) | Local control/value matrices stay in host UI/unit coverage. Native policy and recovery require installed evidence. |

Keep enduring lessons, selector bindings, limitations and evidence in the queue
and existing design/test owners. Completed briefs may be removed. Do not create
a second procedure, runner or repository evidence archive.

## Execution and acceptance

Follow [test maintenance](../tests/README.md#coverage-maintenance-workflow),
[shared support](../tests/support/README.md) and applicable
[VM](Mandates/VM-Mandate.MD), [UI](Mandates/UI-Automation-Mandate.MD) and
[storage](Mandates/Test-Storage-Mandate.md) mandates. Cases own finite inputs,
order and independent assertions; shared helpers own transport, observation and
cleanup. Baseline preparation owns reusable fixtures; deliberate faults remain
attempt-owned. No private usage, grant, clock or Shell-state edits may manufacture
successful access or accounting. Keep engineering faults explicit.

Discover installed selectors through `tools/run-tests system --list --area
'session'` or `--area 'enforcement'`, or the existing integration owner. Brief
names are planned until registered and listed. Add only the missing bounded
case. Follow [system acceptance](TestAutomation/E2E-Execution-Contracts.md#system-acceptance)
for verified artifacts, complete fault/recovery histories and relevant
unrelated-user controls. A native capability required to reproduce an incident
stays an explicit coverage gap if unavailable; policy text or another renderer
cannot substitute. Do not build a new hardware-qualification project.

Observe intermediate results before recovery can conceal failure. Retry only
supported safe operations within original deadlines; never repeat uncertain
credentials, approvals or mutations. Confirm usable recovery, denial, deadlines
and retained work independently of callbacks, authentication completion, process
exit or painted frames.

Review added host resources under the
[parallelism contract](../tests/README.md#host-test-parallelism-review), run
affected host checks and `make build` after the final product/build-input edit.
Update all supported languages if product strings change. Apply
[bounded supporting work](TestAutomation/E2E-Building-Blocks.md#keep-supporting-work-bounded)
before inserting prerequisites; preserve the incident's result and avoid
inheriting unrelated customer capabilities.

Retain selectors, identities, expected/actual results, restoration and
owned-cleanup receipts. Plan retention before installed runs; later tasks can
rotate three-run journals. Use existing verified
[cumulative qualification bundles](../tests/README.md#complete-qualification-evidence-bundles)
before required reports rotate, carrying forward both targets' proof within
existing limits. Never copy attempt roots or credentials. Missing proof requires
the affected history again. Task 012 reuses applicable evidence and reruns only
active conditions invalidated by later changes; earlier revisions are not
blanket proof for the final candidate.

Refresh authoritative inventories/generated coverage when executable coverage
changes and check Markdown links. Advance only the accepted row and sole Next
task pointer. Leave other queues and completion statuses with their owners.
