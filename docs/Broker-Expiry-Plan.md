# Broker timing and expiry exploration plan

Task queue: [Ordered task queue](Broker-Expiry-Task-Queue.md).
Next task: **001c — [Explore expiry coordination in the broker](Broker-Expiry-Tasks/001c-expiry-exploration.md)**.

## Outcome and boundary

Resolve the two separately bounded explorations:
[row 3 expiry coordination](SystemDesign/Broker-Expiry-Locking.md) and
[row 4 timing inputs](SystemDesign/Replace-Main.timeLimitsManager.md).
Active tasks are source/design reviews, not product implementation, VM fault
campaigns or a full optional-extension migration. Existing completed automation
stays done; this reconciliation completes no unchecked row.

The [rows 1/2 countdown handoff](SystemDesign/Broker-Countdown.md) is a separate
implementation session. Do not import it into this launcher. Upstream changes,
native package patches/replacements and replacing Malcontent accounting are
forbidden. Keep native recording and Malcontent storage. A proposed transient
live observer is not permission for a second durable ledger or usage writes.

The design owns product invariants and reliability decisions. The
[coverage allocation](TestAutomation/UI-and-E2E-Coverage.md#expiry-locking-migration-allocation)
owns cross-plan delivery; the E2E queue remains the sole customer-task queue.
This queue owns the explorations and retains missing expiry engineering work
deferred. Extend canonical owners rather than adding a suite, worker framework
or alias selector. Moving a row into deferred work does not drop its acceptance
or resolve the associated release blocker.

## Native-time prerequisite plan

Task 002 found that its reader reaches the extension's `NativeTime1.GetDeadline`;
completed records omit uninterrupted activity. The earlier direct-reader review
remains a valid finding, but the [upstream support proposal](Live-Time-Support-Plan.md)
is superseded and forbidden as a delivery route. Do not wait for a new native
API or restart the rejected saved-history-only approach.

The active reviews use the same queue, without another launcher:

1. **001c — [Explore expiry coordination in the broker](Broker-Expiry-Tasks/001c-expiry-exploration.md).**
   Resolve effect ownership, invalidation, completion and recovery with the
   current timing input. It depends on completed observation task 001, not row 4.
2. **001a0 — [Explore timing without the extension](Broker-Expiry-Tasks/001a0-live-time-support.md).**
   Evaluate existing logind observations plus native recorded usage and a
   transient unfinished interval. Identify synchronization/recovery gaps and
   a bounded recommendation; no prototype or accounting replacement.
3. **001a — [Confirm the live-time observation contract](Broker-Expiry-Tasks/001a-live-time-source.md).**
   Pin a supportable existing-input composition on both targets. A missing
   initial/recovery interval is a blocker, not permission to guess usage.

001c is first so a timing-source blocker cannot prevent row 3 exploration.
Rows 3 and 4 can be explored separately; final extension-independent expiry
requires both deliveries. Review completion grants no source, timing or lock pass.

## Deferred delivery and activation gate

The queue's `Deferred future work` section retains 001b and installed/host TA
tasks 002–013, including suffixed IDs and all existing assertions. They do not
run automatically after the active reviews. Preserve 002's pending host changes
and lack of installed results. No consumer acceptance is weakened to fit an
unproven live observer.

After exploration, explicitly scope/reactivate only a finite delivery increment.
The old 001b helper-only brief cannot silently authorize an activity observer;
revise it with precise source, startup/reconciliation/recovery, consumer and
validation boundaries before activation. A future scheduler needs its own
implementation brief; none is authorized by the current TA tasks. Select current
path TA independently where it is genuinely source-independent, preserving
each task's scope/acceptance and backward dependencies rather than activating
the entire deferred tail. No upstream work or full accounting migration may be
introduced as an automatic prerequisite.

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

Active review tasks own their bounded recommendations, document checks and any
explicitly necessary read-only inspection cleanup. The requirements below remain
the deferred installed/TA and final handover contract; they do not turn a review
into a mandatory live campaign. Existing unchecked briefs retain their installed
assertions even while deferred.

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
No second durable usage ledger, synthetic accounting, top-up, logout fallback or
extension reactivation may manufacture a pass.
The proposed row 4 transient observation must be qualified on its own merits;
it is not an alternate history store or permission to fabricate missing use.

First qualify added assertions on the current production path. Task 002 isolates
the timing endpoint to qualify the delivered row 4 composition; task 003 isolates
the extension lock request to establish native limits. Later
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
inputs/build dependencies changed. Core backend edits are confined to the
explicitly reactivated, bounded reader/observer delivery in 001b; active reviews
authorize no backend edits. Such later work retains the model and
independent Astra xHigh review requirements in [AGENTS.md](../AGENTS.md).
