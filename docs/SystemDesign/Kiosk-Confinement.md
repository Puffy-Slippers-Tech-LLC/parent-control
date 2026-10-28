# Kiosk confinement

The dedicated request station lets a child request time through genuine parent
approval without receiving an unrestricted desktop, terminal, launcher or
management session. Its package-created account is separate from the child's
desktop, governed by [Screen time](Screen-Time.md) and
[Application policy](Applications.md).

## Security boundary and assumptions

The attacker is a technical non-administrator child using exposed station actions
and ordinary local/remote session routes, with files prepared in their own account.
Kernel/trusted-service exploits, stolen administrator credentials, administrator
policy changes and booting another OS are outside this boundary. Root-planted
engineering fixtures do not establish a reachable child action.

The trusted base includes the kernel, root-owned package/distribution code, PAM,
systemd, GDM, AccountsService, Polkit and installed Python/GTK/GI with normal lazy
loading. Packaging targets Ubuntu 26.04/GNOME 50 and Fedora Workstation 44/GNOME 50;
the [overview](../System-Design.md) owns release qualification.

Usable passwordless entry, genuine approval and ordinary-account continuity are
requirements. Unrelated software, cosmetic variation and valid host layouts must
not create avoidable admission vetoes. Rejecting a supported use remains a blocker.
Unsafe fixtures must separately prove that isolation failure never grants
unrestricted access. Explicit administrator denials remain authoritative.

### Usability priority and reasonable child effort

Product usability is the highest priority. Unexpected machine configurations must
not break passwordless sign-in, the request form or core end-to-end use. Every
protection-caused failure needs a concrete intentional breach effort: the child's
actual access, deliberate action, prohibited result and a matching working
normal-use control. Unfamiliar files, services, package versions or configuration
alone supply no justification; an unjustified protective failure is a product bug.
Genuine parent denial and explicit administrator policy remain authoritative.

Review ordinary session selection, shortcuts, TTY/terminal, SSH,
exposed links/choosers/handlers and child-writable consumed inputs. Do not assume
arbitrary kiosk-UID execution, compromised trusted packages/root, expert native
loader chains or kernel/boot/firmware exploitation. Supported installed code,
normal lazy loading and ordinary package/account administration need no private
product protocol, custom runtime, private GI/graphics image, continuous library
audit or per-import authority protocol. Engineering injections remain separate
from customer acceptance. Optional presentation/service failures cannot veto core
use; essential outages require safe retry/exit without unauthorized access.
Human time choosing language, reading, deciding or authenticating is not startup
time.

## Admission and account integrity

[Provisioning](../../tools/provision.py) creates the non-administrative reserved
account with `/usr/sbin/nologin`, a recorded numeric UID and owned home.
Public AccountsService properties select the dedicated Wayland session and
visible/saved classification. The station cannot change its own metadata through
Polkit. Provisioning verifies initial routing; optional artwork cannot veto it.

Fresh creation starts with no expiry and a locked password. After UID publication,
configuration journals original expiry and quarantines the account before deleting
the password. Reconfiguration uses the same UID-bound transaction; interruption
and reboot retain quarantine. Foreign identities/changed records refuse adoption.
Successful native/distro PAM readiness permits expiry restoration.

The [native PAM module](../../tools/pam_oh_no_parent_control.c) checks actual service
and account. The qualified child-run `su-l` route is denied; unfamiliar service
names use the existing account/session checks. GDM account/session checks
validate the reserved identity without consulting saved routing or session type.
Missing/unsafe state and persistent contention deny entry. Shared root-owned no-follow
admission leases persist through PAM teardown, excluding exclusive lifecycle
writers but not competing logins. They require read access only because GDM and
user-manager SELinux write authority can differ.

[Distro PAM integration](../../packaging/distro_pam.py) uses Ubuntu
`pam-auth-update` and Fedora's owned authselect transaction. It verifies finite
product authentication/account blocks, skip destinations and runtime-cap hook;
unrelated vendor text remains opaque. Ordinary accounts retain authentication,
administrator denials and time policy.

Saved preferences and a nologin shell do not attest to GDM's actual next executable.
Desktop/session-choice, TTY and SSH routes retain separate prevention and public
qualification obligations. Remote desktop testing was removed from active scope
by the developer; no remote acceptance is claimed. Account-only probes and host
composition cannot establish usable passwordless graphical entry.

