# Optional child extension design draft

Status: optional-extension migration design. Rows 1/2 are complete; their current
design belongs to [Screen time](Screen-Time.md#countdown-and-expiry-enforcement)
and the [broker API](Broker.md#broker-interface-and-roles). The extension remains
required by existing core integration paths. Native enforcement qualification
and core lifecycle/app-policy work remain; replacing the Shell-local timing
reader is not a prerequisite. Each delivered increment must leave a healthy
publishable product; exploration alone earns no migration acceptance.

This is a design and migration journey, not an execution plan. It defines the
questions, architectural boundaries and release conditions for future work; it
does not schedule tasks, change the active execution queue or authorize
publication. The [specification](../Specification.md) and
[current system design](../System-Design.md) continue to own released behavior.

## Destination and release boundaries

The motivating failure is collateral extension disablement: an unrelated
extension can crash Shell, and GNOME can disable extensions globally after
recovery. Essential product behavior should survive that disablement without
reenabling extensions. This is distinct from providing graphical secure locking
while the compositor itself is crashed or hung.

The goal is to remove core product dependencies on the child extension, while
keeping the extension and its convenience dependencies. Core policy, native
time accounting and locking, independent approvals, login/unlock admission and
application restrictions must work with the extension enabled, disabled or
unavailable. Reliability, robustness and usability take priority over moving
responsibilities to a new owner.

The extension provides three convenience features: **desktop reminders, the
in-session overlay and the countdown timer**. Their extension dependency is
intentional. When the extension is unavailable, those features may disappear;
core controls must continue without reenabling it. When enabled or reenabled,
the extension may read `Main.timeLimitsManager` directly for a precise countdown
and must refresh current state without resetting allowance or grants. There is
no requirement for an extension-independent live countdown or replacement
activity observer. Independent approval through the existing GTK request/kiosk
route remains core; the in-session overlay need not remain available without
the extension.

Extension availability must eventually stop being a prerequisite for enabling
screen limits, admitting valid access, committing a kiosk approval or starting
the broker. That is the destination, not an assumption about intermediate
releases. During migration, the extension remains required wherever an essential
responsibility still depends on it. Publishable intermediate releases may retain
that requirement and must describe it accurately.

Each increment is a complete slice: replacement behavior, its callers, failure
handling, recovery, diagnostics and affected installed acceptance move together.
Do not remove a working extension path or its readiness check and leave its
replacement to another release. An investigation may end with a documented gap
and no runtime change; it need not force a migration.

Ordinary exhaustion must continue to lock without logging the child out or
closing the desktop's apps. Daily allowance and elapsed-time grants retain their
existing semantics. Application-policy transitions retain their own running-app
effects. Parent authentication, other-user isolation and recovery access remain
subject to the [threat model](../Threat-Model.md) and existing component contracts.
This work does not add support for other desktop environments.

Upstream changes, native package patches/replacements and replacing Malcontent's
accounting are forbidden. Use only existing public, supported GNOME/system APIs;
an introspectable D-Bus method is not sufficient when its contract marks it
private or its implementation requires a debug/unsafe mode. Keep
native activity tracking, usage recording, Malcontent's durable store and native
exhaustion locking. Do not build a second timing observer or durable ledger to
replace a convenience reader. If a core path still depends on the extension,
identify that actual dependency and the smallest supported remedy. Preserve
current behavior until the remedy is qualified.

## Scoped increments and dependencies

| Row | Owning design | Boundary |
| --- | --- | --- |
| 1 and 2 | [Countdown and expiry](Screen-Time.md#countdown-and-expiry-enforcement) | Complete; current countdown design. Extension independence remains outside this increment. |
| 3 | [Explore broker expiry locking](Broker-Expiry-Locking.md) | Qualify native exhaustion/revocation behavior; propose broker coordination only for a demonstrated core gap. No independent live-time reader is required merely to retain native enforcement. |

The former row 4 timing-reader replacement is retired as unnecessary for this
goal. Lack of an external equivalent to Shell's live countdown does not block
core independence. Rows 1/2 remain complete and the extension's current timing
reader remains part of its convenience implementation.

The [broker execution plan](../Broker-Expiry-Plan.md) schedules the
native-versus-product expiry review, retaining implementation/TA tasks
deferred. Completed rows 1/2 are outside that launcher. This document supplies
no second next-task pointer.

## Existing responsibilities to preserve

The native stack already supplies much of the intended implementation. Moving
product coordination into the broker should reuse that stack rather than build
a second parental-control backend.

| Component | Existing responsibility to retain |
| --- | --- |
| AccountsService and Malcontent account APIs | Live limits and grants, public limit calculations and PAM integration. |
| Malcontent timer daemon | Recorded usage and public time-estimate/query interfaces. |
| Native GNOME Shell | Activity observation, usage submission, live timing state and native lock-screen operation. |
| Product broker | Role validation, product preferences, approval arithmetic and transactions, app policy, termination and reconciliation. |
| GTK front ends and trusted authentication agent | Requests, management, preferences and parent authentication. |
| Optional extension at the destination | Desktop reminders, in-session overlay and precise countdown using native Shell state and broker calculations. |

Malcontent's [Child interface](https://gitlab.freedesktop.org/pwithnall/malcontent/-/blob/0.14.0/libmalcontent-timer/org.freedesktop.MalcontentTimer1.Child.xml)
expects a session component to submit usage intervals; the daemon is not a
self-contained desktop activity monitor or screen locker.
[GNOME's native manager](https://github.com/GNOME/gnome-shell/blob/50.6/js/misc/timeLimitsManager.js)
provides that integration independently of third-party extensions. The cited
versions are source references; qualification must identify the actual supported
distribution packages and resident session versions.

Do not introduce another authoritative usage database, alternate daily-reset
rules or an independent grant lifecycle to remove a core dependency. An external
live-countdown interface is unnecessary for this goal. The [state owner](State.md)
defines existing authorities.

## Remaining dependency map

These are the remaining subjects for investigation, not completed migrations.
Details and current limitations remain in [Screen time](Screen-Time.md).

| Responsibility in the extension | Consequence of removing it today | Discovery needed before migration |
| --- | --- | --- |
| Additional expiry lock requests in the indicator | Loses the product's additional expiry path; native locking still exists. | [Row 3 exploration](Broker-Expiry-Locking.md): effect ownership, invalidation, completion and recovery, independently of replacing the timing source. |
| Native countdown observations and [deadline endpoint](../../child/applicationUi.js) | Countdown, child-owned status and fixed-duration child approvals with a positive daily allowance depend on it; the kiosk approval calculation does not. | Retain the countdown/overlay dependency, including accurate overlay approval arithmetic. Independent core approval routes must not require this endpoint or extension activation. Verify refresh after reenabling. |
| Login/unlock trigger for `PrepareOwnSession` | Expired soft-app exceptions may miss their required restoration transition. | A reliable independent trigger with the correct authentication and policy ordering. |
| [Resume estimate refresh](../../child/resumeEstimateRefresh.js) | Loses a workaround for stale native deadlines during inactivity/resume. | Which supported packages need it and whether an existing public integration can replace it; no native patches. |
| [Authenticated unlock continuation](../../child/sessionUnlock.js) | Loses recovery from a native exhausted-session admission race. | An existing supported replacement preserving authentication and one-time request lifetime, or an explicit unresolved dependency. |
| [Locked keyboard focus repair](../../child/lockedSessionFocus.js) | Loses a native device-reactivation compatibility hook. | Whether supported native packages provide correct locked input behavior without the hook. |

There are also integration dependencies: broker startup reassertion, transactional
extension activation on screen-limit toggles and kiosk approvals, PAM recovery,
Parent child-selection recovery, extension-owned request/report process cleanup,
and installed payload/trust readiness. They must be retired with their dependent
capabilities, not mistaken for capabilities supplied by Malcontent.

The broker is already a system service. Its
[current unit](../../data/systemd/oh-no-parent-control-broker.service) has no
automatic restart or watchdog configuration. Expanding continuous responsibilities
requires an explicit lifecycle design; a process being active is not evidence
that enforcement is progressing.

## Source findings and broker migration feasibility

The 2026-11-01 source/history review distinguishes the need for a behavior from
the ease of moving it into the broker. A justified extension workaround is not
automatically a feasible broker implementation. Equivalent behavior includes
timing, authentication, cancellation, recovery, preserved work and user isolation,
not merely the same method name or eventual final state.

This assessment inspected the current controllers, introducing/follow-up commits,
test implementations and recorded task dispositions, plus upstream Shell 50.1/50.6,
Mutter 50.1/50.6 and Malcontent 0.14.0 source. Upstream tags do not establish the
behavior of every distribution patch or resident session. No new installed
experiment, migration, queue completion or release acceptance resulted.

| Responsibility | Evidence that the behavior is needed | Can equivalent functionality move easily into the broker? |
| --- | --- | --- |
| Additional expiry/revocation lock request | Native enforcement already exists; the historical repair did not isolate a native lock failure. | Sending a lock request is straightforward. An independent authoritative trigger, stale-effect cancellation, completion and recovery are not. Retaining qualified native enforcement may remove the dependency without moving a scheduler. The [expiry exploration](Broker-Expiry-Locking.md#source-review-result-and-broker-equivalence) owns this decision. |
| Session-entry app-policy restoration | Product-specific saved hard/soft rules require reconciliation after an expired exception; native time enforcement does not implement that transition. | Bounded migration with substantial code reuse: the broker already owns reconciliation. The independent authenticated entry trigger and failure/transaction ordering remain nontrivial. Follow the existing [admission proposal](BypassChallenges/Child-Disables-Extension.md), not a second lifecycle protocol. |
| Resume estimate refresh | Native activity transitions can evaluate a cached deadline before obtaining a fresh estimate, causing premature locking after inactivity. | Concrete public-API candidate: logind's aggregate user activity/sleep state plus Malcontent's existing query/replay APIs. Child identity, cancellation, avoiding active-use replay and recovery still need design and qualification; there is no Shell ordering barrier. See the [API audit](#public-api-feasibility-audit). |
| Authenticated unlock continuation | Native exhausted state can remain set while inactive despite positive time, causing an authenticated Unlock to be refused on versions with the native unlock guard. | Public logind signals expose the request, but no reviewed public API exposes Shell's parental admission state or binds a retry to native consumption/cancellation of the original request. No equivalent replacement was found. The guard is version-specific; see the [API audit](#public-api-feasibility-audit). |
| Locked keyboard focus repair | Retained-entry failures led to a diagnosed native focus issue and passing repaired histories on both targets. | No public external focus-resynchronization operation was found. The hook synchronously re-notifies Shell's resident stage grab; ordinary lock calls and public portals do not supply that operation. An extension bridge retains the dependency, and native patches are forbidden. See the [API audit](#public-api-feasibility-audit). |
| Precise native timing export | Completed usage omits ongoing activity; the export prevents child-overlay fixed approvals from overstating daily time. | An equally precise external replacement is not established by saved usage/estimate queries. It need not migrate for convenience callers. Independent core approvals must be qualified without consuming this endpoint. |
| Extension activation/readiness and owned process cleanup | Current startup, PAM and transactions rely on the essential hooks above; extension disable closes its owned overlay/report processes. | The individual calls are small, but removing gates safely is a cross-component change dependent on the preceding migrations. Preserve independent request lifetimes, rollback, diagnostics and package readiness; the convenience overlay may close. |

### Product reconciliation and approval arithmetic

Commit `baa8f8e6` introduced `PrepareOwnSession` and its extension trigger.
The [broker reconciler](../../broker/oh_no_parent_control/core.py) already reads
the authoritative grant under the policy transaction lock, preserves a current
replacement and restores strict policy for a nonzero expired grant. The current
extension trigger is asynchronous after desktop entry, not an admission barrier.
The linked admission proposal adds stronger authenticated pre-success ordering;
its PAM route coverage, bounded worker lifetime and failure policy make that
delivery larger than simply relocating the current callback. Natural grant
expiry during uninterrupted permitted use must still not immediately restore
soft blocks or terminate apps.

Commit `01ee1c51` added `NativeTime1.GetDeadline` after overlay approval arithmetic
used recorded usage that omitted uninterrupted activity. Current
`Broker._native_deadline()` and `_request_access()` consume it for child-owned
status and fixed child requests when saved control is enabled with positive daily
allowance. Kiosk calculations, rest-of-day requests and zero-daily-limit requests
do not require that native cap. Kiosk approval still reasserts the extension when
saved control is enabled: independence of its calculation is not independence
of the complete transaction. The overlay can retain its reader; deleting the cap
or substituting stale saved estimates would lose accurate convenience behavior.

### Native resume and unlock compatibility

Commit `d4df2187` introduced
[resume estimate refresh](../../child/resumeEstimateRefresh.js); `5b15f17d`
hardened recovery and diagnostics, with timer Busy names corrected by `9162f12d`.
In the inspected [native activity path](https://github.com/GNOME/gnome-shell/blob/50.6/js/misc/timeLimitsManager.js#L569),
activity transitions recalculate state using cached estimates, without first
refreshing them. Native state calculation can also exhaust that cached deadline
while inactive. The extension replays an identical recorded interval through
Malcontent to provoke a fresh estimate; it neither invents use nor repeats writes
during continuous activity. This affects native locking, not just the display.
The workaround is asynchronous and cannot guarantee refresh during service
unavailability. Moving it into the broker needs an authoritative lifecycle
trigger and the same accounting/cancellation safeguards; it must not introduce
another activity accountant.

Commit `f0e4dc77` introduced
[authenticated unlock continuation](../../child/sessionUnlock.js). In inspected
Shell 50.6, `_updateState()` can retain `LIMIT_REACHED` while inactive after a
positive estimate; [ScreenShield.deactivate](https://github.com/GNOME/gnome-shell/blob/50.6/js/ui/screenShield.js#L515)
then rejects logind's authenticated Unlock. The controller continues only that
trusted request, once within two monotonic seconds, after the same session is
active and native admission is positive. A grant alone never authorizes unlock.
Moving this to the broker would need a supported equivalent for native admission
observation, trusted request lifetime and final dispatch ordering. No such
replacement has been qualified; neither polling for positive time nor retrying
Unlock indefinitely is equivalent.

Existing controller tests use event-loop/native-state doubles. The
[reliability queue](../Reliability-Task-Queue.md) retains installed daily-only and
combined resume accounting in 003a/003 and exhausted-session single-authentication
return in 004. Their unfinished status limits claims about complete installed
recovery; source evidence of the defects does not pass those histories.

### Native locked-input compatibility

Commit `2a0447d2` introduced
[locked keyboard focus repair](../../child/lockedSessionFocus.js). Task 044's
history recorded retained locked-entry observation failures on Ubuntu and Fedora,
followed by diagnosis of restored client keyboard focus at activation. Inspected
[Mutter keyboard enablement](https://github.com/GNOME/mutter/blob/50.6/src/wayland/meta-wayland-keyboard.c#L438)
restores the remembered client surface. Its
[grab-notification handler](https://github.com/GNOME/mutter/blob/50.6/src/wayland/meta-wayland-input.c#L55)
reapplies native focus policy; the extension invokes that existing path
synchronously after keyboard-capable device addition, with no new grab or unlock.

Commit `4b9843ff` closed task 044 after the repaired retained-entry histories and
required regressions passed on both targets; the
[canonical scope](../TestAutomation/E2E-Building-Blocks.md#both-retained-child-desktops-and-explicit-entry-modes)
remains accepted. This supports the focus repair, not a universal claim that all
device-reactivation variants leaked actual input, or that extension-disabled
input protection has passed. A broker cannot directly notify another process's
Clutter stage through the existing lock API. Equivalent extension-free locked
input remains a native compatibility gate, not an expiry scheduling problem.

### Public API feasibility audit

The 2026-11-01 follow-up audited the public contracts and their native consumers,
with upstream changes, native patches, private APIs and debug modes excluded.
References include Shell/Mutter 50.1 and 50.6, GDM 50.0, Malcontent 0.14.0,
the logind documentation and xdg-desktop-portal 1.20.3. This is a bounded API
and source assessment, not a proof about every possible integration or an
installed extension-disabled qualification.

Distribution versions must remain separate. The inspected Ubuntu
[Shell changelog](https://git.launchpad.net/ubuntu/+source/gnome-shell/tree/debian/changelog?h=ubuntu/resolute-updates)
and [Mutter changelog](https://git.launchpad.net/ubuntu/+source/mutter/tree/debian/changelog?h=ubuntu/resolute-updates)
name `50.1-0ubuntu1.4` and `50.1-0ubuntu2.5`; Fedora 44's
[Shell recipe](https://src.fedoraproject.org/rpms/gnome-shell/blob/f44/f/gnome-shell.spec)
and [Mutter recipe](https://src.fedoraproject.org/rpms/mutter/blob/f44/f/mutter.spec)
name 50.6. These are source-packaging observations, not an inventory of resident
sessions or a qualification of each distribution's applied patches.

| Reviewed interface | Available capability | Missing guarantee or scope limit |
| --- | --- | --- |
| [logind user/session objects](https://www.freedesktop.org/software/systemd/man/latest/org.freedesktop.login1.html) | Observe aggregate user `State`/`IdleHint`, session `Active`/`LockedHint`, sleep state and trusted-owner `Lock`/`Unlock` signals; request locking/unlocking. | An unlock method sends a request to the session manager. Its reply does not acknowledge Shell admission or completed unlock. Signals carry no native continuation identifier, and hints do not expose Shell's time-limit state. |
| [Malcontent Child](https://gitlab.freedesktop.org/pwithnall/malcontent/-/blob/0.14.0/libmalcontent-timer/org.freedesktop.MalcontentTimer1.Child.xml) and [Parent](https://gitlab.freedesktop.org/pwithnall/malcontent/-/blob/0.14.0/libmalcontent-timer/org.freedesktop.MalcontentTimer1.Parent.xml) | Read recorded intervals and estimates; submit identical recorded intervals with documented overlap merging. | These are the daemon's data and estimates, not Shell's cached state or an acknowledgement that Shell processed an estimate-change signal. Child methods act for the calling UID. |
| [GNOME ScreenSaver](https://github.com/GNOME/gnome-shell/blob/50.6/data/dbus-interfaces/org.gnome.ScreenSaver.xml) | `Lock`, `SetActive`, `GetActive`, active-time queries and activity signals. | No parental admission/deadline export, request-bound unlock continuation or keyboard-focus resynchronization. `GetActive` reports the shield's activity, not complete input protection or its internal parental state. |
| [Shell ScreenTime](https://github.com/GNOME/gnome-shell/blob/50.6/data/dbus-interfaces/org.gnome.Shell.ScreenTime.xml) and [Introspect](https://github.com/GNOME/gnome-shell/blob/50.6/data/dbus-interfaces/org.gnome.Shell.Introspect.xml) | Break-reminder state and high-level app/window information. | ScreenTime's `State` belongs to the break manager, not parental controls. Window focus information neither controls nor certifies locked keyboard routing. |
| [Mutter IdleMonitor](https://github.com/GNOME/mutter/blob/50.6/data/dbus-interfaces/org.gnome.Mutter.IdleMonitor.xml) | Idle-time observation and idle/active watches. | `ResetIdletime` is [explicitly test-only](https://github.com/GNOME/mutter/blob/50.6/src/backends/meta-idle-manager.c#L58), requiring `MUTTER_DEBUG_RESET_IDLETIME`. It is excluded despite appearing in the XML. |
| [InputCapture portal](https://github.com/flatpak/xdg-desktop-portal/blob/1.20.3/data/org.freedesktop.portal.InputCapture.xml) and [RemoteDesktop portal](https://github.com/flatpak/xdg-desktop-portal/blob/1.20.3/data/org.freedesktop.portal.RemoteDesktop.xml) | Request compositor-controlled capture or an authorized remote-input session. | Capture has no immediate-activation request: the compositor chooses activation and devices and may stop capture. Neither portal offers native lock-grab repair or authenticated-unlock continuation. Input injection does not establish native admission. |
| Mutter's direct [InputCapture](https://github.com/GNOME/mutter/blob/50.6/data/dbus-interfaces/org.gnome.Mutter.InputCapture.xml) and [RemoteDesktop](https://github.com/GNOME/mutter/blob/50.6/data/dbus-interfaces/org.gnome.Mutter.RemoteDesktop.xml) D-Bus APIs | Native integration services behind the desktop/portal stack. | Both explicitly declare themselves private with no cross-version compatibility promise; direct use is excluded. |

**Session preparation has a supported integration route.** Linux-PAM's
[module and stack contracts](https://github.com/linux-pam/linux-pam/blob/v1.7.0/doc/man/pam.conf-syntax.xml)
allow product-owned integration without patching GDM. Correct placement after
successful configured authentication is work we control, with distribution and
route qualification still required. GDM 50's
[worker](https://github.com/GNOME/gdm/blob/50.0/daemon/gdm-session-worker.c#L1353)
overrides account-check failure during reauthentication, so an account-only
module is insufficient. Follow the existing
[admission proposal](BypassChallenges/Child-Disables-Extension.md#authentication-and-native-locking);
its gate prepares policy, not Shell's internal unlock continuation.

**Resume has public inputs, but no atomic handover.** Both reviewed Shell
versions derive activity from exactly the aggregate logind user
`State == 'active'`, false user `IdleHint`, and no preparation for sleep; see the
[native activity calculation](https://github.com/GNOME/gnome-shell/blob/50.6/js/misc/timeLimitsManager.js#L564).
A broker coordinator can observe those same public inputs, rather than invent
an activity ledger or substitute one session's idle hint. A fixed helper running
as the child can query/replay only already-recorded intervals through the
existing identity boundary. Malcontent's
[store completion](https://gitlab.freedesktop.org/pwithnall/malcontent/-/blob/0.14.0/libmalcontent-timer/timer-store.c)
emits estimate invalidation after a successful save, including duplicate-interval
replay in this implementation. That is a concrete candidate, not missing API
research. It still needs bounded workers, policy/owner invalidation, inactive
refresh scheduling and protection against late replay during active use.
Separate bus consumers can process an activity transition in different orders;
neither replay success nor a fresh daemon estimate proves Shell's cache has
updated. The current extension workaround is also asynchronous, so qualification
must compare complete behavior without inventing a stronger atomic guarantee.

**Authenticated unlock remains a native-state and ordering gap.** The ability
to observe a trusted logind `Unlock` is already public; broker-owned request
bookkeeping is not itself the missing capability. What is missing from the
reviewed public surfaces is Shell's authoritative `shouldLockSession`/parental
state and a dispatch/completion contract tying continuation to that request.
The [ScreenSaver implementation](https://github.com/GNOME/gnome-shell/blob/50.6/js/ui/shellDBus.js#L518)
routes `SetActive(false)` into the same `ScreenShield.deactivate()` guard as
logind. Replacing the call therefore does not bypass the stale-state refusal.
Observing positive daemon time or `Active`/`IdleHint` cannot prove Shell has
processed the corresponding transition. A finite retry may improve one history,
but without native admission/consumption observations it is not an established
equivalent to the current one-use continuation. A fixed sleep supplies no barrier.

This particular guard is absent from upstream
[Shell 50.1](https://github.com/GNOME/gnome-shell/blob/50.1/js/ui/screenShield.js#L515)
and present in 50.6, introduced by
[commit 5fc616ea](https://github.com/GNOME/gnome-shell/commit/5fc616ea857e86db570f225bbfa275abd4514fb4)
to prevent logind unlock from bypassing exhausted parental limits. Its absence
does not establish safe zero-time admission or complete unlock recovery. Do not
generalize the 50.6 refusal to every Ubuntu package, remove native protection,
or downgrade native packages to avoid it.

**Keyboard focus has no supported external repair in the reviewed stack.**
The relevant keyboard-enable and grab-notification implementations are identical
in Mutter 50.1 and 50.6. The existing hook notifies the compositor's resident
Clutter stage; a separately loaded Clutter library provides no remote reference
to that object. In [ScreenShield](https://github.com/GNOME/gnome-shell/blob/50.6/js/ui/screenShield.js#L193),
locking an already grabbed shield reuses the grab, so repeating `Lock` does not
perform the focus notification. Portal capture supplies no equivalent synchronous
all-keyboard protection at device reactivation.

The public [Wayland session-lock protocol](https://gitlab.freedesktop.org/wayland/wayland-protocols/-/blob/1.45/staging/ext-session-lock/ext-session-lock-v1.xml)
does specify secure lock completion, but it is absent from Mutter 50.6's
[protocol build list](https://github.com/GNOME/mutter/blob/50.6/src/meson.build#L1056)
and [compositor initialization](https://github.com/GNOME/mutter/blob/50.6/src/wayland/meta-wayland.c#L1018).
A protocol specification alone is not an available GNOME implementation.
Replacing the native locker would also cross this design's owner boundary.
Shell's [Eval implementation](https://github.com/GNOME/gnome-shell/blob/50.6/js/ui/shellDBus.js#L70)
requires unsafe mode; it cannot be used to access the resident stage or native
manager under the public-supported-API restriction. An extension bridge remains
an extension dependency. Forging idle/locked hints, toggling enforcement to force
a refresh, input injection or an unlock/relock cycle does not preserve the
existing authority, timing and input guarantees.

The easiest substantial broker migration candidate is the product's session-entry
coordination. Resume has a concrete public-API candidate requiring lifecycle
design and qualification. Authenticated unlock on affected versions and locked
focus have no supported equivalent broker replacement in the audited interfaces;
these are feasibility blockers, not merely unimplemented broker bookkeeping.
Full core independence therefore remains unresolved even if native exhaustion
passes and the extra extension lock request can be retired. Under the fixed
constraints, a remaining hook can be retired only if existing native behavior
is qualified to preserve its complete outcome or a supported equivalent is
demonstrated. Until then retain the working hook and the corresponding extension
requirement; session preparation alone cannot deliver an optional extension.

## Journey through investigation and discovery

### Establish an honest native baseline

#### Development-only recovery gate

[tools/disable-extension](../../tools/disable-extension) accepts one registered
VM name or ID:

```sh
tools/disable-extension --vm '10'
```

Run it in an existing owned, running app-snapshot maintenance VM, such as the
instance left by `tools/prepare-appsnapshot`. It uses the shared VM reservation,
guarded `test-vm exec` transport and watch infrastructure. It never adopts a
manually started guest, boots or restores a VM. The command deploys the
[development launcher](../../tools/development_broker.py) to the root-owned
`/var/lib/oh-no-parent-control-development/` directory and an explicit root-owned
service override under `/etc/systemd/system/oh-no-parent-control-broker.service.d/`.
An exact size/hash trust entry under `/etc/fapolicyd/trust.d/` admits only the
root-owned launcher, including on Fedora's trusted-language policy. The tool
refreshes native trust and waits for that exact record through the package's
bounded snapshot reader; it adds no permissive execution rule.
It restarts the broker with `--disable-child-extension-recovery`, verifies the
launcher process, and disables the extension for every currently eligible child
using the installed extension manager. Administrators and the kiosk are excluded.
Repeated calls accept identical deployed files; unknown files, links, unsafe
ownership or differing versions refuse rather than overwrite. Failures may leave
a partially modified investigation VM; normal snapshot recovery discards it.

The tool, helper and launcher are excluded from both production source and
payload manifests. Production broker code has no gate, environment variable or
persistent preference. Only the VM root can deploy the override; a child cannot
enable this mode in a released installation. The override retains the service's
other settings and survives reboot within the development history.

The launcher suppresses all extension enable requests at the
shared `ExtensionManager.set_enabled` boundary, including startup, screen-limit
toggles, kiosk approval, and PAM/Parent recovery. It also prevents those requests
from clearing GNOME's global extension-disable switch. Disable and cleanup calls
still run normally. Each suppressed call emits a fixed development warning to
stderr/the service journal, without account identifiers. A successful caller
result (including `RecoverChildExtension`) does not establish extension readiness
under this intentional bypass. The ordinary launcher's migration and trust
guards still run before service startup, but importing the patched manager
precedes them and suppressed enables skip its per-activation payload validation.
Timing queries, admission, session preparation, app policy and native enforcement
are unchanged, so remaining extension dependencies can still fail. Disabling the
extension also runs its ordinary teardown, including extension-owned windows.

VM tests explicitly requiring this isolation use
`tools.disable_extension.apply(transport)` with their existing owned, guarded
transport. This uses the same deployment operation without acquiring another
VM lease or restoring the current history. Broker restart and extension
disablement are explicit engineering setup actions, not customer actions.
Ordinary tests never invoke the tool or helper.

The CLI releases its command reservation on exit. No manual gate release or
undo is needed: the next VM `fix-tests`/`write-e2e` run recovers the recorded
maintenance instance and restores a clean snapshot; `prepare-vm` auto mode
likewise discards the modifications. An opting-in test retains its normal
attempt cleanup. No baseline or product snapshot is changed by this tool.
Verify the extension stays disabled throughout each relevant history; new child
accounts created afterwards need another explicit disable operation. This mode
is engineering isolation, not unmodified production acceptance. Retire the tool
once essential capabilities and replacement readiness checks no longer require
the bypass. Never add these development files to a production manifest or run
this installed-product experiment on the development host.

#### Native and product qualification

Begin with the question: what does the supported GNOME and Malcontent stack
already do correctly without our extension? Distinguish two kinds of observation.

**Native qualification** isolates native behavior using a maintained engineering
setup with known native limits and grants. Record any isolation of product
recovery or admission paths. This can establish an OS capability or reproduce a
native defect, but cannot establish a complete installed-product journey.

**Product qualification** uses the installed product's public actions and results,
with the extension kept disabled throughout the relevant history. It includes
Parent, independent GTK/kiosk requests, admission and recovery. The in-session
overlay, desktop reminders and countdown are checked with the extension enabled
or reenabled. These results establish the different core and convenience claims.

Current startup, PAM, Parent and kiosk recovery can re-enable the extension or
refuse an operation when activation fails. Identify every such intervention.
Disabling the extension once is insufficient: verify that it remains disabled
through the history, including login, approval and restart. An involuntary
reactivation makes the extension-disabled result inconclusive. An existing activation
gate may block a product experiment; record that integration gap rather than
calling it a native failure or deleting the gate to obtain a pass.

Distinguish individual extension disablement from GNOME's global extension
switch and failed extension startup. The extension remains installed; supporting
payload removal is a separate lifecycle scope, not a prerequisite for this goal.
Native Shell remains part of the supported desktop in all these variants.
Investigate each distinct failure boundary where it can change the outcome;
do not turn independent dimensions into an exhaustive cross-product.

Use the platform scope in [System design](../System-Design.md): Ubuntu 26.04 /
GNOME 50 is the installed acceptance baseline. Fedora Workstation 44 / GNOME 50
is a separate packaging and qualification target, not an already qualified
release. Findings for one package set do not automatically qualify the other.

### Follow customer histories and their failure boundaries

The following questions define the investigation scope. Exact finite cases and
suite allocation belong to the [test documentation owners](../TestAutomation/README.md),
under the [test scope mandate](../Mandates/Test-Scope-Mandate.md).

| Area | Question that must be answered |
| --- | --- |
| Active expiry | Do daily-only and grant-only use lock at exhaustion, and does grant expiry leave the desktop usable while daily time remains? Do open apps and another user's foreground session survive? |
| Time and approvals | Does native usage continue counting correctly without the extension, and can independent core approval routes complete fixed and rest-of-day approval? With the extension enabled or reenabled, does its countdown remain precise and its overlay work without resetting time? No live countdown or in-session overlay is required while disabled. |
| Inactivity and resume | Are idle, lock, session switching and suspend treated correctly without stale early locks or extra time? Does a grant retain elapsed-time expiry? |
| Admission and renewal | Are zero-time fresh login and retained-session unlock denied? After approval or daily renewal, does normal authentication return to the retained desktop reliably? |
| App exceptions | After an expired soft-app grant, does the next required session-entry transition restore restrictions and stop matching apps while preserving a current replacement grant? |
| Boundaries and concurrency | Are local midnight, DST/clock changes, policy edits, revocation and concurrent sessions consistent with existing allowance and grant contracts? |
| Locked input | Does supported keyboard-device reactivation preserve actual locked-session input protection without the extension hook? |
| Failure and recovery | What happens to an already active desktop, admission and pending approval when the broker, timer daemon, session bus or Shell fails, hangs or changes owner? What remains enforced during the outage? |
| Product lifecycle | Can management, request launch, approval, upgrade, restart and removal remain usable without reactivating the extension, losing settings or changing grant expiry? |

Keep expected and actual behavior separate. For each capability, record the
applicable package/configuration scope, native result, remaining product coupling,
failure owner and smallest candidate remedy in the owning design or normal
runner diagnostics. A blocked observation is not a success. Source inspection,
logs, state hints and synthetic tests cannot replace customer-visible lock,
input, authentication and application results.

Engineering fault injection and accelerated clocks remain engineering checks.
Customer acceptance uses the installed product's public actions and results.
Future live work follows the [VM mandate](../Mandates/VM-Mandate.MD) and
[UI automation mandate](../Mandates/UI-Automation-Mandate.MD); this draft does
not choose a VM, prepare a baseline or add test registrations.

### First expiry migration

The [broker expiry exploration](Broker-Expiry-Locking.md) owns row 3's context,
historical rationale, native qualification and any justified effect-owner changes.
It introduces no requirement to replace the extension's convenience timing source.
The existing
[test allocation](../TestAutomation/UI-and-E2E-Coverage.md#expiry-locking-migration-allocation)
reuses canonical E2E tasks and prevents duplicate expiry qualification.
Expiry migration remains pending independently of completed rows 1/2.

## Journey through gradual migration

### Choose a complete capability slice

The completed first slice is [broker countdown/display](Screen-Time.md#countdown-and-expiry-enforcement).
Subsequent core changes need bounded scope justified by native qualification;
design review is not authority to remove working extension code.
Application-policy reconciliation is another slice:
its privileged implementation is already in the broker and its missing piece is
the lifecycle trigger. The extension's fresh timing reader continues serving
its countdown and overlay. Removing activation gates depends on qualifying
independent core approvals and every other essential consumer; precise
convenience timing does not need to migrate.

For each slice, reuse qualified native behavior and existing public interfaces,
then assess the smallest broker/session integration needed for product behavior.
Do not make upstream fixes or new native exports a delivery dependency. Move
product coordination to the broker while leaving native mechanisms with their
existing owners. In-process Shell compatibility
hooks cannot simply be copied into a daemon; an unresolved native dependency
can prevent that slice from being migrated.

For session-entry reconciliation, build on the
[existing proposed design](BypassChallenges/Child-Disables-Extension.md) rather
than inventing a competing admission protocol. Preserve current-grant behavior,
transaction ownership, authenticated ordering and other-user isolation.

The following landmarks illustrate healthy intermediate releases. Discovery
determines their order and whether a capability needs any new broker code.
Each landmark may require smaller complete increments; none promises core
extension independence before its affected obligations are qualified.

| Migration landmark | Responsibility after handover | Healthy intermediate release |
| --- | --- | --- |
| [Broker-calculated countdown](Screen-Time.md#countdown-and-expiry-enforcement) (complete) | Current design in Screen time. | Extension remains required. |
| Independent session preparation | Broker reconciliation has a qualified admission/lifecycle trigger. | Required app-policy restoration no longer relies on the panel; convenience timing stays in the extension and other core dependencies remain pending. |
| Qualified expiry ownership | Native GNOME supplies the verified behavior, with broker coordination only for demonstrated gaps. | The extension's additional expiry path can be retired without losing locking, completion observation or recovery. |
| Native compatibility dependencies resolved | Already available supported behavior or product integration covers resume, authenticated unlock and locked input. | Each corresponding extension workaround can be removed only once its complete behavior is preserved without native changes. |
| Optional extension handover | Broker and native services supply every essential capability; extension lifecycle controls presentation only. | Activation gates are decoupled, independent request windows survive disablement, and extension-on/off core journeys both work. |

### Introduce the replacement while preserving the working product

A replacement is initially developed alongside the established path. Observation
or shadow comparisons may identify disagreements, but must not award time,
write usage, relax restrictions, terminate apps or authorize unlocks. Keep the
existing production owner until the replacement is qualified.

At handover, designate the owner of every effect. Do not let two independent
accounting writers, reconciliation triggers or recovery loops race. Any temporary
overlap must have a demonstrated idempotence and concurrency contract. Multiple
lock requests are not a substitute for agreeing on the authoritative time state.

Update the complete affected core call chain in the same increment. For example,
decoupling an approval from extension activation includes its transaction,
rollback, readiness and failure paths. Convenience callers may continue using
the extension's native-deadline endpoint; retaining them does not prevent core
independence.

Keep removal of obsolete code reversible through the normal package lifecycle
until the new path has met its release conditions. Do not create a second durable
policy store or a permanent collection of migration switches. If a temporary
switch or fallback is necessary, define its default, authority, retirement
condition and supported rollback before shipping it.

### Finish each increment as a publishable product

An increment is ready only when the selected capability works end to end, its
failure/recovery behavior is defined, and the affected product checks pass.
Unmigrated capabilities continue using their established extension implementation.
The release must not advertise complete extension independence prematurely.

Preserve current APIs and saved state where possible. Any incompatible change
needs the established [migration contract](Data-Migration.md). Package upgrade,
activation and supported rollback must not recreate grants, reset usage or leave
mixed old/new components making incompatible decisions. A required session
renewal or reboot must be reported through the normal lifecycle rather than
treated as a healthy running combination.

Review shared callers and cross-capability effects, including child-request
cancellation and app-policy transactions. Reuse existing affected regressions;
add coverage only for distinct product gaps. Building/packaging-affecting edits
retain the repository's queued package-build requirement. Apply ordinary release
acceptance, localization, lifecycle and cleanup rules through their existing
owners. Publishable means ready for publication, not an instruction to publish.

If a slice cannot meet these conditions, retain the working product path and
record the unresolved design question. Do not ship an intermediate release that
depends on the next migration to restore required functionality.

### Make the extension optional after the essential slices are complete

Only after every essential dependency is qualified elsewhere should a release
separate screen-limit enablement from optional extension activation. Replace
extension-health gates with the appropriate enforcement-readiness decisions.
Extension unavailability can then affect presentation without failing policy
saves, valid access or approvals.

Independent core request windows must survive extension disablement. The
extension-owned in-session overlay may close with the extension; its loss must
not reset policy/grants or strand an approval transaction. Reminder settings
must remain saved; missing convenience presentation is expected while disabled.
Do not clear GNOME's global
extension-disable switch as an enforcement prerequisite or silently reactivate
other extensions after a crash.

Keep extension-on and extension-off product journeys supported after this
handover. If optional installation is also offered, separate essential shared
assets from extension payload and trust requirements, and qualify upgrade/removal
accordingly. Disabled runtime and absent payload are different lifecycle claims.

## Locking and service reliability decisions

The [expiry migration](Broker-Expiry-Locking.md#locking-and-service-reliability-decisions)
owns lock-request completion, supervision and outage requirements. Apply those
requirements before transferring continuous expiry responsibilities; a broker
request and the extension both depend on GNOME's secure lock.

## Related designs and specification changes

The [disabled-extension reconciliation proposal](BypassChallenges/Child-Disables-Extension.md)
addresses one essential slice. Its preservation of existing startup extension
readiness is compatible with intermediate releases, but is not the final
optionality contract. Its authentication and enforcement obligations remain.

The proposed [weekly bedtime design](Bedtime.md) currently requires in-Shell
guards and same-callback relocking. It is not implemented and is not part of
the native daily-limit qualification baseline. Before combining the designs,
resolve its essential extension dependencies explicitly; an asynchronous broker
relock is not equivalent to that proposal's before-desktop-access requirement.

Current specification requirements tie child activation and service recovery to
the extension. Preserve those requirements during intermediate releases. When a
qualified slice changes public behavior, update the specification and relevant
Screen time, Broker, Front ends, State and Lifecycle owners together. This draft
does not silently redefine their current guarantees or complete unrelated
execution-policy assurance work.

## Outcome of the design journey

The discovery record should make it possible to explain, for each essential
capability, which native behavior is reused, which product responsibility moves
to the broker, which supported interface connects them, and which dependency
still prevents core operation without the extension. Convenience dependencies
remain intentional. Each migration decision includes its
failure policy and the complete release boundary that keeps the product healthy.

The final optional-extension release requires the installed product's core
journeys to work with the extension disabled throughout, including enablement,
native accounting, independent GTK/kiosk approvals, natural expiry, renewal/unlock,
session-entry app restoration and recovery. Desktop reminders, the in-session
overlay and countdown need not work while disabled. Its extension-enabled and
reenabled convenience paths must still work, and
disabling it during use must not change policy, grants or essential app lifetime.
Only remaining convenience features may disappear.
