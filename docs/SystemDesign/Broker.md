# Broker, accounts, and authorization

[System design overview](../System-Design.md)

Read this for caller identity, D-Bus permissions, broker responsibilities,
approvals, revocation, and transaction rollback.

Implementation: [service.py](../../broker/oh_no_parent_control/service.py), [core.py](../../broker/oh_no_parent_control/core.py), [adapters.py](../../broker/oh_no_parent_control/adapters.py), [D-Bus contract](../../data/dbus-1/com.puffyslippers.OhNoParentControl1.xml), [Polkit integration](../../data/polkit-1).

## Runtime hierarchy and trust boundaries

Front ends do not read or write the private preference files. The parent reads
remaining time through the broker's `GetTimeStatus` method. The broker checks
the current caller and selected child before reading the AccountsService grant
and querying Malcontent usage under the child's own identity. This avoids a
separate AccountsService authentication requirement during periodic refresh.
Runtime product policy changes and cross-account writes pass through
the broker. The system-bus policy permits callers to reach the service; the broker,
not possession of the bus name or a client executable, is the authorization
boundary.

During the child-trust upgrade reboot guard, the same service admits
`LogEvent`, `ExportDiagnosticLogs`, `ListKioskUsers` and `GetChildLanguageContext`,
with their normal caller/target authorization and privacy checks. All other
methods return `Error.RebootRequired`. This
[diagnostics-only mode](Logging-and-Feedback.md#investigation-coverage) owns no
enforcement adapters, subscriptions or policy workers and does not claim
management readiness.

## Broker layers

The broker is divided into these layers:

- `service.py`: service construction, startup reconciliation, D-Bus dispatch,
  asynchronous approval workers, and public error translation
- `core.py`: caller roles, target eligibility, validation, time arithmetic,
  serialization of approval/revocation, and rollback transactions
- `adapters.py`: caller credentials, AccountsService, logind/systemd,
  and Malcontent timer access
- `authorization.py`: interactive Polkit checks and silent cancellation when
  the requesting connection or session becomes unavailable
- `preferences.py`: current schema, strict normalization, and atomic per-child
  storage
- `catalog.py`: launcher discovery in the selected child's XDG and system
  application directories, with native, Snap, or Flatpak target projection
- `execution_policy.py`: aggregate UID-scoped fapolicyd rule generation,
  replacement, activation, and rollback
- `app_termination.py`: UID-confined native, Snap, and Flatpak process discovery
  and termination, including desktop application scopes and their descendants
- `extension_manager.py`: safe per-child activation and runtime verification of
  the immutable GNOME extension payload
- `config.py` and `logs.py`: fail-closed machine configuration and broker-owned
  component logs
- `data_migration.py`: offline, version-stepped migration of saved application
  data before a new broker may start

## Accounts and roles

Candidate accounts are enumerated from current NSS identities so a newly
created local user can appear before first login. Accounts with a noninteractive
shell are excluded from the discovered lists. AccountsService is then the
authority for UID, local/system status, account type, lock state, display name,
and icon. The current AccountsService shell also determines interactive approver
eligibility on direct UID selection and transaction revalidation.

Discovery also excludes systemd's reserved dynamic-greeter UID range
60578–60705 before AccountsService lookup, on both supported distributions.
These transient display-manager identities are not persistent children or
approvers. After a session transition, AccountsService can retain an older
greeter object for the same name; querying it with the current NSS UID can
otherwise abort discovery and execution-policy reconciliation. Ordinary accounts
outside this range still use fresh NSS enumeration, including newly created and
high-UID accounts, and all direct lookups retain the object-path/UID checks.
See [systemd UID ranges](https://systemd.io/UIDS-GIDS/#special-systemd-uid-ranges).

An eligible child is a local, non-system, non-administrator account with UID at
least 1000, excluding the configured kiosk UID. An eligible approver is a local,
non-system, unlocked, interactive administrator with UID at least 1000 and a username safe
for the Polkit identity rule. The broker reloads these account records rather
than trusting cached front-end labels or roles.

The dedicated kiosk UID is generated into the root-owned machine configuration
at installation. It is neither a child nor an administrator and may use only
the request-station operations allowed by the broker.

The Parent App's `.desktop` entry is owned by `root:sudo` with mode `0640`,
restricting its discovery to Ubuntu administrators. The executable launcher
is separately installed with mode `0755`. Parent startup calls
`ListManagedUsers`, which rejects an ordinary child but also permits the
configured kiosk UID. Consequently `_can_start` is not an administrator-only
gate: a directly launched Parent process under the kiosk identity can pass it,
although the installed restricted session offers no such launch route.
`ListApplications`, `SetPreferences`, `SetParentControl` and
`RevokeOneTimeGrant` independently require management authorization at the
broker. Do not equate window-startup permission with policy-write permission.

Management authorization uses the live AccountsService administrator and local-account flags and
also accepts UID 0. This is distinct from approver eligibility: root is not
listed as a selectable approver, and approvers must meet all the local-account,
unlocked-account, and username restrictions above.

## Broker interface and roles

The Admin column includes UID 0 for management authorization.

`own` means that the broker derives or verifies the child identity against the
calling UID. `selected child` means a caller may supply an eligible target UID;
the broker resolves and revalidates it.

| D-Bus method | Child | Kiosk | Admin |
| --- | --- | --- | --- |
| `ListManagedUsers` | - | yes | yes |
| `ListKioskUsers` | - | yes | - |
| `ListApprovers` | yes | yes | yes |
| `GetOwnAccount` | own | - | - |
| `GetOwnLanguage` | own | own | own |
| `GetOwnWhatsNew` | own | - | own |
| `AcknowledgeOwnWhatsNew` | own | - | own |
| `GetChildWhatsNew` | - | selected child | - |
| `AcknowledgeChildWhatsNew` | - | selected child | - |
| `SetOwnLanguage` | own | own | own |
| `GetOwnNotifications` | own | - | - |
| `SetOwnNotifications` | own | - | - |
| `GetChildNotifications` | - | selected child | - |
| `SetChildNotifications` | - | selected child | - |
| `GetOwnTimeGrantPresets` | own | - | - |
| `SetOwnTimeGrantPresets` | own | - | - |
| `GetChildTimeGrantPresets` | - | selected child | - |
| `SetChildTimeGrantPresets` | - | selected child | - |
| `GetOwnSessionAllowsSoftApps` | own | - | - |
| `GetChildLanguage` | - | selected child | - |
| `GetChildLanguageContext` | - | selected child | - |
| `SetChildLanguage` | - | selected child | - |
| `GetPreferences` | own | selected child | selected child |
| `GetPolicyWarnings` | own | selected child | selected child |
| `ListApplications` | - | - | selected child |
| `GetTimeStatus` | own | selected child | selected child |
| `HasRunningSoftBlockedApps` | - | - | selected child |
| `ListRunningSoftBlockedApps` | - | - | selected child |
| `CalculateRemainingTime` | own | selected child | selected child |
| `CalculateOwnRemainingTime` | own | - | - |
| `PrepareOwnSession` | own | - | - |
| `UpdateRequestPreferences` | own | selected child | selected child |
| `UpdateRequestPreferencesWithUnit` | own | selected child | selected child |
| `SetRequestMuted` | own | selected child | selected child |
| `SetPreferences` | - | - | selected child |
| `SetParentControl` | - | - | selected child |
| `RevokeOneTimeGrant` | - | - | selected child |
| `RequestOwnAccess` | own | - | - |
| `RequestAccess` | - | selected child | - |
| `LogEvent` | child component | kiosk component | parent component |
| `ExportDiagnosticLogs` | all product logs | all product logs | all product logs |
| `GetStartupTimings` | read | read | read |

`LogEvent` is intentionally role-scoped: a front end cannot choose another
component's log, and no D-Bus caller may write the broker component log.

For the language methods, `own` means the caller's account for every role,
including the kiosk and administrators, rather than a selected child. These
methods persist only presentation intent. The child-language methods are kiosk-only
and validate an eligible child target before accessing storage; see the
[language contract](State.md).

The own-notification methods accept only eligible child callers and no target
UID. They persist personal reminder choices through the same store without
changing time limits, grants or application policy; see the
[notification storage contract](State.md#persistent-and-derived-state).

The What's New methods bind component visibility and acknowledgement to the
caller role. Administrators use their own Parent record; children use their own
Child record; the kiosk uses its selected child's Child record. Queries return
only the installed version, and acknowledgement collects deleted metadata IDs;
see the [backend contract](State.md#whats-new-backend).

`GetOwnSessionAllowsSoftApps()` is an eligible-child-only, read-only boolean
query for reminder wording. It reads live application policy under the shared
transaction lock and never writes policy or request preferences; the
[notification controller](Screen-Time.md#remaining-time-notifications) owns delivery.

`ExportDiagnosticLogs` is a separate, read-only permission for all three product
roles. It takes no arguments and returns the bounded ZIP of all four components
from the latest three available log dates. It never accepts arbitrary filesystem
paths or grants direct log-directory access. The broker rechecks the caller's
role before delivery and permits only one outstanding export. See
[diagnostic export](Logging-and-Feedback.md#feedback-and-diagnostic-export).

`GetStartupTimings` uses the same role check as diagnostic export and returns
six monotonic startup timestamps. It is a read-only technical interface, not a
parent-management operation or customer-facing timing screen. Those raw timing
values do not enter the automatic feedback report.

`SetRequestMuted` authorizes the target account as shown above and validates
`surface` as `child` or `kiosk`; it does not bind that value to the caller role.
The shared form selects its own surface. `CalculateRemainingTime` validates
caller-supplied arithmetic operands and returns a calculation; it does not
authorize or write a grant.

## Authorization and grant transactions

Time grant preset customization uses the child-owned and kiosk-selected-child
permissions described in the [preset backend](State.md#time-grant-preset-backend).
These personal-setting APIs persist editable durations without changing active
grants, AccountsService policy or the approval transaction.

The kiosk's forked MATE agent can finish systemd startup before registering with
PolicyKit. With interactive authorization enabled, an unfulfilled challenge
(`authorized=false`, `is_challenge=true`, no dismissal) permits the same kiosk
check to be retried every 100 ms for at most five seconds from its initial
dispatch. This follows the ordinary PolicyKit
[interactive authority result](https://github.com/polkit-org/polkit/blob/main/src/polkitbackend/polkitbackendinteractiveauthority.c):
completed authentication clears the challenge flag. Approval, rejection,
dismissal and D-Bus errors are terminal; the child overlay does not retry.
The original worker, transaction lock, subject, selected identities and lifecycle
subscriptions remain in force. Lock, session loss or caller disconnect cancels
the wait, and an active retried check uses the same remote cancellation path.
This is checkout-covered startup handling; real native-agent readiness and
translated approval remain part of task 300's pending installed acceptance.

`RequestAccess` is restricted to the configured kiosk UID.
`RequestOwnAccess` derives its target from the child caller, and rejects a child
whose screen-time control is disabled. Both paths validate the requested
duration, approver, target, and saved preference snapshot before invoking a
dedicated interactive Polkit action.

The broker supplies the selected administrator username as an action detail.
It also supplies the complete product-owned approval message through PolicyKit's
supported [`polkit.message` detail](https://polkit.pages.freedesktop.org/polkit/eggdbus-interface-org.freedesktop.PolicyKit1.Authority.html).
The GTK-independent shared gettext loader uses the signed-in child's saved
language for child requests and the selected child's saved language for kiosk
requests. Message operands come only from broker-validated request data. Duration
units and plurals, rest-of-day and optional soft-app access are translated across
the supported catalogue. The account label stays in `target-account`, expanded
once by PolicyKit after translation so user data is not interpreted as properties.
Empty/unsupported selections and missing entries preserve the shared loader's
English fallback without consulting the root service locale. Agent-owned
authentication labels, buttons and errors retain their normal session language;
see [localization ownership](Localization.md#responsibilities-and-language-ownership).
The installed Polkit administrator rule restricts the challenge to exactly that
identity, so the standard agent shows one password prompt without a second
identity-selection page. The action uses `auth_admin`, implies no AccountsService
permission, and retains no reusable authorization in either front end. The
kiosk session runs the maintained MATE Polkit agent as a restartable user
service; agent failure denies the in-flight attempt without permanently ending
the request station.

Pending authorization belongs to the requesting bus connection and its logind
session. The broker resolves the process's session, falling back to the owning
user manager's primary graphical `Display` for apps launched as user services,
as Polkit does. An already locked/inactive/closing session cannot start a prompt.
While a prompt is pending, the broker watches that session's lock, activity,
closing/removal events, loss of logind, and disappearance of the original bus
name. These cancel only that request through Polkit's public
`CancelCheckAuthorization`, using the original broker connection and cancellation
ID. The local GIO wait is cancelled as well; a late approval cannot revive the
request. Authentication otherwise remains user-driven without an idle timeout.
Sessionless callers with a bus-registered agent retain disconnect cancellation.

Agent Cancel is identified by the nonempty `polkit.dismissed` detail in
Polkit's public authorization result. Its `is_challenge` flag describes whether
authentication could authorize the subject and is not a cancellation signal.
Cancellation returns the existing `cancelled` result, which both shared request
interfaces handle silently. Logs include the random request correlation ID,
fixed cancellation reason, and remote cleanup result, without account names,
session IDs, bus names, or authentication details. The broker releases its
transaction lock after the local wait finishes and remote cancellation completes
or reaches its five-second cleanup deadline, allowing a new kiosk request.
Account writes and the successful-request cooldown are not reached by a cancelled
authorization. This broker-only change activates at `process-restart`; there is
no D-Bus contract, Polkit policy, or saved-data migration change. See the
[lockout regression](../../tests/component/test_authorization_lifecycle.py).

An approved request initializes `DailyLimit` from saved preferences and enables
Malcontent limits if necessary before applying the filter and grant. Unlike the
child request, the kiosk request does not require `parent_control_enabled` to
be true. It does not change that saved toggle or activate the child extension.
Both installed request forms nevertheless disable submission when that toggle
is false. This UI guard is narrower than the kiosk D-Bus method's authorization.

After approval, the broker confirms that the requesting bus name still exists
and revalidates the child, approver, and preferences after authentication,
after the identity-scoped usage query, and immediately before writes. A
nonblocking broker lock permits only one app-policy save, approval, revocation,
or session-entry reconciliation transaction at a time. The per-caller repeat
interval is recorded only after a successful grant, so denial or cancellation
does not consume it.
The shipped interval is five seconds and is keyed by the requesting UID in
broker memory. All children selected by the same kiosk therefore share its
cooldown; different child callers have separate entries. Broker restart clears
this transient history. The check runs before the authentication prompt.

`SetParentControl`, both request-preference methods and `SetRequestMuted` do not take
that shared lock. The parent serializes its own saves, and approval checks for
stale preferences, but the lock is not a blanket serialization guarantee for
every settings write or independent client.

For a request that keeps soft blocks enabled, the broker writes and verifies the
complete hard-and-soft filter, terminates matching apps owned by the selected
child, and writes `ActiveExtension` last. Native and Snap processes are pinned
with pidfds and signalled only after all four kernel-reported UIDs match the
child. Snap processes additionally match the kernel-applied
`snap.<instance>.<app>` AppArmor security label rather than the transient
executable path inside a mounted Snap revision. Flatpak instances are
enumerated and killed by instance ID using the child's
UID, primary GID, empty supplementary groups, and runtime directory. Every live
session for that UID is in scope; another user's process is never signalled.
When soft blocked apps are allowed, the broker installs the hard-only filter and
does not terminate any open process, including an already-open hard-blocked app.

Parent revocation uses the same process-ownership boundary. It restores and
verifies the complete filter, terminates matching apps for the selected child,
and clears `ActiveExtension` last. No active-grant precondition is required:
revocation can reconcile strict policy with a zero or expired grant and leaves
the daily allowance untouched. Reversible failure before termination
restores the complete old account state. Once termination may have changed a
process, that side effect cannot be rolled back; failure instead restores the
old time values, keeps the strict filter active, and reports the failure. A
rollback read-back failure is reported distinctly.

`HasRunningSoftBlockedApps` is an administrator-only read for an eligible child.
It resolves saved soft-block targets and patterns through the same native,
AppImage, desktop-scope, descendant, Snap and Flatpak discovery as termination,
without signaling or changing policy. Parent queries it when remaining time is
zero and refreshes the result with time status every 30 seconds and after
revocation. A positive result enables Revoke even in a locked child desktop.
The broker and Parent changes load on process restart; no data migration is
required.

App-policy save rollback has a different persistence boundary: before termination,
failure restores the old preference record and filter; once termination starts,
failure keeps the requested preferences and strict filter. Session preparation
also keeps strict policy once termination starts and does not modify the grant.
Account read-back and successful fapolicyd compile/reload commands are the current
verification boundary. There is no active-generation acknowledgement in the
production adapter; see [notification recovery](Applications.md#notification-recovery-and-acknowledgement-limit).

### Prospective kiosk approval lifetime

**R01c decision, prospective:** keep cancellation effective until a single broker
effect-admission point immediately before the first policy write. Authentication
success alone does not cross it. After admission, only that original approved
request may finish despite departure, under the existing transaction and rollback
rules. The [specification](../Specification.md#prospective-kiosk-visit-lifetime)
owns the visible result. R01 integrates and independently reviews this decision
in the [integrated contract](Kiosk-Confinement.md#r01-integrated-admission-contract);
no implementation or installed acceptance is claimed here.

#### Audited implementation gap

Current `_PendingAuthorization.run()` watches the sender and session only through
authentication. `_authorization_finished()` sets `auth_done`, after which
`_cancel()` ignores transitions; `run()` then removes its subscriptions.
`_request_access()` subsequently performs the approver-scoped usage query (up to
30 seconds), account/preference revalidation, running-app preflight and `_apply()`'s
four account snapshot reads before its first write. Its caller check is only
`CallerCredentials.alive()` / `NameHasOwner`, not continued visit activity.
Extending subscriptions without replacing the authentication-only latch would
therefore leave the same gap. The usage helper's separate bus connection and
approver credentials are data-query authority, never the originating visit.

`_session_for_caller()` resolves system-bus sender PID through `GetSessionByPID`.
Only `NoSessionForPID` falls back through `GetUserByPID` to `User.Display`; an absent
user or empty display permits a sessionless check today. It pins neither process
start identity nor agent generation and does not watch later display changes.
These current limits and the existing cancellation regression remain historical
facts; this decision changes no source, tests or their expectations.

#### Visit, requester and agent association

Use the following broker-owned, in-memory association on both platforms. The
native privileged entry gate registers the admitted session over authenticated
system D-Bus; the broker independently reads its logind and manager identity.
Only that protected gate may create an admission record. The fixed lifecycle
controller from [R01a](Kiosk-Confinement.md#r01a-execution-and-activation-decision)
may operate its own admitted visit through narrowly authorized lifecycle calls;
neither a form-supplied token nor the shared kiosk UID establishes ownership.
These are proposed internal interfaces, not existing D-Bus methods.

Distinguish the gate-created **session admission record** from an active **visit**.
Keep that record only while its exact logind session and pinned infrastructure
remain owned and live; invalidate it on session removal, service-owner loss or
infrastructure replacement. Lock/switch-away ends the visit, not necessarily the
logind session. On return, the pinned controller asks the broker to reactivate
that retained record: independently revalidate the original session, drain old
work and create a fresh visit ID and form/agent generations. No second PAM/login
gate is assumed when switching back. A new login needs a new gate-created record.

| Binding | Authority and lifetime |
| --- | --- |
| Originating visit | Broker-issued random visit ID plus boot identity, logind unique owner, exact session ID/object path, kiosk UID, seat and session leader process/start identity. Verify a local dedicated graphical kiosk session. A lock, loss of activity, closing/removal or loss of logind ends that activation permanently; return to the same logind session creates a new visit ID. |
| Infrastructure and controller | Pin the owned manager's systemd `InvocationID` and controller process/start identity. Reuse of a healthy manager creates no reusable visit authority. Renewal or controller replacement invalidates old unadmitted requests; new infrastructure requires a new admission association. |
| Requester | Capture the original unique system-bus name, bus instance, kernel-derived UID/PID and process start identity; verify the fixed form's owned unit and confined role. A new connection/process cannot inherit the binding. Form callbacks carry the local visit/request generation and discard results from any earlier generation. |
| Request and selected accounts | One random correlation/cancellation ID, request kind, target and approver account snapshots, duration, soft-app choice and non-personal preference snapshot. Retain existing eligibility and snapshot revalidation; never replace a vanished approver, target or sender with the current selection. |
| Authentication agent | Pin the fixed agent unit's `InvocationID`, `MainPID`/start identity and its association with the exact admitted logind session. The confined graph permits only this agent role to register kiosk authentication agents, including process-scoped registrations; a foreign registrar is a conflict, never an object to unregister or kill. A new visit starts a fresh owned agent even when the manager is reused. |

Use public [logind session/user interfaces](https://www.freedesktop.org/software/systemd/man/259/org.freedesktop.login1.html)
and [systemd unit/service identities](https://www.freedesktop.org/software/systemd/man/259/org.freedesktop.systemd1.html).
For manager-launched form/agent processes, allow `User.Display` fallback only
when it equals the gate's exact admitted session and that session still meets
the activity/ownership checks. Subscribe before reading, reread after association,
and watch that user's display and service-owner changes through effect admission.
A missing, changed, ambiguous or foreign display cancels the affected attempt;
never resolve it again to adopt a later session. The kiosk route has **no
sessionless fallback**. Ordinary child/sessionless callers retain their existing
contract; narrowing kiosk admission does not remove their bus-agent support.

Keep the stock MATE agent and its vendor privileged authentication helper.
The [agent's startup](https://github.com/mate-desktop/mate-polkit/blob/master/src/main.c)
resolves its process's session before public
[Polkit registration](https://polkit.pages.freedesktop.org/polkit/PolkitAgentListener.html).
Serialize startup with the visit association and stable `Display`; no other
kiosk visit may register/start a competing form or agent in that manager.
Before reusing the fixed agent unit, cancel/drain old requests and prove the old
owned agent process and its bus connections have ended. Pin the new unit/process
before requesting authentication. A completed systemd job or `Type=simple`
process is only startup evidence, not proof of successful registration. The
genuine selected-parent Polkit exchange establishes operational authentication.
Under the [revised observable timing boundary](Lifecycle.md#one-measured-entry-and-recovery-budget),
automatic preparation and dispatch/retry consume the original readiness budget
and retain the same visit/agent pins. A dispatched native exchange remains
user-driven, with lifecycle cancellation and no new idle timeout; pending time
is not proof of prompt visibility or human waiting. An unfulfilled returned
challenge may retry only with remaining budget. Never retry approval, dismissal
or denial as startup. Installed acceptance independently observes the actual
prompt within the end-to-end bound; no job or pending call qualifies it.
Do not invent a registration-enumeration API, use log text as readiness, or
substitute a password collector/probe. R02a–R04 must prove the shipped agent's
session association and actual prompt on each platform, including the absence
of a process-scoped competing agent. A registration conflict preserves the
foreign instance and offers retry/exit after the conflict is resolved.

Locale preparation uses the fixed controller's validated locale-only launcher,
with visit and agent generation on each callback. Freeze agent replacement while
authentication or post-authentication checking is pending; agent death, unit
replacement or Polkit owner loss cancels that unadmitted request. A recovered
agent requires a fresh request/authentication; it cannot resume the old check.
R08b owns translation fallback, not a relaxation of these identity checks.

One admitted live logind session owns the kiosk UID/user manager globally at a
time, including across seats; seat identity never creates another owner. A competing
login waits under R01e's single entry deadline for normal release, then either
starts its own new visit or returns to sign-in with an already-open/retry result.
It cannot attach to an old prompt, steal the manager or terminate a healthy or
foreign session. Returning to the same session after switching away creates new
form/agent generations after old cancellation cleanup. Physical infrastructure
renewal, interruption recovery and the numeric deadline remain R01e/R06a's scope.

#### Cancellation versus effect admission

The broker owns one monotonic request state machine:
`authenticating → checking → committing → finished`, with
`authenticating/checking → cancelled` terminal for authority. Authentication
approval enters `checking`; it does not make later cancellation a no-op.
Keep a dispatching lifecycle observer alive while the worker performs blocking
usage queries, preflight and account reads. It must not depend on the blocked
worker pumping its old authentication loop.

Observe sender/process loss, visit/controller/manager/agent replacement, logind
or Polkit owner loss, session lock/inactivity/closing/removal and fallback-display
change. Before admission any such event permanently cancels the request. Cancel
pending Polkit remotely with the original broker connection/cancellation ID and
locally with GIO, retaining the existing five-second remote cleanup limit. After
authentication, discard the outstanding read result; no new remote check or
reusable authorization is created. Keep the transaction slot until owned work
has drained or its maintained timeout has ended; then release it for a fresh
request. Cancellation causes no policy writes, app termination or success
cooldown; already-saved request choices need not be rolled back.

Perform usage/calculation, termination preflight and **all four reversible account
snapshot reads** while still cancellable. Revalidate the bound caller, accounts,
preferences, visit and service generations after those slow operations. Complete
a fresh read of the pinned session/display state and dispatch queued lifecycle
events before requesting admission. A short broker-owned state lock orders
cancellation against `checking → committing`; it performs no blocking I/O and
claims the transaction exactly once, immediately before its first possible write.
No usage query, preflight or snapshot reads may be deferred until after this
claim. Apply the same gate to rest-of-day, which has no usage query.

This is a broker ordering boundary, not an atomic transaction with logind:
already observed cancellation or an unavailable final read wins; a transition
first observed after the claim is ordered after it. The controlled histories
below must establish which event won, rather than infer it from a hidden prompt,
wall-clock timing or bus-name survival. Near-simultaneous external events are
reported according to that observed order, never described as a global instant.

Once `committing` wins, departure, disconnect or agent teardown does not retract
the accepted transaction. Finish only the original immutable request, retaining
the broker transaction lock through completion/rollback. Apply existing daily
limit/type, filter, verified child-only termination and `ActiveExtension`-last
ordering. Preserve all current calculation timestamps, grant arithmetic,
eligibility checks, rollback and failure reporting: admission is permission to
attempt the transaction, not a success receipt. Before termination failure
restores reversible state; after termination may have changed processes, keep
strict filtering and restore prior time state. Record cooldown only on success.
Do not replay an in-memory approval across broker restart or infer a successful
grant after a crash. R01e owns infrastructure recovery; current failure limits
remain explicit. An old reply goes only to its original connection/generation;
a later visit can observe the child's actual balance but receives no old success
screen, prompt or authorization. A fresh request waits for transaction/cleanup
release and, after original success, the existing kiosk cooldown.

#### Finite implementation and acceptance handoff

R02a implements the identity/observer/admission slice; R06 composes renewal and
competing visits. R09b2 registers the following complete histories for R10c2 and
R11c2 on their respective targets. Selectors remain **unimplemented**. Preserve
each request, transition, late-result release, independent grant observation,
fresh approved request and restoration in one attempt.

| Ordering control | Required result |
| --- | --- |
| Authentication still pending; switch/exit, then reenter; release a late authentication result | Original request is cancelled, with no grant/policy/app effect or success cooldown. New visit adopts no prompt/result. Fresh genuine approval succeeds. Include return to the same logind session, not only a new login. |
| Authenticate; hold the fixed-duration usage query; switch/exit and observe cancellation before releasing the query; reenter | The released query/result cannot cross admission. Original policy/grant remains at its baseline and its apps are not terminated; fresh approval succeeds after drain. Repeat bounded engineering controls with delay in preflight/snapshot reads and rest-of-day to cover the other pre-write gaps. |
| Authenticate; delay and release usage while the visit is active; observe admission; hold immediately after the claim and before the first write; switch/exit and reenter; release completion | The original request may complete once for its original child, duration and soft-app choice, even with its form/connection gone. Independently observe its actual grant/filter/app result before submitting a fresh request. No old UI result or authority is adopted; fresh genuine approval succeeds after transaction release and successful-request cooldown. |

Delay/release and phase witnesses are engineering controls; no public action
exposes them. Observe the original child's grant through a separate Parent view,
and permitted/blocked app behavior for the selected soft-app choice; do not use
prompt disappearance as the grant oracle. Capture the baseline and original
result before the fresh request can replace it. Include a successful permitted
control after cancellation, agent replacement, display change and competing
visit; preserve other users' apps and live/foreign sessions. Engineering failure
controls on each side of termination retain existing rollback assertions and
must not relabel a failed transaction as cancellation or success. R01c itself
accepts only this source-grounded decision and documentation consistency, with
no runtime state; R01's integrated contract records the architecture review.

## Related design

- For grant arithmetic, read [calculations and usage identities](Screen-Time.md#grant-arithmetic-and-usage-identities); for screen-time activation, read [enablement](Screen-Time.md#screen-time-model).
- For termination matching, read [running application identity](Applications.md#running-application-identity); for expired grants at login/unlock, read [session reconciliation](Applications.md#session-entry-reconciliation).
- For preference fields being written, read [State](State.md).
- For file-log handling, read [Logging and feedback](Logging-and-Feedback.md#logging).
