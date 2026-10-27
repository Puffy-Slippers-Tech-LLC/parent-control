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

Review ordinary session selection, shortcuts, TTY/terminal, SSH, remote desktop,
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
Polkit. Routing is verified; optional artwork cannot veto it.

Fresh creation starts with no expiry and a locked password. After UID publication,
configuration journals original expiry and quarantines the account before deleting
the password. Reconfiguration uses the same UID-bound transaction; interruption
and reboot retain quarantine. Foreign identities/changed records refuse adoption.
Successful native/distro PAM readiness permits expiry restoration, subject to the
[expiry provenance limitation](Lifecycle.md#kiosk-provisioning-and-selected-session).

The [native PAM module](../../tools/pam_oh_no_parent_control.c) checks actual service
and account. The qualified child-run `su-l` route is denied; unfamiliar service
names use the existing account/session checks. GDM account/session checks
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

### D00 residual cleanup audit

Source review at candidate `134ce316f372f35615242a01d2b7f1551597b690`
confirmed `releases/v1.3` resolves to
`188be907c46b1cd0dabae06ac898c43e75beb05e`. The worktree initially had no
staged, unstaged or untracked changes. No overlapping baseline source work was
present. Completed C01–C04
dispositions and C05u/f acceptance remain accepted, without reopening reports.

The release comparison retains `gnome-session --session oh-no-parent-control`,
`Kiosk=true`, the required app and app-success/failure shutdown. Current deltas
preserve the notification provider, vendor agent/locale restart interface,
isolated shared form and named crash-notifier conflicts. The ordinary native
time-check result mapping and GDM runtime-cap behavior remain release-derived.
The added native kiosk dispatch/lease and UID-bound provisioning are reviewed
below, rather than assumed safe from their lineage.

The source/package retirement is already delivered: [Makefile](../../Makefile)
selects the public session, current form, native PAM, provisioning and lifecycle;
it selects no private runtime/material/view/preparation service, confinement
loader, compositor/audio override or PreSession hook. Current file discovery and
the C02d deletion in `a2b98d14` agree. Do not replay those deletions or restore
whole release files. [The fixed feature wrapper](../../tools/kiosk_session.c)
has only Wellbeing and package-query roles; it is not a session dispatcher.
Historical policy capture/removal in
[lifecycle_migration.py](../../packaging/lifecycle_migration.py) and its
[package renderer](../../packaging/render_lifecycle.py) remains necessary for
owned upgrade/rollback/post-erase cleanup, not a selectable legacy fallback.

#### Admission refusals and recovery owners

Trace: shared distro PAM → native `pam_sm_acct_mgmt`/`pam_sm_open_session` →
`kiosk_identity`/`admission`/`run_kiosk_check` → login helper
`main`/`verify_session`/`read_session`. Session opening also requires a successful
account check on that handle; `pam_sm_close_session` retains the lease until
`pam_end`. Provisioning/configuration is a separate writer, not a login repair
daemon. These complete functions and their callers establish the following
finite map for both targets; none of the errors below proves a child attack.

| Boundary and current result | Disposition, owner and representative control |
| --- | --- |
| [Native `kiosk_identity`](../../tools/pam_oh_no_parent_control.c) and [login helper `main`](../../tools/oh-no-parent-control-login-check) reject the qualified `su-l` route, with no catch-all service-name refusal; missing service is an API error. Native non-kiosk accounts bypass kiosk checks; `systemd-user` keeps a lease without routing work. | **D00a2 completed: service-name allowlist removed; both-target installed checks passed.** Unknown graphical-service naming alone is no deliberate breach predicate. Positive control: the dedicated Wayland app selected through real `gdm-autologin`, with actual execution verified. The qualified child-run `su --login` route below supplies the narrow refusal and same-route ordinary positive. A benign unfamiliar name is a host dispatch control, not a claimed real login. Named terminal/SSH/remote services remain leads for D01/D01r and remaining C06a, not protection claims. Existing account/session authority remains required. |
| Login helper `verify_session` repairs a saved session/type mismatch, then returns denial even after successful readback. Account stage uses the saved type; session stage uses `XDG_SESSION_TYPE`. Empty/unrecognized values also deny. Saved defaults do not attest to the selected executable. | **D00a residual: routing/retry boundary.** `Session=ubuntu`, empty saved fields, or stale `SessionType=x11` with an actual dedicated Wayland launch are availability controls, not attacks. Keep the actual alternate-desktop attempt separate for D01/D02. Prefer safe owned repair or removing the avoidable dependency; prove usable entry after recovery without a rejection loop or manual state deletion. Missing transport alone supplies no attack evidence. |
| `read_session` parse failure, missing NSS account, UID zero, bus error or timeout returns unavailable (2); repair setter/readback errors return denial (1). Native `run_kiosk_check` maps them to PAM errors. Each bus call is bounded at 4/5 seconds and the native child at 25 seconds, with reap on timeout. | **D00a residual: routing-service availability**, separate from routing drift if it needs an independent fix. Preserve foreign/invalid identity barriers. Malformed or temporarily unavailable routing discovery must not become an attack verdict or a kiosk password requirement. Cover one malformed reply and one transient service failure with restoration and fresh public use. Preserve original sanitized cause; do not mechanically translate errors to PAM success. |
| Native `admission`: a missing lease is created read-only/no-follow; an existing lease is opened read-only. New-inode `fstat`/`lstat`/identity/`fchmod`, existing open, shared `flock`, and retained `lock_current` stat/identity/barrier checks can all deny. Existing mode other than 0600, changed inode/link/type/owner, or inaccessible barrier state is never repaired. | **D00a residual: owned lease recovery.** Separate a stale but proven owned inode/mode or transient I/O fault from foreign/replaced state. No mode bit, failed stat or missing state demonstrates child control. Keep no-follow/inode ownership and foreign/live preservation; repair only proven owned state through its writer. Controls: absent/new lease, healthy existing lease, one owned stale-mode case, retained-handle recheck, and release/reentry. Do not unlink a live or foreign inode. |
| Shared-lock contention and an existing removal marker deny immediately. `lock_current` also rechecks the marker on existing handles. | **Preserve actual lifecycle ownership**, not an attack claim. An active exclusive configuration/removal writer must exclude admission; a live admission must exclude removal through teardown. A failed read, orphaned owned marker or accidental contention is not evidence of an active authorized operation. D00a's lease/recovery slice must distinguish these and demonstrate fresh use after the owner finishes; wider interrupted-state histories remain with remaining C09c. |
| Native PAM user/service/data errors, wrong options, absent successful account binding, allocation/clock/fork/exec/wait failure or abnormal helper exit fail the attempt. Session maps failure to `PAM_SESSION_ERR`; `pam_set_data` failure releases a newly held lease. | Preserve API/identity and same-handle authority, bounded child cleanup and no fabricated grant. These are operational failures, not desktop-defense passes. D00a changes only directly affected recovery paths; reuse host timeout/fresh-retry and handle-binding controls, then public entry after restoration. Ordinary authentication/time enforcement and explicit vendor/admin denial stay authoritative. |
| [Provisioning](../../tools/provision.py) `kiosk_account`, `cache_kiosk`, `provision_accounts_service` and `provision_configuration` reject foreign UID/home/admin identity, unsafe ownership, wrong object/visibility/limit/routing readbacks, missing templates or invalid broker configuration. `provision_icon` alone catches optional artwork errors. | Retain identity/configuration authority and optional icon isolation. A service/parse/readback failure during owned configure can leave quarantine; it is availability work, not attack success. D00a owns a demonstrated direct admission-cleanup conflict; do not add provisioning to every login or a host inventory. Keep fresh unsaved and retained hidden-account recovery distinct; opaque AccountsService metadata and a missing/custom icon must remain usable. |
| [Package postinst](../../packaging/lifecycle/postinst.in) calls lifecycle `prepare`, visibility recovery, provisioning, distro activation, `commit_migration` and `release_account`. Readiness/foreign-state/contention failures retain quarantine/records. Distro `verify`/`runtime_ready` check finite owned blocks/payload, preserving opaque vendor content and administrator edits. | **Retain owned migration/removal**, including capture receipts and post-erase finalization. Verify recovery through the maintained configure retry, never manual record deletion. Existing first-configuration, interruption and vendor-PAM histories remain their owners. The documented [expiry provenance limitation](Lifecycle.md#kiosk-provisioning-and-selected-session) is unresolved, not evidence that an administrator's day-1 denial can be cleared. Broader lifecycle redesign is outside D00a cleanup; any directly affected authority defect needs its own both-target prerequisite. |

Selected session units have no private readiness/material dependency or human
idle deadline. Notifications and the vendor agent are wanted, not required;
app failure/exit shuts down the session. An absent optional unit is not an
admission predicate. The app still needs the system bus at construction;
`RequestWindow._load_users`, `_users_done` and `_approvers_done` surface broker
failures, while `_preferences_saved` → `_agent_prepared` → `_request_done` keeps
genuine approval, denial and Cancel separate. `_request_failed` re-enables the
form; `KioskLogout` bounds public logout handoff at 750 ms with unit shutdown
fallback. Do not claim this proves every service outage recovers automatically.

Preserve these main feature consumers in
[main.py](../../kiosk/oh_no_parent_control_kiosk/main.py),
[agent_locale.py](../../kiosk/oh_no_parent_control_kiosk/agent_locale.py) and
[session_logout.py](../../kiosk/oh_no_parent_control_kiosk/session_logout.py).
Locale discovery/C-only inventories and agent environment-write/restart/job/
timeout errors stop approval, not session admission. The existing
[native-authentication fallback gap](Localization.md#native-authentication-fallback)
belongs to remaining C09a1; required shared-service and unavailable-child gaps
remain C09b/C09b1. They are availability defects, not justified protective
refusals, and gain no acceptance here. No language/feature campaign is added to
desktop cleanup; an edit touching these callers must include its affected control.

#### Automation disposition and bounded validation

**D00b residual: empty in the inspected selected consumers.**
[test_enforcement.py](../../tests/system/test_enforcement.py) binds 267 to
`system_kiosk_confinement.verify_session_composition`, 268 to
`system_kiosk_admission.verify` and 271 to `system_kiosk_scope.verify`.
Their exact owners are
[system_kiosk_confinement.py](../../tests/integration/system_kiosk_confinement.py),
[system_kiosk_admission.py](../../tests/integration/system_kiosk_admission.py) and
[system_kiosk_scope.py](../../tests/integration/system_kiosk_scope.py).
The census explicitly reports identity-only/unqualified confinement; 268 proves
account routing/refusal/retry, not graphical authentication or usable entry.
271 preserves vendor execution and invocation-owned cleanup. No selected private
view worker/import was found. [The registry](../../tests/integration/system_case_ids.py)
keeps 270/292/10 retired and 269/289–294's pending/retired dispositions;
`validate_inventory` rejects registration of `UNBOUND_CASES`. Preserve those IDs
and historical results, not their retired machinery.

Retain product coverage in
[test_prepared_kiosk_pam.py](../../tests/unit/test_prepared_kiosk_pam.py),
[test_kiosk_login.py](../../tests/unit/test_kiosk_login.py),
[test_provision.py](../../tests/unit/test_provision.py),
[test_kiosk_confinement.py](../../tests/unit/test_kiosk_confinement.py),
[test_system_kiosk_admission.py](../../tests/unit/test_system_kiosk_admission.py),
[test_system_kiosk_scope.py](../../tests/unit/test_system_kiosk_scope.py) and
[test_package_configuration.py](../../tests/unit/test_package_configuration.py).
Old refusal assertions describe current behavior, not usability approval; revise
only the affected product expectations with their authorized repair. Names such
as “prepared” do not justify deleting current product tests. No task-brief/history
tests or replacement tests of retired tests are required by this review.

Concrete earlier failure boundaries survive in source: Fedora GDM `xdm_t`
versus user-manager `init_t` requires read-only shared leases; lifecycle
`barriers` labels only its verified exclusively held inode `xdm_var_run_t`
when package creation would leave `var_run_t` (delivered in `03c206e4`).
`test_removal_exclusion_spans_close_until_pam_end_and_releases` checks new/existing
leases for both callers; installed `caller_identity`/`pam_caller_command` retains
the real Fedora contexts. [system_kiosk_accounts.py](../../tests/integration/system_kiosk_accounts.py)
`fixture_record`/`exercise` retains `SystemAccount=true` despite visible daemon
state, unknown metadata/xattrs, unsafe-mode and atomic recovery cases. The exact
inputs of other earlier passwordless-login incidents are unavailable; these are
known error-boundary controls, not a claim to have reproduced those incidents.

D00a's finite gate uses the qualified
[cross-plan operations](../TestAutomation/E2E-Building-Blocks.md#cross-plan-baseline-reuse):
`journey_blocks.station_entry`, `request_flow.prepared_request` (75 seconds,
one child/approver), `approval_flow.rejected_request` (wrong password and
independent Cancel), `kiosk_approved_flow.approved_request`, public Parent grant
readback, normal exit and fresh usable entry/request, then owned restoration.
Their source owners are [journey_blocks.py](../../tests/e2e/journey_blocks.py),
[request_flow.py](../../tests/e2e/request_flow.py),
[approval_flow.py](../../tests/e2e/approval_flow.py),
[kiosk_approved_flow.py](../../tests/e2e/kiosk_approved_flow.py) and
[kiosk_approval.py](../../tests/e2e/kiosk_approval.py).
`QUALIFICATION_PLAN`/`KioskApprovalJourney.check_settings` supplies independent
positive grant observation; the approval leaf alone does not prove it.
[baseline_journey.py](../../tests/e2e/baseline_journey.py) `PLAN`/`BaselineJourney`
already combines zero-grant rejection/Cancel endpoints, positive effects and
exit/reentry, but its roughly 24-minute history includes broader feature work.

The D00 audit found no dedicated short complete gate; qualification of leaves
was insufficient. D00a1 subsequently qualified the
[short public history](../TestAutomation/E2E-Building-Blocks.md#short-confinement-usability-history)
on both targets, including public restoration and owned runner cleanup.
**Before each product task completes**, run that gate on its candidate and bind
each changed slice's
representative variation/recovery control above as well: host injections for
parse/command errors, installed engineering checks for actual routing/lease/
service context, then restored public usability. New variations are unqualified;
268 and a visible window cannot substitute for them. Add ordinary-account login
for shared PAM edits; overlay/enforcement controls only if their callers change.

The service-dispatch, routing/service and owned-lease residuals are independent
boundaries. D00a must split required independent fixes/qualification before
editing, keeping each product fix's review/build, both-target usability and
cleanup together. D00 audits only: it supplies no installed pass, closes no
other task, and allocates no VM/artifacts. D00b verifies this empty obsolete-
consumer disposition against D00a's actual changes rather than replaying C03/C04.

#### D00a2 service-variation prerequisite

D00a2's finite product slice replaces the native/helper service allowlist with
the reached `su-l` refusal below. No catch-all unknown-service refusal remains;
`gdm-autologin` and a benign unfamiliar service use the existing account/session
checks. Missing service remains an API error. Ordinary authentication/time
checks, same-handle account authority, bounded helper execution and lifecycle
leases retain their owners. Saved-routing recovery belongs to D00a3.
The affected controls are the existing native/helper service, handle, timeout
and lease regressions; installed 268's account/routing checks; the real graphical
variation with `app_execution_qualified == True`; the reached child-run `su-l`
refusal and same-route ordinary positive; and the complete short usability
history, which also exercises ordinary-account graphical entry. These checks
passed on the repaired product candidate on `onpc-Ubuntu26.04` and
`onpc-Fedora44`, including approval, rejection/Cancel, reentry and restoration.
The independent Astra xHigh backend review found no actionable issues; all 216
selected host checks and the DEB/RPM `make build` checks passed. Owned cleanup
finished on both targets.

Installed admission 268 also passed on both targets. Its dedicated `su-l`
callback worker uses the existing child fixture's real UID while retaining
effective/saved root through `pam_end`, then restores its original credentials.
Fedora's vendor `su` stack otherwise accepts a root real UID before reaching
the product account module. This corrects the engineering caller context while
retaining kiosk status 6, ordinary status 0 and teardown status 0. The separately
qualified real child-run `su` refusal remains the reached-route control.

D00a2q supplies the finite
[`gdm_service_variation.qualify(transport, lease)`](../../tests/e2e/gdm_service_variation.py)
binding through `KioskServiceVariationQualification` and the registered installed
selector `check_e2e_kiosk_service_variation`. It runs before the existing
`KioskEntryJourney` worker reattaches, in the same guarded installed attempt.

The binding uses AccountsService to enable automatic login for the station and
request `oh-no-parent-control` / `wayland`. It saves the prior automatic account,
routing and exact GDM/PAM configuration. Temporary GDM debug and an optional
`pam_warn` account observation expose the real vendor `gdm-autologin` invocation;
no authentication or product admission gate is replaced or bypassed. One display
manager restart supplies the invocation. Journal boot/cursor boundaries, the real
`/usr/libexec/gdm-session-worker`, its station/service initialization and its
same-PID account callback/refusal distinguish refusal from missing setup.
GDM command resolution of `oh-no-parent-control.desktop` is recorded separately:
it is neither saved-default evidence nor proof that the selected app executed.
The observed manager executable is `/usr/sbin/gdm3` on Ubuntu and `/usr/bin/gdm`
on Fedora; both invoke `/usr/libexec/gdm-session-worker` for the PAM operation.

The qualified positive requires the shared public
`station-default-entry` and `kiosk-request-form` observations, a real
`gdm-autologin` Wayland logind session, GNOME 50's dedicated
`gnome-session-manager@oh-no-parent-control.service` process and the owned
running app service/process. The manager's executable, arguments, UID, cgroup
and stable process identity distinguish it from GDM's launch wrapper.
The caller requires `result == 'session-created'` and
`app_execution_qualified == True` after the product fix.

Restoration checks owned identities/bytes before writes, restores the original
automatic account, routing, PAM bytes and GDM bytes/owner/mode after
AccountsService's keyfile serialization, and restarts the display manager.
The existing public normal-entry/form/Cancel/GDM-return history then verifies
restoration before runner/VM cleanup. Changed or foreign configuration refuses
restoration instead of being overwritten.

D00a2q's pre-fix qualification passed on `onpc-Ubuntu26.04` and `onpc-Fedora44`:
both returned `account-refused` from the witnessed real `gdm-autologin` operation,
resolved the dedicated desktop file and restored normal public entry. D00a2's
repaired candidate then passed actual dedicated app execution through this
variation on both targets, exact settings restoration and normal public
entry/form/Cancel/return plus runner/VM cleanup. The pre-fix refusal supplies no
usable-session or defense credit; the positive execution is now qualified only
for this named binding.

The D00a2 preflight identified a separate control gap:
`system_kiosk_admission.verify` invokes `pam_acct_mgmt` directly for `login`/
`sshd`, and `sshd -T` observes configuration only. Neither witnesses an actual
child-invoked prohibited route. The serial HAR bindings cover their fixed harness
fixture, not station-account admission. **D00a2r** closes that gap through
[`su_service_route.qualify(transport, lease)`](../../tests/e2e/su_service_route.py),
`KioskServiceRouteQualification` and the registered installed selector
`check_e2e_kiosk_service_route`.

The accepted standard-child fixture invokes the installed setuid `/usr/bin/su
--login oh-no-parent-control` with an empty token. The child controls that target
and login action; no kiosk-code execution is assumed. The exec wrapper records
its actual child credentials and process start time. Boot/cursor/PID/time-bound
journal observations identify the executable and actual PAM service, **`su-l`
on both targets**, rather than assuming the service from the command name.
Independent logind and process observations find no station session or shell.

The native service-refusal return is silent. A temporary, uniquely named
tracefs instance and paired uprobes observe the installed module's exported
`pam_sm_acct_mgmt`, using its package-listed file and ELF symbol/load offset.
The same child-invoked PID enters with `argc=1` and returns
`PAM_PERM_DENIED` (6). This distinguishes the native kiosk account refusal from
an earlier authentication failure or a generic failed command. Observation
changes neither the module nor PAM dispatch. Unknown/replaced probe definitions
or instance identities refuse cleanup; only exact owned definitions are removed.
This binding requires x86_64, existing tracefs and `readelf` on the two named
targets. Authentication refusal before the callback remains unqualified and
stops the route without bypassing a gate.

The same child positively invokes `su --login` for the accepted `other-child`
fixture and runs `/usr/bin/id -u`. The existing private credential reader and
guarded SSH input carry the fixture password. Before one pipe write, the helper
observes the password prompt and rechecks the live su PID/start time, executable,
real/effective credentials, exact target/command and NSS identities. Exit zero,
the ordinary target's effective UID and the same actual `su-l` service establish
success. No password, account lock, shell or vendor authentication rule changes.

Installed qualification passed on `onpc-Ubuntu26.04` and `onpc-Fedora44`: native
refusal, ordinary positive, unchanged credentials/shell/PAM/module, exact trace
removal, normal public passwordless station entry/form/Cancel/return and owned
runner/VM cleanup. That prerequisite changed no product source and qualified
only this reached service-route control. D00a2 retained the same native refusal
and ordinary positive on its repaired candidate; its separate graphical and
complete usability results are recorded above.

#### D00a3 routing qualification prerequisite

`system_kiosk_admission.verify` retains real alternate-session and `x11` saved
preferences through account-only callbacks, expecting refusal/repair/retry;
that account-only history supplies no graphical execution observation.
The service-only `gdm_service_variation.qualify` uses dedicated saved routing
and observes the actual Wayland session, app and selected GNOME-session process.
Saved-routing variation needs independent session selection: simply omitting
the dedicated setup would let the saved preference select another session.

D00a3q implements
[`gdm_service_variation.qualify_routing(transport, lease)`](../../tests/e2e/gdm_service_variation.py)
through `KioskRoutingVariationQualification` and the listed installed selector
`check_e2e_kiosk_routing_variation`. GDM's greeter peer `SelectSession` selects
the dedicated session independently of the saved alternate/empty/`x11` values,
then invokes the real `gdm-password` route without answering any prompt.
Exact input readback and the attempt-bound installed helper's refusal/repair
diagnostic distinguish a reached saved-routing check from an earlier failure.
The peer acknowledgement and daemon selection identify a refused route before
selected-command resolution; an absent later resolution is not an execution
claim. Refused variations receive no execution credit. The normal dedicated positive
uses the existing Wayland logind, running app-service/process and selected
GNOME-session process observations, tying GDM's opened session ID to logind;
D00a3 reuses them with `expectation='execution'`.

The separate discovery control temporarily stops AccountsService under an
exclusively created runtime mask, invokes the installed native account callback,
and requires the helper's unavailable diagnostic. Restoration checks the exact
owned mask, service configuration, saved routing and ordinary-account isolation;
changed or foreign entries refuse restoration. The existing public station-list
observation establishes a usable greeter before each variation and discovery loss,
separately from the preceding display-manager restoration. This prevents the next
variation from immediately restarting a greeter still starting up. The caller
then runs the existing fresh public station entry/form/Cancel/return history.
Installed qualification and owned cleanup passed on `onpc-Ubuntu26.04` and
`onpc-Fedora44`: normal dedicated execution, all three pre-fix refusal/repair
controls, actual discovery loss, exact restoration and fresh public use.
No separate product recovery defect was established.
No product admission or package consumer changes are included;
malformed replies and D00a3's full product acceptance remain with D00a3.

#### D00a prerequisite allocation

D00a's source inspection confirmed the service allowlist in native
`kiosk_identity`/helper `main`, the drift/discovery rejection in `verify_session`,
and the stale-state rejection in `admission`/`lock_current`. These are independent
boundaries; they cannot share one small product fix and its required installed
gate. No product code changed during this split and no installed result is
claimed. The [ordered queue](../Kiosk-Desktop-Queue.md) now allocates:

| Owner | Remaining finite deliverable |
| --- | --- |
| D00a1 | Completed: short public history qualified on both targets with restoration and runner cleanup. The wider completed baseline stays accepted. |
| D00a2q | Qualify the real graphical service-variation binding, independent selected-session/result observations and owned restoration on both targets before the service-dispatch product edit; no consumer acceptance credit. |
| D00a2r | Qualify one actual child-invoked prohibited service route and its account-refusal witness, ordinary-account positive and owned restoration on both targets before the service-dispatch product edit; no product changes or consumer acceptance credit. |
| D00a2 | Remove unjustified service-name rejection; verify actual dedicated graphical execution through the affected service, a reached prohibited-route control and ordinary-account login, with same-candidate both-target public usability. |
| D00a3q | Completed: both-target normal execution, three saved-routing refusal/repair controls, transient discovery loss, exact restoration, fresh public use and owned cleanup passed; no product changes or consumer acceptance credit. |
| D00a3 | Remove the avoidable saved-routing/discovery admission dependency, including drift, malformed-reply and transient discovery controls. Keep invalid identity/authority barriers and prove restored public use on both targets. |
| D00a | Resolve owned lease/recovery at native `admission`/`lock_current` and lifecycle `barriers`, preserving live/foreign state, read-only Fedora leases and active writer exclusion. Include stale-mode, retained-handle and release/reentry controls with both-target usability. |

Historical migration capture/rollback remains necessary; broader provisioning,
expiry provenance, locale/agent and shared-service defects retain the explicit
owners above. The prerequisite insertion does not close D00a or D00b, change
their scope, or qualify new variation bindings. Each product fix owns its review,
build, affected checks, exact-candidate public history and restoration before
completion. Any independently missing reusable qualification must precede its
product consumer under the shared execution contract.

## Verification scope and evidence limits

The completed v1.3-derived baseline validation accepted Ubuntu and Fedora core
histories and separate feature/pause results through C05u/C05f, including public
restoration and owned cleanup. The retained
[both-target baseline handoff](../TestAutomation/E2E-Building-Blocks.md#c05f-fedora-baseline-acceptance)
owns that acceptance; the [operation applicability map](../TestAutomation/E2E-Building-Blocks.md#c04b-baseline-operation-applicability)
owns exact delivered scope. Completed prerequisites stay complete without old
report inspection. Concrete later changes receive affected checks in their
current task. This baseline supplies no final defense claim for unqualified
desktop, terminal/SSH, exposed-input, recovery or update routes.

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
inputs. The [proof record](../Kiosk-Confinement-Proof.md) retains historical claims
and disclosed proof loss; it is not current design authority.

Host composition cannot establish installed confinement or usable public entry.
Entry/approval operation qualification does not establish complete journeys,
downstream time/app effects, every retained feature or human-wait behavior.
Changed distro code, PAM, native launchers, plugins and consumed executable inputs
require affected qualification on both platforms. A historical pass or surviving
callable name cannot close those limits.