<a id="c02-activated-session-baseline"></a>
<a id="c02a-prepared-session-runtime"></a>
<a id="c02c-prepared-native-and-distro-pam-integration"></a>

## Native execution and executable identity

The Wayland session directly starts distribution
`gnome-session --session oh-no-parent-control` and GNOME Kiosk.
Isolated Python entrypoints run the shared form and notifications; the vendor
authentication agent retains its public systemd identity. App exit/failure requests
session shutdown. Reading, choosing language and authenticating have no idle deadline.

Native PAM owns account/session admission, ordinary time/runtime-cap behavior and
the lifetime lease. There is no private mount image, role dispatcher,
required-material inventory or preparation-service admission path. Fixed native
Wellbeing and package-diagnostic wrappers remain feature helpers: ordinary users
retain their environment for Wellbeing; package queries use a finite vendor command.

### Compatibility and recovery boundary

Exclude demonstrably child-controlled inputs at their actual selection boundary;
a write bit alone does not establish child control. Trusted vendor helpers,
unrelated ambient siblings and valid local PAM variation have no admission vote.

Optional presentation failure must preserve the core form and genuine approval.
Essential-service/enforcement outages require safe retry/exit and useful original
diagnostics. Recovery preserves live/foreign sessions and never replays approval.
Human language selection, reading and authentication consume no machine-startup
budget. [Lifecycle](Lifecycle.md#compatibility-and-recovery-boundary) and
[Localization](Localization.md#native-authentication-fallback) retain availability
and fallback limitations.

<a id="c01b-feature-and-approval-source-lineage"></a>
<a id="c02b1-prepared-broker-approval-boundary"></a>
<a id="c02b-shared-form-and-agent-boundary"></a>

## Roles, services and dialogs

The selected [app](../../data/systemd/user/oh-no-parent-control-app.service),
[agent](../../data/systemd/user/oh-no-parent-control-polkit-agent.service) and
[notification](../../data/systemd/user/oh-no-parent-control-notifications.service)
units serve the session. Polkit authenticates the selected parent; product forms
never receive passwords. The stock agent retains its vendor privileged helper.
Locale restart-job completion alone does not prove native agent registration.

[Broker](Broker.md#authorization-and-grant-transactions) owns authorization,
cancellation and grant effects. The shared form retains language, Preferences,
duration controls, artwork, What's New, reports and child-overlay behavior.
About, editors, privacy and reports stay in-app. Kiosk mode suppresses external
handlers, file choosers, management controls and arbitrary launches.
[Front ends](Frontends.md) and [Logging](Logging-and-Feedback.md) own those features.

<a id="c02c1-prepared-account-provisioning"></a>
<a id="c02c2-prepared-owned-lifecycle-migration"></a>
<a id="c04a1-first-configuration-interruption-inputs"></a>
<a id="c04a2-removal-and-recovery-records"></a>
<a id="c04a3-pam-variation-histories"></a>

## Installation, updates and removal

[Owned migration](Lifecycle.md#prepared-owned-lifecycle-migration) binds
configuration, legacy retirement, quarantine and retry to verified identities.
PAM leases exclude exclusive migration/removal.
[Activation](Lifecycle.md#package-activation-and-session-renewal) determines actual
restart/session/reboot requirements; ambient variation alone requires no reboot.

[Package removal](Package-Removal.md#pam-and-kiosk-ownership) preserves live/foreign
state, publishes durable denials before erasing payload, verifies UID/home ownership
and restores only owned integration. Ordinary removal retains preferences/logs;
purge follows its own cleanup boundary.

<a id="c04a-installed-engineering-dispositions"></a>
<a id="c04a-completed-host-acceptance"></a>
<a id="c01c-automation-and-package-consumer-lineage"></a>
<a id="c03-shared-form-and-cumulative-host-automation-alignment"></a>

## Offense and defense scenarios

The following stable engineering bindings preserve the meaning of incoming
contract references; the registry owns executable status, not these aliases.

| Binding | Scope and limit |
| --- | --- |
| 267, `verify_session_composition` | Current account/routing, finite PAM and shipped GNOME Kiosk definitions; no execution fence. |
| 268, account admission | Identity admission, saved-routing tolerance, `su-l` refusal, restoration and ordinary-account positives; no authentication, graphical entry or remote-route proof. |
| 271, ordinary integration | Current vendor execution, distro readiness and invocation-owned manager cleanup; no private namespace/generation/mask assertions. |
| 269 | Pending reachable startup/audio input protection with ordinary-use controls. |
| 289 | Pending real dependency update, retained use, normal exit and fresh-entry history. |
| 290, 293 | Pending usable repeated entry with unrelated writable siblings/ambient host replacement; former private-view workers removed. |
| 291 | Pending essential-service interruption/recovery; it is not a consumed-input protection binding. |
| 294 | Pending owned interrupted-state recovery preserving foreign/live sessions. |
| 270, 292 | Retired private namespace-callback and native bootstrap/loader matrices; ordinary PAM behavior survives in 268/271. |
| 10 | Retired private MAC-unload witness; quarantine/finalization recovery survives in removal cases 9/11. |

First-configuration interruption/reboot/retry, removal ownership/finalization and
PAM variation histories retain their current lifecycle records and ordinary-user
controls. Exact case identities and registrations remain in the
[system registry](../../tests/integration/system_case_ids.py); pending/retired
identities must not acquire accidental executable registrations or be reused.

Required public outcomes include dedicated-session routing, terminal/SSH and
alternate-desktop denial, genuine password denial/Cancel, selected-child-only
grants, safe close/return to sign-in and in-app reports without unsolicited
submission. Reachable startup/plugin/helper inputs and exposed service launches
require route-specific review with permitted-use controls.

Engineering composition reads verify account/routing, finite PAM integration and
shipped definitions. The shared census reports `session-identity-only` and
`confinement_qualified: false`. Account-only PAM probes do not prove authentication,
graphical entry, session callbacks or enabled remote routes. Ordinary-account
checks retain vendor execution and owned restoration. None establishes arbitrary
code containment or coverage of every route.

Dependency-update/reentry, ambient variation, essential-service recovery and
interrupted-state histories retain distinct obligations. Unknown valid host content
must not force refusal/reboot. Historical private namespace, role, loader,
material/view and generation mechanisms are retired and have no admission authority.
Stable test identities/status remain in their inventories; removing a mechanism
does not permit ID reuse or erase required customer outcomes.

<a id="c01-selective-replacement-boundary"></a>
<a id="c01a-session-source-lineage"></a>
<a id="c02d-native-and-runtime-source-cleanup"></a>
<a id="c02e-feature-protocols-and-package-source-cleanup"></a>
<a id="c03a1-native-runtime-host-test-reconciliation"></a>
<a id="c03a-native-and-package-host-test-reconciliation"></a>
<a id="c03b-approval-and-broker-host-test-reconciliation"></a>
<a id="c04c-proof-and-design-consumer-reconciliation"></a>
<a id="current-session-confinement-rebuild"></a>
<a id="r01-integrated-admission-contract"></a>
<a id="accepted-mapping-of-legacy-assertions"></a>

## Selected source boundary

Only session confinement derives from the pinned v1.3 release
`188be907c46b1cd0dabae06ac898c43e75beb05e`. Main's shared form, broker approval,
language, reporting and other product features remain current; whole release
files are not substitutes for that selective boundary.

The selected owners are public GNOME session/app/agent/notification units,
provisioning, native/distro PAM and owned lifecycle migration. Former native
headers, private runtime/material/view/preparation modules, confinement loader,
compositor/audio overrides and PreSession hook are removed from the runtime and
payload. Fixed historical migration data preserves restoration authority without
recreating a selectable old mechanism. The mixed native wrapper retains only
Wellbeing and bounded package-diagnostic feature consumers. Current direct
request/approval/cancellation APIs are preserved; no controller/visit-token API
is selected.

## Admission defaults and recovery

Default to passwordless access to the restricted request app. A protective
rejection needs a specifically recognized deliberate breach pattern, with actual
child control, a reachable action, a prohibited result and a working normal-use
control. Unknown files, packages, service names, saved preferences, discovery
failures and lock contention are not attack patterns by themselves.

For each protective predicate, document its caller/input, narrow enforcement
point, recognized-attack negative, normal-use positive, benign adjacent or unknown
configuration, recovery and target applicability. Prefer an action-level barrier
over rejecting an entire session. Genuine parent/admin denial, identity checks,
same-handle PAM authorization and foreign/live-state ownership remain authoritative.
Never turn a PAM error into success, enable global null-password authentication,
fabricate a grant or fall back to an unrestricted desktop.

### Service and routing boundary

Native PAM and the login helper validate the reserved NSS identity, not a
catalogue of familiar services or saved desktop choices. The specific reached
`su-l` route is denied; unfamiliar service names retain ordinary identity and
ownership checks. The helper receives user, service and fixed PATH, with bounded
execution and distinct failure mapping. Missing service and malformed PAM state
remain operational/API failures, not evidence of an attack.
After a temporary helper/NSS failure, restore the authoritative dependency and
retry entry; the failure never substitutes for a successful identity check.

Saved session/type and `XDG_SESSION_TYPE` have no admission vote. Provisioning
owns initial AccountsService routing; login does not query or rewrite it.
Stale alternate/empty/`x11` preferences and routing-discovery outages must not
veto actual dedicated Wayland execution. Saved defaults and command resolution
alone do not identify the program GDM ultimately starts.

### Lease and lifecycle boundary

Native admission opens shared leases read-only and no-follow, retains them through
`pam_end`, and rechecks inode, ownership, mode and removal barriers. Fedora GDM
and user-manager SELinux contexts differ; shared descriptors need no write access.
Active lifecycle writers exclude admission, and live admissions exclude writers.
Fresh admission retries a busy shared lock for at most two seconds on the same
read-only descriptor. Only lock contention is retried; other lock failures deny
entry. After acquisition, the existing inode, ownership, mode and removal-barrier
checks still apply. A writer that stays active through the deadline denies entry;
no stale state is removed or adopted by this wait.

Lifecycle `barriers` can repair a safe stale admission mode only after exclusive
locking, fresh regular-file/owner/single-link checks and named-inode equality.
It changes the locked descriptor to 0600 without replacing it. Legacy leases
remain strict; foreign, writable, linked or live state must not be adopted.
Lifecycle labeling applies only to the verified exclusively held inode.

Removing state is published before its marker; completion erases the marker
before state. A marker without authoritative state is unowned and cannot be
deleted merely because no lock is live. Recover valid interrupted owned state
through the configuration writer, preserving capture/rollback authority.

Benign optional variation must preserve entry and approval. Required-service,
routing and owned-lock faults need bounded retry or safe owned repair; restored
dependencies must permit fresh passwordless use without reinstalling or manually
deleting product state. An essential outage can prevent a request, but cannot
count as working use or successful attack defense. The app requires the system
bus; locale/agent failures and shared-service failures retain the availability
limits in [Localization](Localization.md#native-authentication-fallback) and
[Lifecycle](Lifecycle.md#compatibility-and-recovery-boundary).

## Local desktop boundary

The prohibited result is a usable full graphical desktop as the station account,
with normal launch controls. An ordinary account's desktop, blank compositor,
missing dependency or generic failed login does not establish that result or a
successful defense. Retain effective supported mechanisms; add a barrier only
for a demonstrated reachable gap at its narrowest owner.

### Graphical session selection

AccountsService saved choices and the station's nologin shell do not constrain
GDM's actual selected command. GDM prefers the current greeter selection over the
saved default, resolves the desktop file and passes its command to the session
worker after PAM. The login shell becomes an environment value rather than the
graphical launcher. Chooser cancellation resets GDM's selection.

Native PAM receives no selected-command input. Do not infer a desktop barrier
from `PAM_SERVICE`, saved routing or `XDG_SESSION_TYPE`. Public chooser
reachability and independently observed execution are separate requirements.
A station chooser unexposed during normal passwordless entry is a finite no-route
disposition, not denial of a selected alternate executable or a universal fence.
Do not manufacture reachability with authentication delay, privileged greeter
selection or saved-routing mutation.

### Request-session actions

| Boundary | Mechanism and required permitted use |
| --- | --- |
| Desktop shortcuts | `Kiosk=true` selects GNOME Kiosk rather than full Shell. Vendor handling neutralizes menu/run actions. Check Super, Super+A, Alt+F2 and Ctrl+Alt+T separately with corresponding working ordinary-desktop controls; no universal shortcut claim follows. |
| About, Help and What's New | Kiosk omits Help and disables external links while retaining readable, dismissible in-app information. The child overlay keeps permitted links. |
| Error reports and editor | Kiosk hides and guards attachments/download choosers, keeps Privacy in-app and rejects external editor navigation/new windows. Parent attachments and export remain available. |
| Preferences, reminders and language | Notification actions are dismiss/fixed Preferences only; previews supply no arbitrary launch action. Locale preparation restarts only the fixed vendor authentication-agent unit. Preserve useful dialogs and genuine selected-parent authentication. |
| Cancel, Escape, result and app exit | Public GNOME logout has a bounded 750-ms handoff with app-quit fallback; app success/failure requests session shutdown. Return to GDM and fresh usable entry, with no desktop fallback. Authentication denial/Cancel grants nothing. |

Standalone terminal/TTY, SSH and other exposed actions/consumed inputs retain
their distinct confinement obligations. Remote-desktop testing is excluded;
no remote acceptance or all-provider protection is claimed. Trusted-code
compromise and arbitrary station-code execution remain outside the threat model.

### Bounded confinement usability check

A confinement change must preserve fresh passwordless entry, a usable request,
genuine parent approval with independently observed intended results,
denial/authentication Cancel without a grant, normal exit and fresh usable
entry/request. Require the affected candidate on both Ubuntu and Fedora.
Seeing a window or passing an account-only PAM probe is insufficient.

Add ordinary-account login for shared PAM/session changes, a shared-overlay
request if that caller changes, and representative public time/soft-app/hard-block
controls if authorization or enforcement can change. Cover directly affected
benign/fault boundaries with finite representative inputs. Keep injected errors
and installed engineering probes separate from public usability after restoration.
Required-service recovery must never replay approval.

For an availability repair, select one finite fault and its supported recovery
action. Entry/lifecycle repairs follow the entry/approval/exit/reentry history
above after restoration; request-only repairs need one entry and the affected
request/recovery sequence. Safe refusal during an outage is distinct from usable
requests after restoration; a diagnostic-only form or successful callback is
insufficient. Keep denial/Cancel checks at the lowest effective layer, retaining
installed controls when authentication association or dispatch changes.

Use existing qualified operations and the
[short public history](../TestAutomation/E2E-Building-Blocks.md#short-confinement-usability-history).
The [local desktop composition](../TestAutomation/E2E-Scenario-Recipes.md#local-desktop-acceptance-composition)
owns exact public selection/shortcut inputs, independent observations, deadlines
and restoration. A failed positive, timeout, unknown provider or incomplete
observation is inconclusive. Human reading, choosing and authentication time
must not become a machine-startup deadline. Run affected checks after concrete
changes; unchanged completed scope needs no repeated history or proof archive.

## Verification scope and evidence limits

The core public journey is Parent configuration of a child's time/app limits,
passwordless kiosk entry, child/approver selection, genuine authentication,
requested time and selected soft-app use while hard blocks remain, then public
revocation restoring restrictions. Denial/Cancel must grant nothing. Normal
exit/reentry, session switching, fresh requests, human language/authentication
pauses and retained features remain required controls. Shared overlay behavior
needs affected checks when changed code serves both surfaces. The
[finite baseline recipe](../TestAutomation/E2E-Scenario-Recipes.md#c04b-baseline-public-use-slice)
and [cross-plan reuse map](../TestAutomation/E2E-Building-Blocks.md#cross-plan-baseline-reuse)
own exact coverage and remaining general feature work. Fedora baseline acceptance
does not broaden release support.

The public GNOME/session/PAM composition replaces the former private runtime.
Legacy fragment aliases preserve navigation, not delivery receipts, current passes
or obsolete mechanisms. Historical results never qualify changed executable
inputs.

Host composition cannot establish installed confinement or usable public entry.
Entry/approval operation qualification does not establish complete journeys,
downstream time/app effects, every retained feature or human-wait behavior.
Changed distro code, PAM, native launchers, plugins and consumed executable inputs
require affected qualification on both platforms. A historical pass or surviving
callable name cannot close those limits.
