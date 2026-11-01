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
handover and its product invariants. The [TA execution plan](../Broker-Expiry-Plan.md)
owns the extracted automation work, delivered by `tools/broker` through the
shared launcher. Customer scenarios keep their existing E2E owners.

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
   [canonical test ownership](#test-ownership-and-no-duplicate-work),
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
would test a dependency intentionally absent from this experiment. The
[TA plan](../Broker-Expiry-Plan.md) now owns the panel-independent observations,
native lock qualification and live-revocation checks, with the canonical E2E
owners retaining shorter-grant continuation and retained-entry histories.
Until those gates pass, retain the production extension expiry path; native
natural-expiry estimates alone cannot retire it.

## Existing automation and missing acceptance

The [TA plan's coverage review](../Broker-Expiry-Plan.md#coverage-review-and-exclusions)
records existing executable coverage, missing engineering assertions and pending
canonical customer owners. Its [ordered queue](../Broker-Expiry-Task-Queue.md)
implements the missing defense before enforcement changes. No automation or
production behavior is implemented by this document refactor.

An extension-independent current native-time source remains a prerequisite:
`TimerUsage.query_native_deadline` currently calls the extension's
`NativeTime1.GetDeadline`; recorded use omits uninterrupted activity. Repeated
reads must not extend time or checkpoint invented use. Resolve this dependency
without a second ledger before assigning independent expiry authority.

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

The extracted [TA acceptance contract](../Broker-Expiry-Plan.md#acceptance-contract-for-this-queue)
and task briefs retain independent timing, actual lock completion, live
revocation, authoritative ordering, stale-effect cancellation, outage protection
and reconstruction, admission/isolation and unavailable-lock boundaries.
These remain mandatory handover gates on both supported targets, not optional
automation improvements. The current TIME04 upper sample plus 15-second bound
is preserved; budgets must be declared before attempts, never relaxed to pass.

### Test ownership and no duplicate work

The [canonical allocation](../TestAutomation/UI-and-E2E-Coverage.md#expiry-locking-migration-allocation)
owns cross-plan delivery. The [TA execution plan](../Broker-Expiry-Plan.md)
selects only missing engineering work through the existing installed session,
broker unit and private-service owners. Customer recipes, stable IDs, pending
prerequisites and task selection remain with the E2E queue. No parallel expiry
suite, duplicate suspend/game qualifier or alias selector is introduced.

Completed unchanged cases stay done. Changed bindings receive only affected
checks. Partial operation qualification closes no customer case; a full canonical
case can close only after its original prerequisites, recipe, both-target
acceptance and cleanup. Unsupported providers and before-access exposure remain
blockers. The TA plan's final reconciliation records remaining handover gates;
TA completion alone grants no migration or release acceptance.

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


