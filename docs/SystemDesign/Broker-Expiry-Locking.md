# Broker-owned expiry locking migration

Status: proposed; implementation and installed qualification are pending.
**Test automation is the first deliverable, before enforcement changes.**

This is the first essential capability slice of the
[optional child extension design](Optional-Child-Extension.md). It transfers
the product's additional exhaustion/revocation lock coordination from the
extension to the existing broker, retaining native GNOME accounting and secure
locking. It does not make the whole extension optional.

The [specification](../Specification.md) owns required customer behavior.
[Screen time](Screen-Time.md#countdown-and-expiry-enforcement),
[Broker](Broker.md), [State](State.md) and [Lifecycle](Lifecycle.md)
own current implementation boundaries. This document owns the proposed expiry
handover and its acceptance scope, not a second E2E execution queue.

## Scope and invariants

At zero total usable time, lock only the intended managed child's desktop.
Do not log out the child, close ordinary work or disrupt another user's
foreground session. Explicit app-policy/revocation termination retains its
existing separate contract. Daily access and wall-clock grant expiry retain
their current semantics: the larger remaining amount applies; a shorter grant
expiring does not remove daily time. Revocation must use the live grant, not a
cached client claim. Fresh login and retained unlock must preserve their
existing authentication and admission guarantees.

Malcontent remains the usage authority; AccountsService remains the live limit
and grant authority; GNOME Shell observes activity and supplies the secure lock.
The broker owns product coordination. Add no alternate usage ledger, grant
store, daily-reset rules, whole-session termination fallback or separate daemon.
Keep unrelated extension readiness, session preparation, reminders, resume,
authenticated-unlock and keyboard compatibility responsibilities in place.
Qualify their affected interactions without silently claiming those other
capabilities migrated.

## Handover sequence

1. Establish the TA defense on the current production path. Reuse the
   [canonical test ownership](#test-ownership-and-no-duplicate-work) below,
   implement missing observations and cases there, and obtain installed results
   on Ubuntu 26.04 and Fedora 44. The baseline must distinguish real lock/input,
   retained work and peer continuity from timer values or service-state hints.
2. Resolve the independent live-time source and the native-versus-broker
   coordination boundary. Qualify what native GNOME already enforces; add
   broker behavior only for the demonstrated product obligations. Repeated
   timer queries must not move the deadline forward or checkpoint invented use.
3. Implement the bounded broker lifecycle and effect ownership alongside the
   established production path. Observation/shadow work must not write usage,
   award time, relax policy or compete to mutate state. Define stale-work
   cancellation and approval/revocation ordering before effect handover.
4. Switch the product lock-request owner only after the replacement passes the
   affected installed histories with the old extension request unable to mask
   it. Whole-extension-disabled checks establish independence once the timing
   prerequisite is resolved; narrower test-only isolation may diagnose expiry
   without conflating the remaining compatibility hooks. Neither isolation is
   a production preference or proof that the whole extension is optional.
5. Remove the obsolete extension lock requests, update affected specification,
   design, diagnostics and package activation contracts together, and complete
   scoped regressions, queued package build and the independent backend review.
   Failed or blocked acceptance retains the working production path.

Use the maintained launchers, public product actions/observations, shared
fixture/credential/session helpers and owned cleanup under the
[test documentation map](../TestAutomation/README.md).
Fault injection is engineering qualification. No tests, implementation or queue
rows are completed by this document refactor.

## Investigation and historical rationale

The 2026-10-31 investigation selected only the first dependency-map row:
qualification of native exhaustion locking without the indicator's additional
lock requests. This gap remains open; no responsibility has been handed over.

Historical rationale must remain part of this qualification. Commit `71df606b`
(2026-09-02 16:11:48 PDT, "Fixed child time revocation bug; Fixed icon alignment
on parent app") introduced the explicit lock request together with
`CalculateOwnRemainingTime`: the broker reads the live grant instead of trusting
the indicator's cached grant after revocation. It also specified repeated
enforcement after a zero-time retained desktop unlock and other-user isolation.
Later that evening, `b20eebe6` documented removal of the login-time
`RuntimeMaxSec` cap because that stale snapshot could terminate a desktop despite
a later grant. These are concrete product requirements, not a generic desire
for redundant locks. The inspected history does not isolate whether native
Shell alone failed revocation locking on that original package set. Native
resume-cache and authenticated-unlock defects documented in
[Screen time](Screen-Time.md#countdown-and-expiry-enforcement) are separate,
later compatibility findings; another lock request does not repair those defects.

The prepared Ubuntu VM reported Ubuntu 26.04.1, Shell
`50.1-0ubuntu1.4`, Mutter `50.1-0ubuntu2.5`, Malcontent
`0.14.0-0ubuntu1.2` and product `2.0+local1~ubuntu26.04.1`.
The broker was running the development recovery bypass. Both fixture children
had no enabled extensions; the foreground was GDM with no child desktop.
Consequently these observations do not establish a resident child Shell version
or an extension-free desktop lock result.

Inspection of that VM's packaged `libshell-18.so` resources established an
independent native path: `main.js` creates `TimeLimitsManager` and
`TimeLimitsDispatcher`; the manager schedules the estimated current-session
end; the dispatcher calls `SystemActions.activateLockScreen()` at
`LIMIT_REACHED` when locking is available. That action calls
`Main.screenShield.lock(true)`. A broker expiry scheduler is therefore not
justified merely by removing the extension. The dispatcher does not itself
observe lock completion or subscribe to lock-action availability to retry a
skipped request. Those are qualification boundaries, not demonstrated failures.

A native engineering probe temporarily used the public AccountsService
properties (`LimitType = 2`, the daily-limit flag) and queried
`MalcontentTimer1.Child.GetEstimatedTimes` through a fresh child-owned bus
connection. With zero daily allowance and a ten-second grant, the native
current-session end matched grant expiry and reported exhaustion after natural
expiry. With 600 seconds of unused daily allowance, expiry of a shorter grant
left a positive native daily estimate. Original limits and grants were restored
and read back. No usage intervals were submitted. Because no child desktop was
active, this establishes native estimate behavior only, not ongoing accounting,
screen locking, input protection, retained applications or other-user isolation.

The existing [natural-expiry journey](../../tests/e2e/natural_expiry.py) requires
the extension countdown to seed its expiry observation. Reusing it unchanged
would test a dependency intentionally absent from this experiment. The next
bounded work within this same gap is a maintained native-expiry observation
that reuses the guarded child-entry, activity and locked-input helpers without
requiring the panel. It must observe daily-only and grant-only natural locks,
continued access when a shorter grant expires with daily time left, and retained
apps/other-user isolation, while verifying the extension stays disabled. It must
also preserve the original revocation requirement: clearing a grant locks at
zero total time but preserves any remaining daily access, including across a
retained-session return. A native natural-expiry pass alone cannot retire that
product enforcement path.
Until those observations exist, retain the production extension expiry path;
do not add a second accounting writer or claim native locking is qualified.

## Existing automation and missing acceptance

The existing automation is a starting point, not yet a sufficient handover gate.
The runnable scenario bindings include E2E-008 case 22 (daily exhaustion,
retained denial, approved recovery and fresh denial), E2E-010 cases 25/26
(another user's retained activity across child expiry), and E2E-011 cases 27–29
(daily, grant-only and combined countdowns through exhaustion). Their current
time observations require the extension panel. System cases 281/282 cover
installed PAM/runtime-cap and graphical recovery boundaries; case 282 explicitly
requires the extension active and checks extension recovery. These checks retain
their distinct assertions, but do not prove extension-independent expiry.

E2E-007's full active revocation matrix (17–20), expired-grant continuation
under E2E-038 (164–170), and suspend/wake variants 124/125 are pending with no
executable bindings. Case 22's revocation occurs after child logout, so it does
not cover immediate active-desktop revocation. Case 29's combined allowance does
not establish continued access after a shorter grant expires while daily time
remains. Existing arithmetic/unit checks cannot replace those installed results.

Cases 17–20 also switch to Parent before revocation and then attempt retained
child entry. Their complete acceptance must be preserved, but it cannot prove
immediate locking while the child remains in the foreground. That missing
engineering assertion belongs to the installed session owner in the allocation,
using an authorized management connection without switching the target desktop.
Cases 25/26 observe peer activity through the original deadline and denied child
return; they do not continuously observe the background child's lock transition.
System 282 observes ScreenSaver activity plus lock policy and session retention,
not an actual locked-input challenge or the whole entry exposure interval.

Before removing the extension's lock request, extend the maintained shared
observations and affected scenarios to cover these distinct expiry outcomes,
including the original revocation regression, without requiring the panel to
establish enforcement. Preserve the current extension-enabled journeys. Add
focused engineering coverage for broker restart/loss/hang, timer and session-bus
owner changes, uncertain lock completion, stale deadlines, concurrent approval
or revocation and another user's foreground session. Native and broker lock
requests use the same secure-lock owner; neither a successful logind request
nor `LockedHint` alone establishes protected input.

A broker handover also needs an extension-independent source of current native
time. The existing `TimerUsage.query_native_deadline` calls the extension's
`NativeTime1.GetDeadline`; recorded usage alone omits uninterrupted activity.
Reusing that endpoint or repeatedly subtracting recorded use from allowance
does not remove this dependency. Resolve and qualify the timing contract before
assigning independent expiry authority, without a second usage ledger.

Moving the request into the current broker unchanged would add a service/bus
dependency without automatic restart or watchdog supervision. A robust handover
must define independent deadline progress during management/authentication,
bounded lock completion/retry, reconstruction after restart, stale-work
cancellation and enforcement during outages. Qualify these changes on Ubuntu
and Fedora before claiming equivalent or improved reliability. Timing and
lifecycle prerequisites belong to this complete expiry slice; they do not
authorize migrating the other extension capabilities in the same increment.

## Locking and service reliability decisions

Both the existing extension request and a broker-issued request ultimately rely
on GNOME's native secure lock. The comparison is about request delivery,
completion and lifetime, not two different lock implementations.

| Candidate path | Completion property to account for |
| --- | --- |
| Existing `org.gnome.ScreenSaver.Lock` call | GNOME replies after `lock-screen-shown`; our extension reports errors but has no dedicated bounded expiry-lock retry loop. |
| Broker calling logind `LockSession` | Successful return means a lock signal was sent; it does not acknowledge completed locking. |
| Native GNOME expiry dispatcher | Already exists without the extension; its timing, lockability and recovery behavior need qualification for our product. |

See the inspected [GNOME D-Bus handler](https://github.com/GNOME/gnome-shell/blob/50.6/js/ui/shellDBus.js#L518),
[logind lock handler](https://github.com/GNOME/gnome-shell/blob/50.6/js/ui/screenShield.js#L145)
and [logind contract](https://www.freedesktop.org/software/systemd/man/latest/org.freedesktop.login1.html).
A replacement must not downgrade acknowledgement to request-only success.
Define bounded observation, retries, owner changes and failure reporting. A
`LockedHint` or screensaver-active value alone is not proof of protected input.

If investigation justifies continuous broker work, design it within the existing
service before adding a daemon. Deadlines must not wait behind parent
authentication or long management operations. Define startup readiness, connection
recovery, crash/hang supervision, restart limits and reconstruction from existing
authoritative state. A heartbeat must represent useful progress; automatic
restart does not establish correct accounting or enforcement during an outage.

State explicitly what protects an already unlocked desktop while a service is
unavailable. Denying the next login does not protect that desktop. Neither an
extension nor an external broker can independently repair a hung compositor's
secure lock. Session termination would sacrifice open work and change the
current contract; it is not an implicit fallback. An unresolved protection gap
blocks the corresponding release claim rather than becoming unlimited time or
an undocumented behavior change.

### Required acceptance histories

These are pending handover gates, delivered by the canonical owners in the
[allocation](../TestAutomation/UI-and-E2E-Coverage.md#expiry-locking-migration-allocation).
Before enforcement edits, TA must specify finite observation windows, sampling
precision, retry budgets and recovery deadlines for each binding. Keep the
existing TIME04 bound (sample upper end plus 15 seconds) for its current natural
expiry binding; any different bound needs an explicit behavior decision before
acceptance, not adjustment after a failure. Restart/hang budgets must include
the outage interval and must not restart the original allowance or grant clock.

| Boundary | Required result |
| --- | --- |
| Independent timing | With the extension endpoint unavailable, uninterrupted active daily use decreases the native balance; repeated reads do not extend the deadline. Idle, lock, switch and suspend retain native activity accounting while grants expire in elapsed time. Status and fixed/rest-of-day approval on both surfaces preserve their existing calculations, authorization and failure refusal. No synthetic usage or top-up may repair the history. |
| Lock completion | Exhaustion and foreground zero-daily revocation reach an actual input-protecting lock within the declared window, retaining ordinary work. Delayed replies, missing replies, unavailable lock action and lock-service owner replacement cannot be recorded as success. Bounded retry revalidates the current child, session and balance; positive daily time after grant expiry/revocation remains usable. |
| Ordering and stale work | Hold an approval challenge open across an expiry deadline: enforcement still progresses. Race expiry with committed renewal, revocation, allowance edits and control disablement; stale callbacks cannot lock a now-entitled desktop or relax a current restriction. Observe authoritative commit order, including Busy/refusal and rollback, rather than assuming every concurrent request succeeds. Replaced/ended sessions and reused account identities cannot receive an old lock request. |
| Restart and hang | Crash, stop and stall the broker separately with a desktop already usable, including a pending lock request; replace timer/session-bus owners at their real process boundary. Observe protection through the original deadline during the outage, then reconstruction from current native state within the declared recovery budget. No lost work, duplicate time, replayed approval, stale lock or healthy heartbeat without deadline progress is acceptable. Recovery after the outage alone does not satisfy protection during it. |
| Admission and isolation | At zero time, retained entry and fresh login expose no usable desktop; normal authentication after legitimate renewal returns to the same retained work. Check the unresolved before-access interval under obligation 142, not just the final lock. While the target expires or recovers, another user's foreground input, original activity and access remain unchanged. |
| Unavailable secure lock | Identify the actual protection available while Shell/lock service is hung or unavailable. If an already unlocked desktop cannot be protected without ending its work, record the unsupported reliability boundary and block the corresponding handover claim. Restart supervision, a denied future login or a sent lock signal cannot satisfy this gate. |

Run affected histories first on the existing extension-enabled path, then with
the old expiry request unable to supply the replacement result. Keep timing-only,
native-probe and fault-injection results distinct from complete public scenario
acceptance. Qualification of a shared operation supplies mechanics, never the
current case's state or its observed results.

## Test ownership and no duplicate work

The [coverage allocation](../TestAutomation/UI-and-E2E-Coverage.md#expiry-locking-migration-allocation)
is the canonical cross-plan allocation. Existing recipes own finite inputs and
ordered customer results; the existing E2E queue owns task selection/status.
Deliver the migration's TA through those existing bindings rather than a
parallel expiry scenario suite or second set of qualification workers.

The allocation records the single delivery owner for each requirement, including
planned engineering extensions with no executable binding yet. Do not maintain
a second ownership table here. General startup, authentication, save, identity,
reload and partial-termination residuals remain with tasks
169/170/173–175/178/179; consume their mechanics without copying their matrices.

If the migration implements a pending canonical case, it implements its full
recipe and registers that same stable case ID. After acceptance and cleanup,
close that existing queue row under its normal completion contract; never leave
an equivalent future implementation task or introduce an alias selector.
Before later task work, reconcile the actual delivered scope. An already
completed unchanged case is reused, without another run merely because this
design or a later task references it. Only genuinely changed behavior/bindings
receive affected regressions.

Partial operation qualification closes no complete scenario. A pending row
stays pending until its remaining unique outcomes pass. Reuse supplies no
mutable VM state. A different real game, before-access interval, app restoration
transition or natural midnight/DST boundary is a distinct result, not an excuse
to repeat generic expiry qualification. Missing supported multi-desktop,
suspend or provider routes remain explicit blockers.

This design does not authorize skipping the E2E sequence. Migration work must
deliver each canonical row's prerequisites before its acceptance; blocked
providers remain blockers even when the migration needs their outcome. Reuse
of an accepted operation avoids its separate qualification attempt, not the
operation or assertions needed inside a complete customer history.

Task 182 ends at its positive D>G>0 child witness, without a second
grant-expiry wait. LIFE03's two existing tasks are the sole shared suspend
implementation/qualification, usable by both migration and later cases.
The migration adds no duplicate check_e2e_suspend or game qualifier under
another name. Future briefs link to this allocation and retain their finite
recipe and only the missing result.

## Completion and reliability claim

Acceptance requires the existing extension-enabled product and the replacement
expiry path to preserve all in-scope outcomes on both targets. Independently
establish real lock/input ownership, original apps and peer continuity, daily
versus grant semantics, live revocation, and defined failure/recovery behavior.
Do not accept an extension reactivation, skipped test, hint-only lock result,
lost app or artificial time/usage change as a pass.

The current broker has no automatic restart/watchdog supervision. Moving the
call unchanged would add failure dependencies and can be more fragile. A
qualified handover can improve resistance to extension disablement and provide
central bounded recovery, but only after demonstrating useful deadline progress,
reconstruction and lock completion. Both implementations still depend on the
compositor's secure lock; no claim of repairing a hung Shell is made.


