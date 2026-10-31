# Optional child extension design draft

Status: draft for design review. The journey starts by qualifying native GNOME
and Malcontent behavior with our extension disabled, then gradually removes
essential responsibilities from the extension. Each migration increment must
leave a healthy product that is ready to publish. A new daemon or independent
accounting engine is not a starting assumption.

This is a design and migration journey, not an execution plan. It defines the
questions, architectural boundaries and release conditions for future work; it
does not schedule tasks, change the active execution queue or authorize
publication. The [specification](../Specification.md) and
[current system design](../System-Design.md) continue to own released behavior.

## Destination and release boundaries

The destination is a product whose policy, time accounting, approvals, expiry
locking, login/unlock admission and application restrictions work with the
extension enabled, disabled or unavailable. The panel countdown, reminders,
animations, request shortcut and related presentation can remain optional.
Independent launch of the existing GTK request app must remain available.

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
| Optional extension at the destination | Countdown, reminders and desktop presentation of service-owned results. |

Malcontent's [Child interface](https://gitlab.freedesktop.org/pwithnall/malcontent/-/blob/0.14.0/libmalcontent-timer/org.freedesktop.MalcontentTimer1.Child.xml)
expects a session component to submit usage intervals; the daemon is not a
self-contained desktop activity monitor or screen locker.
[GNOME's native manager](https://github.com/GNOME/gnome-shell/blob/50.6/js/misc/timeLimitsManager.js)
provides that integration independently of third-party extensions. The cited
versions are source references; qualification must identify the actual supported
distribution packages and resident session versions.

Do not introduce another authoritative usage database, alternate daily-reset
rules or an independent grant lifecycle merely to remove the extension. A missing
public interface is a design gap to resolve, not permission to duplicate the
whole backend. The [state owner](State.md) defines existing authorities.

## Starting dependency map

These are the initial subjects for investigation, not completed migrations.
Details and current limitations remain in [Screen time](Screen-Time.md).

| Responsibility in the extension | Consequence of removing it today | Discovery needed before migration |
| --- | --- | --- |
| Verified total-time calculation and expiry lock requests in [the indicator](../../child/remainingTimeIndicator.js) | Loses the product's additional expiry path; native locking still exists. | Whether native exhaustion locking meets the complete product contract across supported session transitions. |
| [Native deadline endpoint](../../child/applicationUi.js) | Positive-daily-allowance child status reads and fixed approvals can fail without fresh timing data. | A supported source for ongoing usage or an equivalent live balance, without depending on the UI transport. |
| Login/unlock trigger for `PrepareOwnSession` | Expired soft-app exceptions may miss their required restoration transition. | A reliable independent trigger with the correct authentication and policy ordering. |
| [Resume estimate refresh](../../child/resumeEstimateRefresh.js) | Loses a workaround for stale native deadlines during inactivity/resume. | Which packaged versions need the workaround and whether a native fix or public external integration resolves it. |
| [Authenticated unlock continuation](../../child/sessionUnlock.js) | Loses recovery from a native exhausted-session admission race. | A native correction or supported replacement that preserves authentication and one-time request lifetime. |
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
Parent, child requests, kiosk, admission and recovery. It is the evidence needed
to claim that a migrated capability no longer requires the extension.

Current startup, PAM, Parent and kiosk recovery can re-enable the extension or
refuse an operation when activation fails. Identify every such intervention.
Disabling the extension once is insufficient: verify that it remains disabled
through the history, including login, approval and restart. An involuntary
reactivation makes the extension-free result inconclusive. An existing activation
gate may block a product experiment; record that integration gap rather than
calling it a native failure or deleting the gate to obtain a pass.

Distinguish individual extension disablement from GNOME's global extension
switch, failed extension startup and eventual absence of the extension payload.
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
| Live balance | Does uninterrupted use count correctly in both status and approval calculations, without the deadline moving forward on repeated reads? Can both request surfaces complete fixed and rest-of-day approval? |
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

## Journey through gradual migration

### Choose a complete capability slice

Use discoveries to choose the next bounded capability that can be transferred
without leaving a missing dependency. A likely early slice is application-policy
reconciliation, whose privileged implementation is already in the broker and
whose missing piece is the lifecycle trigger. Fresh timing information is a
dependency for status and fixed approvals. Expiry ownership and eventual removal
of activation gates depend on resolving the relevant timing and native-lock
questions. This is a dependency direction, not a committed execution order.

For each slice, prefer qualified native behavior first, then a native fix or
supported interface improvement, then the smallest broker or session adapter
needed for product behavior. Move product authority to the broker while leaving
native mechanisms with their existing owners. In-process Shell compatibility
hooks cannot simply be copied into a daemon; an unresolved native dependency
can prevent that slice from being migrated.

For session-entry reconciliation, build on the
[existing proposed design](BypassChallenges/Child-Disables-Extension.md) rather
than inventing a competing admission protocol. Preserve current-grant behavior,
transaction ownership, authenticated ordering and other-user isolation.

The following landmarks illustrate healthy intermediate releases. Discovery
determines their order and whether a capability needs any new broker code.
Each landmark may require smaller complete increments; none promises an
extension-free product before the final handover.

| Migration landmark | Responsibility after handover | Healthy intermediate release |
| --- | --- | --- |
| Independent session preparation | Broker reconciliation has a qualified admission/lifecycle trigger. | Required app-policy restoration no longer relies on the panel; remaining timing and lock functions still use the extension. |
| Independent live time information | Broker consumers obtain qualified native timing without the extension endpoint. | Both request surfaces and approvals work with the new data path; expiry still uses its established owner. |
| Qualified expiry ownership | Native GNOME supplies the verified behavior, with broker coordination only for demonstrated gaps. | The extension's additional expiry path can be retired without losing locking, completion observation or recovery. |
| Native compatibility dependencies resolved | Qualified native fixes or supported replacements cover resume, authenticated unlock and locked input. | Each corresponding extension workaround can be removed independently once its complete behavior is preserved. |
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

Update the complete affected call chain in the same increment. For example,
replacing the native-deadline endpoint includes the helper, broker calculations,
child estimate and approval consumers, and their failure paths. It is not
complete merely because a new endpoint exists while one caller still requires
the extension.

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

Independent request and error-report windows must survive extension disablement.
Reminder settings must remain saved; missing countdown/reminder presentation and
child-side preview must have a deliberate UI outcome. Do not clear GNOME's global
extension-disable switch as an enforcement prerequisite or silently reactivate
other extensions after a crash.

Keep extension-on and extension-off product journeys supported after this
handover. If optional installation is also offered, separate essential shared
assets from extension payload and trust requirements, and qualify upgrade/removal
accordingly. Disabled runtime and absent payload are different lifecycle claims.

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
still prevents removing extension code. Each migration decision includes its
failure policy and the complete release boundary that keeps the product healthy.

The final optional-extension release requires the installed product's core
journeys to work with the extension disabled throughout, including enablement,
accounting, both approval surfaces, natural expiry, renewal/unlock, session-entry
app restoration and recovery. Its extension-enabled path must still work, and
disabling it during use must not change policy, grants or essential app lifetime.
Only remaining convenience features may disappear.
