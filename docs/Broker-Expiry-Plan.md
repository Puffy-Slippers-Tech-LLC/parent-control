# Broker expiry test automation execution plan

Task queue: [Ordered task queue](Broker-Expiry-Task-Queue.md).
Next task: **002 — [Check native time without the extension](Broker-Expiry-Tasks/002-native-time.md)**.

## Outcome and boundary

Deliver the missing automation defense for the proposed
[broker expiry handover](SystemDesign/Broker-Expiry-Locking.md), before changing
production enforcement. This plan implements tests and their shared mechanics;
it does not implement the broker scheduler, change native accounting, remove
extension behavior or authorize the whole optional-extension migration.
No row is completed by this extraction.

The design owns product invariants and reliability decisions. The
[coverage allocation](TestAutomation/UI-and-E2E-Coverage.md#expiry-locking-migration-allocation)
owns cross-plan delivery; the E2E queue remains the sole customer-task queue.
This queue selects only missing expiry engineering work. Extend the canonical
owners rather than adding another suite, worker framework or alias selector.

## Coverage review and exclusions

The review compares executable bindings, not titles or pending declarations.
System-281 owns PAM/runtime-cap policy. System-282's
[graphical worker](../tests/integration/system_graphical_expiry.py) and
[session registration](../tests/system/test_session_expiry.py) exercise real
grant expiry, retained session and extension recovery with the extension active.
Task 001 added panel-independent timed locking, fresh protected-input challenges,
original-work recovery and foreground graphical-peer input/work continuity at
this same owner, accepted on Ubuntu 26.04 and Fedora 44. ScreenSaver/logind hints
remain supporting observations. Extend this owner only for the distinct
engineering conditions below; do not duplicate 281, startup or package recovery
coverage. Extension-independent accounting and enforcement remain pending.

| Existing owner | Reuse and remaining boundary |
| --- | --- |
| Cases 22, 25–29, TIME04 | Daily/grant/combined expiry, retained/fresh denial, recovery and peer continuity already have bindings. Panel observations do not establish endpoint independence. Add affected observations at the shared owner; never a second baseline journey. |
| Tasks 084/085, cases 17/19; tasks 143–145, cases 18/20 | Full revocation, Cancel, retained entry and multi-desktop recipes remain here. They switch to Parent before revoke; task 004 below adds only foreground revocation through an authorized management connection. |
| Task 182; tasks 206–212, cases 164–170 | FLOW18 preparation ends at positive D>G>0. Uninterrupted shorter-grant expiry and soft-app access belong to 206; later transitions remain 207–212. Native estimates in task 002 establish timing semantics, not another customer no-lock journey. |
| Task 164/case 122; LIFE03 tasks 166a/166; tasks 167/168, cases 124/125 | Idle and real suspend/wake use these owners and their prerequisites. No new suspend qualifier or copied wake matrix. |
| Tasks 171/172, obligations 142/143 | Before-access exposure and real identity-scoped usage-reader failures stay here. This plan does not close them with a final lock, timing probe or timer-owner fault. |
| Tasks 169/170/173–175/178/179 | Startup, authentication, save, identity, reload and partial-termination residuals retain their matrices. Task 006b adds only old expiry callback isolation when the session changes. |
| Reliability 001 family, 002 family, 003 family, 004 family | Reuse deterministic retry/cancellation, real Busy/owner-loss, resume accounting and retained-unlock mechanics; add only deadline/lock effects absent from them. Do not implement their retry, reader or unlock matrix again. |
| Games, fullscreen, app restoration, household routines, midnight/DST | Existing recipes retain their distinct public outcomes; no second provider/game/day-boundary campaign. |

Pending E2E prerequisites remain blockers to the corresponding migration claim,
not work silently imported into this launcher. Run them through their existing
sequence and specialized acceptance. If future scope explicitly delivers a full
canonical case here, first reconcile its allocation and canonical row; use the
same case ID, full recipe, prerequisites and normal E2E close-out, never an alias
or a second implementation. Partial engineering work closes no customer row.

## Acceptance contract for this queue

Read [execution plans](Execution-Plans.md), the
[test documentation map](TestAutomation/README.md) and selected brief. Installed
tasks require `onpc-Ubuntu26.04` and `onpc-Fedora44`; a narrowed diagnostic run
cannot remove either. Read VM/UI/storage mandates before the respective work.
Use existing fixture, credential, activity, locked-input and fault ownership
helpers. Customer actions use public product routes; injected faults and native
probes remain engineering qualification. No development-host installation.

Rows 003 and 012 are bounded review/characterization tasks with actual attempts
on both named targets, as their briefs require. They can document an unsupported
native/secure-lock boundary without granting a passing enforcement result.
Missing ownership or observation still blocks them. A production-path regression
cannot be reclassified as a successful diagnostic to evade failure handling.

Every unfinished row applies the VM mandate's
[timing and slow-VM resilience](Mandates/VM-Mandate.MD#timing-and-slow-vm-resilience).
The [shared expiry owner](../tests/support/README.md) declares the delivered
sampling, lock-verification and recovery budgets and their distinct claims.
Preserve TIME04's current sample upper end plus 15 seconds and the engineering
timed-lock bound; outage time still counts against the original effect/recovery
deadline. A sent lock request, LockedHint, ScreenSaver activity, countdown or
successful restart alone cannot pass. Task briefs below add only their specific
trigger, ordering and observation needs; host orderings use controlled events
rather than hoping for a particular scheduler interleaving.

Lock-producing histories establish real protected input, retained ordinary work
and the relevant session/peer isolation control. Timing-only probes establish
only native timing; positive-entitlement controls require continued usable
input/work and no stale lock. Fault cases exercise one fault
and its recovery per attempt, with identity-recorded injection/restoration and
owned cleanup. Account/grant/usage edits cannot repair the observed history.
No second usage ledger, synthetic accounting, top-up, logout fallback or
extension reactivation may manufacture a pass.

First qualify added assertions on the current production path. Tasks 002/003
also isolate the extension endpoint/request to establish native limits. Later
replacement implementation must run only affected histories with the old expiry
request unable to mask the result, including whole-extension-disabled checks
once timing is independent. TA completion grants neither replacement acceptance
nor proof that all extension capabilities are optional.

Before effect handover, the implementation work must also extend the same
canonical tests to the new broker effect owner: cancellation after authoritative
renewal/disablement, ended/replaced sessions and reused account identities,
revalidation before retry, pending-effect reconstruction and genuine watchdog
progress. These future effect assertions cannot be passed by mocks of a
nonexistent scheduler or by current extension behavior. Current-code TA rows
own only testable existing contracts; these external replacement gates remain
pending until the production owner exists. A failing current-path product
assertion still follows failure handling and blocks its task.

Behavior mismatches use [failure handling](../tests/README.md#handling-test-failures).
An unsupported secure-lock outage or missing provider remains an explicit
handover blocker; tests must not turn it into a skip/pass. Where required
production behavior does not yet exist, retain the concrete blocker and return
condition rather than weakening a test or adding enforcement inside a TA task.

## Execution and completion

```sh
tools/broker --check
tools/broker
tools/broker --tasks 0
tools/broker --stop
tools/execute-plan --plan 'docs/Broker-Expiry-Plan.md' --check
```

The thin [launcher](../tools/broker) uses `PlanWorkflow` with GPT-6.1 Sol High,
registered VM selection and shared session limits, goal activation, attachment,
cancellation, checkpoints and per-task Git close-out. The generic entry shares
the same master-path owner. It adds no launcher state machine or new grants;
new executable discovery follows normal setup/rule activation if needed.
Do not invoke another workflow launcher inside a task coordinator.

Tasks are bounded by a single outcome/fault family. Installed estimates exceed
30 minutes only to keep fault, original deadline, recovery and cleanup together
on both targets; no Cartesian fault/account/provider matrix is required.
Use scoped host checks and maintained runner selectors, review resource changes
under the parallelism contract, and register distinct passing engineering
parameters once under system-282. Diagnostic probes use maintained guarded
qualification routes; unsupported protection cannot become a passing registration.
All new parameter names remain unimplemented until listed.
Do not add tests of these task documents or ordinary test helpers.

Each row owns its affected checks and cleanup. Record a short result, check only
that row and advance the pointer. Trust checked prerequisites; never rerun them
to renew evidence. Maintain inventories and generated coverage when bindings
change, check Markdown links, and run the queued package builder only if packaged
inputs/build dependencies changed. Core backend edits are outside this plan;
any separately authorized such change retains its model and independent Astra
xHigh review requirements.
