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

## Admission and account integrity

[Provisioning](../../tools/provision.py) creates the non-administrative reserved
account with `/usr/sbin/nologin`, a recorded numeric UID and owned home.
Public AccountsService properties select the dedicated Wayland session and
visible/saved classification. The station cannot change its own metadata through
Polkit. Routing is verified; optional artwork cannot veto it.

Fresh creation starts with no expiry and a locked password. After UID publication,
configuration journals original expiry and quarantines the account before deleting
the password. Reconfiguration uses the same UID-bound transaction; interruption
and reboot retain quarantine. Foreign identities/changed records refuse adoption.
Successful native/distro PAM readiness permits expiry restoration, subject to the
[expiry provenance limitation](Lifecycle.md#kiosk-provisioning-and-selected-session).

The [native PAM module](../../tools/pam_oh_no_parent_control.c) checks actual service
and account. Terminal/SSH account admission is denied. GDM account/session checks
require dedicated routing and Wayland; repair still denies the current attempt.
Missing/unsafe state and contention deny entry. Shared root-owned no-follow
admission leases persist through PAM teardown, excluding exclusive lifecycle
writers but not competing logins. They require read access only because GDM and
user-manager SELinux write authority can differ.

[Distro PAM integration](../../packaging/distro_pam.py) uses Ubuntu
`pam-auth-update` and Fedora's owned authselect transaction. It verifies finite
product authentication/account blocks, skip destinations and runtime-cap hook;
unrelated vendor text remains opaque. Ordinary accounts retain authentication,
administrator denials and time policy.

Saved preferences and a nologin shell do not attest to GDM's actual next executable.
Desktop/session-choice, TTY, SSH and remote-desktop routes retain separate
prevention and public qualification obligations. Account-only probes and host
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

Native PAM owns account/session routing, ordinary time/runtime-cap behavior and
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
| 268, account admission | Current account-only routing/refusal/retry/restoration and ordinary-account positives; no authentication, graphical entry or remote-route proof. |
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

## Verification scope and evidence limits

The public GNOME/session/PAM composition replaces the former private runtime.
Legacy fragment aliases preserve navigation, not delivery receipts, current passes
or obsolete mechanisms. Historical results never qualify changed executable
inputs. The [proof record](../Kiosk-Confinement-Proof.md) retains historical claims
and disclosed proof loss; it is not current design authority.

Host composition cannot establish installed confinement or usable public entry.
Entry/approval operation qualification does not establish complete journeys,
downstream time/app effects, every retained feature or human-wait behavior.
Changed distro code, PAM, native launchers, plugins and consumed executable inputs
require affected qualification on both platforms. A historical pass or surviving
callable name cannot close those limits.
