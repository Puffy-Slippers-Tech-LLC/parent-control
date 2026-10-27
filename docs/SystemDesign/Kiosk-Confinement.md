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
Polkit. Provisioning verifies initial routing; optional artwork cannot veto it.

Fresh creation starts with no expiry and a locked password. After UID publication,
configuration journals original expiry and quarantines the account before deleting
the password. Reconfiguration uses the same UID-bound transaction; interruption
and reboot retain quarantine. Foreign identities/changed records refuse adoption.
Successful native/distro PAM readiness permits expiry restoration, subject to the
[expiry provenance limitation](Lifecycle.md#kiosk-provisioning-and-selected-session).

The [native PAM module](../../tools/pam_oh_no_parent_control.c) checks actual service
and account. The qualified child-run `su-l` route is denied; unfamiliar service
names use the existing account/session checks. GDM account/session checks
validate the reserved identity without consulting saved routing or session type.
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
`main`/`verify_identity`. Session opening also requires a successful
account check on that handle; `pam_sm_close_session` retains the lease until
`pam_end`. Provisioning/configuration is a separate writer, not a login repair
daemon. These complete functions and their callers establish the following
finite map for both targets; none of the errors below proves a child attack.

| Boundary and current result | Disposition, owner and representative control |
| --- | --- |
| [Native `kiosk_identity`](../../tools/pam_oh_no_parent_control.c) and [login helper `main`](../../tools/oh-no-parent-control-login-check) reject the qualified `su-l` route, with no catch-all service-name refusal; missing service is an API error. Native non-kiosk accounts bypass kiosk checks; `systemd-user` keeps a lease without routing work. | **D00a2 completed: service-name allowlist removed; both-target installed checks passed.** Unknown graphical-service naming alone is no deliberate breach predicate. Positive control: the dedicated Wayland app selected through real `gdm-autologin`, with actual execution verified. The qualified child-run `su --login` route below supplies the narrow refusal and same-route ordinary positive. A benign unfamiliar name is a host dispatch control, not a claimed real login. Named terminal/SSH/remote services remain leads for D01/D01r and remaining C06a, not protection claims. Existing account/session authority remains required. |
| Login helper `verify_identity` checks the nonzero reserved NSS identity. Saved session/type and `XDG_SESSION_TYPE` no longer vote on admission; the helper has no bus reader, parser or setter. Native callers no longer forward the unused transport value. | **D00a3 completed.** Stale alternate session, empty fields and saved `SessionType=x11` passed independent dedicated Wayland selection/execution controls on both targets. Actual alternate-desktop prevention remains D01/D02 work. Provisioning still owns initial saved routing; admission does not rewrite preferences. |
| Missing NSS identity, UID zero or identity lookup error returns unavailable (2), with a closed account diagnostic. Native `run_kiosk_check` retains distinct PAM failure mapping and its 25-second timeout/kill/reap. Routing discovery is no longer invoked. | **D00a3 completed:** host malformed reply and timeout doubles receive no bus invocation; installed real discovery loss permits the native account callback, preserves ordinary-account isolation, restores exact service/mask state and permits fresh public use on both targets. Invalid identity, administrator denial, lifecycle leases and same-handle authority remain barriers; no PAM error is translated to success. |
| Native `admission`: a missing lease is created read-only/no-follow; an existing lease is opened read-only. New-inode `fstat`/`lstat`/identity/`fchmod`, existing open, shared `flock`, and retained `lock_current` stat/identity/barrier checks can all deny. Native PAM never repairs an existing lease. | **D00a owned lease recovery:** lifecycle `barriers` can repair a safe stale admission mode only after exclusive locking, fresh regular-file/owner/single-link checks and named-inode equality. It changes the locked descriptor to 0600 without replacement. Legacy locks remain strict. Controls: absent/new lease, healthy existing lease, one owned stale-mode case, retained-handle recheck, and release/reentry. Foreign, writable, linked or live state remains protected; transient errors require fresh retry, not an attack claim. |
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

**D00's initial audit found no obsolete executable v1.4 consumer in the selected workers.**
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

#### D00b automation close-out

D00b confirmed the C03/C04 dispositions above against D00a's selected consumers:
no private runtime/view fixture, import, package-test requirement or executable
registration remains to remove. Historical package snapshots and foreign-generation
preservation checks remain necessary migration/ownership controls. Stable
267/268/271 bindings, retired/pending identities and their qualification limits
are unchanged; the catalogue still owns unfinished route qualification.

One redundant host check in `test_kiosk_confinement.py` still mirrored the old
`login`/`sshd` rejection sequence. It was removed under the
[test scope mandate](../Mandates/Test-Scope-Mandate.md), without a replacement
test of the installed case. Native service dispatch remains covered by
`test_prepared_kiosk_pam.py` and installed 268's ordinary-account/`su-l` controls.
The existing routing-restoration guard now injects failure at the current
allowed variation and drops the obsolete unrepaired-routing case; it still
requires exact kiosk/ordinary state restoration. The optional-telemetry mock
now targets `user_command`, preserving its deadline and unavailable result.
No product expectations or installed bindings changed.

Host ownership: `tools/run-tests unit 'tests/unit/test_kiosk_confinement.py'
--timeout 180s -q` passed all 63 remaining checks after repair. The unchanged
`test_kiosk_login.py`, `test_system_kiosk_admission.py` and
`test_system_kiosk_scope.py` selections passed another 74 checks in this task.
Coverage generation and system/E2E host-only listing passed; changed Markdown
links passed. Resource ownership is unchanged: private pytest state, existing
module fixtures and descriptor cleanup; no VM, display or external service was
allocated. No build is required for these non-package inputs. D01 may trust
D00a's completed both-target usability, recovery and installed 268 results;
D00b grants no new installed acceptance and leaves no unexplained legacy consumer.

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

Before D00a3, `system_kiosk_admission.verify` expected refusal/repair/retry for
alternate-session and `x11` saved preferences through account-only callbacks.
That history supplied no graphical execution observation. D00a3q qualified
the finite pre-fix refusal/repair and discovery-loss controls on both targets,
including exact restoration and fresh public entry; it supplied no consumer
acceptance credit. No separate essential-service recovery defect was established.

The current
[`gdm_service_variation.qualify_routing(transport, lease)`](../../tests/e2e/gdm_service_variation.py)
binding uses `expectation='execution'` through `KioskRoutingVariationQualification`
and `check_e2e_kiosk_routing_variation`. GDM's greeter peer `SelectSession`
selects the dedicated session independently of saved alternate/empty/`x11`
values, then invokes real `gdm-password` without answering a prompt. Exact
input readback and the attempt-bound identity diagnostic establish the reached
account check. Every variation requires actual Wayland logind, running app
service/process and selected GNOME-session process observations, tying GDM's
opened session ID to logind; saved defaults and command resolution alone earn
no execution credit. A usable public greeter separates restored attempts.
Actual AccountsService discovery loss must permit native account admission;
exact owned service/mask, routing and ordinary-account restoration precede
fresh public entry/form/Cancel/return. Changed or foreign state refuses cleanup.

D00a3 removes `busctl`, `read_session` and `verify_session` from the packaged
helper, retaining `verify_identity` and its native bounded caller. The helper
remains a used package input for NSS identity validation; no package removal or
new routing supervisor is needed. The installed binding now requires execution
for every preference variation and successful native admission during the outage,
with an attempt-bound identity diagnostic. The short confinement history also
checks genuine approval, rejection, Cancel, reentry and ordinary graphical use.

The final candidate passed installed admission 268, the routing binding above
and `check_e2e_confinement_usability` on `onpc-Ubuntu26.04` and `onpc-Fedora44`,
including public restoration and owned runner/VM cleanup. Host checks covered
malformed replies/timeouts without bus access, invalid identity, same-handle
authority, administrator denial, lifecycle exclusion and bounded child cleanup.
Independent Astra xHigh backend review found no actionable issues; 286 focused
product/ownership checks, 445 existing launcher checks and DEB/RPM builds passed.

#### D00a lease qualification prerequisite

D00a's resumed source inspection found one concrete stale-mode repair deadlock:
native `lock_current` requires mode `0600`, while lifecycle `barriers` calls
`read(path, private=True)` before opening and exclusively locking the same inode.
An owned mode `0640` therefore blocks both admission and its maintained writer.
The small repair belongs at that writer after ownership, inode and exclusive-lock
checks; PAM must retain read-only shared leases and foreign/live-state guards.
No product edit or installed result was made during this inspection.

Existing `test_prepared_kiosk_pam` controls cover new/existing leases,
retained-handle identity/mode/marker checks and ownership through `pam_end`.
Installed `system_kiosk_admission.verify` covers account/service/routing controls;
`held_account` holds a real account handle but does not qualify a lease-recovery
variation or restored public use. The qualified service/routing operations and
short usability history do not cover the missing variation either. **D00a4q**
therefore qualifies the finite absent/healthy/stale-mode, retained-handle and
active-writer controls on both targets before D00a product edits. Its current
refusal characterization and exact fixture restoration earn no repaired-product
acceptance. No excluded task-brief/history tests are restored.

The registered `check_e2e_kiosk_lease_variation` now binds
[`kiosk_lease_variation.qualify`](../../tests/e2e/kiosk_lease_variation.py) and
[`system_kiosk_lease_variation.engineering`](../../tests/integration/system_kiosk_lease_variation.py)
to the [finite lease matrix](../TestAutomation/E2E-Building-Blocks.md#owned-sign-in-lease-variation).
One fresh GDM admission creates the absent lease; healthy existing and retained
handles use real `gdm-password` and `systemd-user` callers, including Fedora's
`xdm_t`/`init_t` read-only opens. The same inode's `0640` admission/writer refusal,
identity-guarded exact restoration, same-handle recheck, exclusion through close
until `pam_end`, actual lifecycle writer hold/release and fresh admission remain
engineering controls. The complete existing short public history follows exact
restoration. D00a4q passed the finite refusal controls, complete short public
history and owned cleanup on `onpc-Ubuntu26.04` and `onpc-Fedora44`, without
product changes or D00a acceptance credit. The separate `recovery` expectation
is selected by D00a for the repaired candidate; its installed result is recorded below.
Fedora's vendor `systemd-user` account stack can return at its sufficient
`pam_unix` entry before the shared module. Its installed retained-handle control
therefore acquires/rechecks at the actual session include; a successful account
callback alone is not lease evidence. Ubuntu's user-manager and both GDM
bindings acquire/recheck at account admission.

Marker disposition is bounded by actual provenance: `prepare` saves authoritative
removing state before writing its marker; `commit_migration` and `finish_remove`
erase the marker before state. Their normal interruption order does not create
an orphan marker without state. `marker` validates ownership/content, and a
marker without authoritative state is explicitly refused as unowned by the
configuration/rollback paths. Do not adopt or delete it based on absence of a
live lock. Valid interrupted marker-plus-state recovery stays with the existing
configuration writer; broader interrupted-state recovery remains C09c. Transient
read/lock faults remain bounded engineering/fresh-retry controls, not attack claims.

#### D00a owned lease repair

The only product change is admission-mode recovery in lifecycle `barriers`.
Its initial read retains the ordinary safe-file checks for the admission lease;
the legacy leases still require mode 0600. After exclusive acquisition it reads
fresh descriptor metadata, checks the named inode and revalidates type, owner,
single link and absence of group/other write access before changing the same
descriptor to 0600. A live shared handle prevents repair until release. Native
PAM, its read-only Fedora descriptors, removal markers and lifecycle labels are
unchanged. No inode, installed record or historical evidence is removed.

Three focused product regressions cover live-handle exclusion followed by
same-inode recovery, and post-lock hardlink/replacement preservation. They use
private pytest paths and close their own descriptors; resource ownership remains
within the existing package-configuration module. No task-history or test-tool
tests are added. Independent Astra xHigh review found no actionable issues.
All 498 selected package-configuration and native PAM checks and the DEB/RPM
build passed. On both `onpc-Ubuntu26.04` and `onpc-Fedora44`, the repaired
candidate passed the `recovery` lease matrix, complete short public history,
ordinary-account login and installed admission case 268. Same-inode repair,
retained read-only handles, writer exclusion, fresh admission after release,
public settings restoration and owned session/VM cleanup passed.

The residual source dispositions are now explicit: D00a2 removed service-name
rejection; D00a3 removed saved-routing/discovery admission; D00a repairs this owned
lease conflict. Historical migration remains the necessary restoration owner.
Marker provenance, wider interrupted lifecycle/expiry recovery, locale/agent and
shared-service gaps retain the owners in the refusal map. None selects a legacy
confinement fallback or becomes unexplained cleanup work for D00b.

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
| D00a3 | Completed: saved-routing/discovery admission dependency removed; both-target preference execution, discovery loss/restoration, complete public usability and installed admission passed, with invalid identity/authority barriers retained. |
| D00a4q | Completed: finite installed lease refusal, active writer exclusion, exact fixture restoration and complete short public history passed on both targets before product edits; no consumer acceptance credit. |
| D00a | Completed: lifecycle writer repairs the safe stale lease on the same inode, preserving native read-only leases and live/foreign state. Both-target recovery, retained-handle/exclusion controls, complete short public history, installed 268 and owned cleanup passed; independent review, affected host checks and build passed. |

Historical migration capture/rollback remains necessary; broader provisioning,
expiry provenance, locale/agent and shared-service defects retain the explicit
owners above. The prerequisite insertion does not close D00a or D00b, change
their scope, or qualify new variation bindings. Each product fix owns its review,
build, affected checks, exact-candidate public history and restoration before
completion. Any independently missing reusable qualification must precede its
product consumer under the shared execution contract.

## D01 local desktop route review

D01 reviewed the rebuilt account, PAM, selected-session and request-action
callers after completed D00b cleanup. The completed
[C05u/C05f handoff](../TestAutomation/E2E-Building-Blocks.md#c05f-fedora-baseline-acceptance)
and D00a's both-target usability/restoration remain accepted; no historical
reports were reopened. This is a source review, with no product changes or new
installed defense claim. D01r owns the remote provider; D02 owns independent
design approval and the final small implementation/qualification allocations.

### Actual local selection and execution boundary

Provisioning's `provision_accounts_service` sets the public saved session/type.
The AccountsService Polkit rule denies the station's own metadata changes. Neither
controls GDM's current selection. Ubuntu's shared PAM profiles and Fedora's
authselect integration reach native `pam_sm_acct_mgmt` and
`pam_sm_open_session`; `kiosk_identity`, `admission` and `run_kiosk_check` bind
identity, lifecycle ownership and successful account authorization on the same
handle. The login helper's `main`/`verify_identity` reads no selected executable.
It receives only user, service and fixed PATH. No selected-command barrier is
present here; inventing one from `PAM_SERVICE`, saved routing or
`XDG_SESSION_TYPE` would repeat the removed admission mistake.

The vendor source trace uses upstream 50.0, not an assertion that either distro
ships unmodified upstream bytes:

- [Shell login dialog](https://github.com/GNOME/gnome-shell/blob/50.0/js/gdm/loginDialog.js):
  `SessionMenuButton._populate` selects available sessions; its activation calls
  `SelectSession`. `_onPrompted`/`_shouldShowSessionMenuButton` expose the chooser
  during verification, excluding an already logged-in user. Immediate passwordless
  success does not establish a usable chooser interval.
- [GDM session](https://github.com/GNOME/gdm/blob/50.0/daemon/gdm-session.c):
  `gdm_session_handle_client_select_session` → `gdm_session_select_session` →
  `get_session_name` prefers the current selection over the saved default.
  `get_session_command_for_file` reads its desktop `Exec`;
  `gdm_session_start_session` sends the corresponding Wayland/X session command
  to the worker. The handler rejects changes after the session is running.
- [GDM worker](https://github.com/GNOME/gdm/blob/50.0/daemon/gdm-session-worker.c):
  `gdm_session_worker_authorize_user`/`gdm_session_worker_open_session` run PAM;
  `gdm_session_worker_handle_start_program` and
  `gdm_session_worker_start_session` execute the supplied program as the account.
  Its login shell becomes an environment value, not the graphical launcher.
- [GDM manager](https://github.com/GNOME/gdm/blob/50.0/daemon/gdm-manager.c):
  `on_session_cancelled` → `queue_session_reset` → `on_reset_session` invokes
  `gdm_session_reset`/`do_reset`, clearing current and saved selections. Choosing
  another account's desktop and then cancelling is not source evidence of a
  surviving kiosk selection.

The existing real GDM binding in
[`gdm_service_variation.py`](../../tests/e2e/gdm_service_variation.py)
uses `PEER_SELECTION`/`peer_selection` to explicitly select the **dedicated**
session, then independently observes actual execution. `qualify_routing` varies
saved defaults, not a child's selected alternate desktop. It cannot prove that
the chooser is reachable or that a selected full desktop is blocked.

### Finite local attempts and controls

The prohibited result throughout is a usable full desktop **as the station
account**, with normal desktop launch controls. An ordinary account's desktop,
a blank compositor, an unavailable dependency or a generic rejected login is
not that result and supplies no defense pass.

| Child access and deliberate action | Current disposition and smallest owner | Negative, permitted control and restoration |
| --- | --- | --- |
| At GDM, select the station and choose an available full desktop; also check the ordinary-account chooser → Cancel → station sequence without supplying an administrator password. | **C07a1 qualified a no-route disposition on both targets; no missing barrier demonstrated.** Ordinary-account public desktop selection works. Normal passwordless station selection, directly and after ordinary chooser cancellation, reaches the dedicated request without exposing a station chooser. No authentication delay or saved-routing change manufactured reachability. C07a retains its own both-target usability gate and may add only a demonstrated justified barrier. | Independent selected desktop-file command, station-UID session/manager/Kiosk processes and public usable request results passed for both attempts. Owned saved choices and public policy were restored, followed by usable Cancel/reentry and runner/VM cleanup. This does not claim that a selected alternate executable was denied; see the exact qualification below. |
| In the usable request session press Super, Super-A, Alt+F2 and Ctrl+Alt+T, seeking desktop launch controls. | **C07s1 qualified these four request-only results and working ordinary controls on both targets.** Dedicated `Kiosk=true` starts GNOME Kiosk rather than full Shell. Upstream [Kiosk compositor](https://github.com/GNOME/gnome-kiosk/blob/50.0/compositor/kiosk-compositor.c) `kiosk_compositor_start` calls `neuter_builtin_keybindings`, whose no-op handler covers `panel-main-menu` and `panel-run-dialog`. This is no claim about every distro shortcut. C07s owns only a demonstrated desktop-enabling result. | Each distinct attempt preserved a usable request without a desktop/run surface. Ordinary overview, app grid, Run and terminal controls worked; Fedora's terminal chord is permanently baseline-prepared. Owned closure, Cancel/fresh entry, public settings restoration and runner cleanup passed. A terminal-only or VT outcome belongs to the remaining plan, not an expanded desktop assertion. |
| Open About/Help or What's New and try offered links leading to external handlers. | **Source-effective action barrier.** `RequestWindow._build` omits kiosk Help; `_show_about` and `WhatsNewPresenter.show` pass `links_enabled=False`. About renders plain labels; `WhatsNewDialog._render`/`_activate_link` suppress external actions. No new barrier justified. | Complete kiosk action inventory must lack external launches while information remains readable/dismissible; the overlay retains permitted links. Close the dialog and compare the unchanged request. An external handler alone is not a demonstrated chain to a desktop. |
| Open an error report and try attachments, download, Privacy or editor links. | **Source-effective action barriers.** `ErrorHandler.present` propagates kiosk mode to `FeedbackDialog`; `_choose_attachments`/`_download_logs` are hidden and guarded, Privacy stays in-app, and the editor has no attachment callback. `RichTextEditor._decide_policy` refuses non-blank navigation/new windows. No new barrier justified. | Require useful report/editor/privacy with no chooser or external action; ordinary Parent attachments/export remain permitted. Restore any owned dependency fault, close the report, then exit/reenter normally. Trusted WebKit compromise is excluded. |
| Open Preferences, preview reminders/banner actions or change language. | **Source-effective fixed actions.** `ReminderDialog._preview` supplies no launch actions; `NotificationApplication._method_call`/`_show` reject supplied actions and expose only dismiss/fixed Preferences activation. `agent_locale.prepare`/`_start` restart the fixed authentication-agent unit. No desktop launcher found. | Preserve usable dialogs, preview and genuine authentication. Cancel drafts/dismiss banners and retain request/settings. Do not add an arbitrary service-launch premise or a general feature campaign. |
| Cancel/Escape, close a report/result, approve, or close the app hoping to uncover a desktop. | **Source-effective session shutdown.** `RequestWindow._logout` and its Escape/result/approval callers use `KioskLogout.begin`; public GNOME logout has a 750-ms handoff, then app quit. App-unit success/failure starts `gnome-session-shutdown.target`. No desktop fallback is selected. | Observe GDM with no residual station desktop, then fresh usable passwordless entry; authentication denial/Cancel retain the request and grant nothing. Preserve ordinary-account continuity. Injected app/service failure is engineering coverage, not a substitute for public exit. |

#### C07a1 public selection qualification

The registered
[`check_e2e_public_desktop_selection`](../../tests/integration/check_e2e_public_desktop_selection.py)
binding passed both targets through
[`PublicDesktopSelectionJourney`](../../tests/e2e/public_desktop_selection.py).
The [building-block owner](../TestAutomation/E2E-Building-Blocks.md#public-desktop-selection)
owns its English GNOME 50 GDM adapter, independent launch observer, 120-second
machine checkpoints and 1800-second worker envelope.

| Target | Ordinary-account positive | Direct station selection and chooser → Cancel → station |
| --- | --- | --- |
| `onpc-Ubuntu26.04` | Jordan publicly chose Ubuntu; `ubuntu.desktop` resolved `/usr/bin/gnome-session --session=ubuntu`, with the actual Ubuntu manager, Shell and usable desktop. | Both normal passwordless attempts exposed no station chooser and reached a usable request-only session. |
| `onpc-Fedora44` | Jordan publicly chose GNOME; `gnome.desktop` resolved `/usr/bin/gnome-session`, with the actual `--session=gnome` manager, Shell and usable desktop. | Both normal passwordless attempts exposed no station chooser and reached a usable request-only session. |

Each station result independently bound `oh-no-parent-control.desktop` and
`gnome-session --session oh-no-parent-control` to the station UID, active local
Wayland `gdm-password` session, actual
`gnome-session-manager@oh-no-parent-control.service` process and GNOME Kiosk.
Public Riley/Jamie request controls were usable. Exact owned saved routing and
public policy restoration, normal Cancel, fresh passwordless usable reentry and
owned session/VM cleanup passed. GDM saved Jordan's selected session name while
leaving its initially empty saved transport unchanged; cleanup recognizes only
that launch-bound change and restores the exact original fields.

These results establish no reachable alternate station choice in these two
normal histories, not a selected-command denial or a universal desktop fence.
No product code or admission predicate changed. C07a's
[local graphical-session result](#c07a-local-graphical-session-result) consumes
this exact result with its separate complete both-target usability gate.

#### C07a local graphical-session result

C07a retained the existing mechanism: the qualified direct station selection and
ordinary chooser → Cancel → station paths exposed no alternate station desktop
choice on either target. C07a1's ordinary desktop positives and independent launch
observations remain applicable; no selected-alternate-command denial is claimed.

`check_e2e_confinement_usability` passed on `onpc-Ubuntu26.04` and
`onpc-Fedora44`: fresh passwordless usable requests, wrong-password rejection and
independent Cancel with zero grant, genuine approval and independent grant read,
normal exit, fresh usable entry and public settings/grant restoration. Owned
session/VM cleanup and baseline restoration passed. No product or automation
changed, so no new fault boundary, backend review or package build was required.
Request-session desktop attempts remain with C07s.

#### C07s request-session result

C07s retained `Kiosk=true`, vendor shortcut handling and the existing fixed-action
and session-shutdown barriers. C07s1's qualified Super, Super-A, Alt+F2 and
Ctrl+Alt+T results and working ordinary-desktop controls remain applicable on
both targets: no request-session desktop-launch chain was demonstrated. This
finite result does not establish a universal desktop fence. No product or
automation changed, so no new benign/fault boundary, shared-overlay control,
backend review or package build was required.

`check_e2e_confinement_usability` passed separately for C07s on
`onpc-Ubuntu26.04` and `onpc-Fedora44`: fresh passwordless usable requests,
wrong-password rejection and independent authentication Cancel with zero grant,
genuine approval with the independent expected-grant check, normal exit and
fresh usable reentry. Public settings/grant restoration and owned session/VM
cleanup, including baseline restoration, passed on both targets. C11d/C12d
retain their final finite route-negative acceptance; this result adds no broader
desktop or terminal/TTY claim.

### Existing coverage and D02 handoff

Request-action source owners are
[`RequestWindow`](../../kiosk/oh_no_parent_control_kiosk/main.py),
[`WhatsNewPresenter`](../../kiosk/oh_no_parent_control_kiosk/whats_new.py),
[`WhatsNewDialog`](../../kiosk/oh_no_parent_control_kiosk/whats_new_dialog.py),
[`AboutDialog`](../../common/oh_no_parent_control_ui/about.py),
[`ErrorHandler`](../../common/oh_no_parent_control_ui/errors.py),
[`FeedbackDialog`](../../common/oh_no_parent_control_ui/feedback.py),
[`RichTextEditor`](../../common/oh_no_parent_control_ui/rich_text_editor.py),
[`ReminderDialog`](../../kiosk/oh_no_parent_control_kiosk/preference_dialog.py),
[`NotificationApplication`](../../kiosk/oh_no_parent_control_kiosk/notifications.py),
[`agent_locale`](../../kiosk/oh_no_parent_control_kiosk/agent_locale.py) and
[`KioskLogout`](../../kiosk/oh_no_parent_control_kiosk/session_logout.py).
The table names the complete affected methods/callers; no edit to them is
authorized merely by a source gap or an unfamiliar machine state.

Reuse these exact owners, with their current qualification limits:

- [Restricted-station cases](../../tests/e2e/restricted_station.py) 50–52:
  `PLAN`/`DENIED_PLAN`/`CANCELLED_PLAN` →
  [`onpc_restricted_station::run`](../../tests/integration/graphical_smoke/lib/onpc_restricted_station.pm)
  → [`onpc_station::restrictions`](../../tests/integration/graphical_smoke/lib/onpc_station.pm)
  send Super, Super-A and Ctrl+Alt+T.
  [`AccessibleUI.kiosk_restrictions`](../../tests/e2e/accessible_ui.py) checks
  the complete request tree and bounded outside-app absence. C07s1 separately
  qualified the shared shortcut operation's Alt+F2 result and all four ordinary
  controls on both targets, as scoped below; C07a1's public-selection binding
  is described above. Preserve stable cases and extend only a distinct missing
  outcome; these finite results are not a universal desktop fence.
- About: `check_e2e_read_restricted_station_about`,
  `RestrictedStationAboutJourney`, `AccessibleUI.open_kiosk_about/read_kiosk_about`
  and [case 192](../../tests/e2e/kiosk_about.py). Preferences/report bindings:
  [`KioskPreferencesConfinementJourney`](../../tests/e2e/kiosk_preferences_confinement.py)
  and [`KioskFeedbackConfinementJourney`](../../tests/e2e/kiosk_feedback_confinement.py)
  through their corresponding `check_e2e_kiosk_*_confinement` selectors. These
  protect offered actions; their census is not a desktop execution fence.
- Normal exits: [Cancel case 47](../../tests/e2e/kiosk_cancel.py),
  [Escape case 48](../../tests/e2e/kiosk_escape.py) and the accepted
  [short usability composition](../TestAutomation/E2E-Building-Blocks.md#short-confinement-usability-history),
  with its 1800-second worker bound. Reuse its complete approval, denial/Cancel,
  ordinary-account entry, exit and fresh-request controls on both targets.
- Host owners are [session composition](../../tests/unit/test_kiosk_login.py),
  [native/helper admission](../../tests/unit/test_prepared_kiosk_pam.py) and
  [request rendering](../../tests/unit/test_kiosk_rendering.py).
  Installed 267 `verify_session_composition` and 268
  `system_kiosk_admission.verify` check composition/account callbacks; neither
  binds a child-selected alternate command to a public desktop outcome.

D02 must resolve the finite GDM reachability/selected-command observation and
shortcut/provider gaps before choosing a fix, preserving the existing effective
action barriers. Any independent missing automation needs its own both-target
qualification before its product consumer. Freeze one demonstrated defect and
one enforcement boundary per product task; if no defect is demonstrated, retain
the existing mechanism and qualify the result. No private runtime, package
inventory, service-name allowlist or new test of task/history documents is
justified. Remote provider work stays with D01r; standalone SSH/terminal/TTY and
other child-controlled inputs stay with their remaining-plan owners. D01 started
no VM, product process or temporary allocation requiring restoration.

## D01r remote desktop route review

Select **GNOME Remote Desktop system Remote Login over RDP**, followed by its
remote GDM greeter, for `onpc-Ubuntu26.04` and `onpc-Fedora44`. This is a source
review, not provider setup, a working installed positive or a desktop-defense
pass. D01 and the completed baseline remain accepted without report inspection.
The [provider catalogue](../TestAutomation/E2E-Building-Blocks.md#remote-login-qualification-gap)
owns missing bindings; D02 reviews this map alongside the local map above.

### Provider applicability and child access

The [upstream 50.0 instructions](https://github.com/GNOME/gnome-remote-desktop/blob/50.0/README.md#headless-multi-user-remote-login)
describe two credentials: system RDP credentials reach a login screen, then
the selected Linux account authenticates at GDM. The initial credential does
not grant that account's desktop or parent approval. Review availability is
established by Ubuntu's [26.04 release package](https://packages.ubuntu.com/resolute/gnome-remote-desktop)
`50.0-0ubuntu2` and Fedora's [44 release package](https://packages.fedoraproject.org/pkgs/gnome-remote-desktop/gnome-remote-desktop/fedora-44.html)
`50.0-1.fc44`. The trace below uses upstream 50.0; installed updates, distro
patches, GDM/Shell, client version, locale and keyboard must be recorded and
checked in the future qualification. These are available target packages, not
observed VM versions or broader release qualification.

The child uses an ordinary RDP client from an account/device they control,
with legitimate access to the system RDP credential, and deliberately supplies
`oh-no-parent-control` at the remote greeter without a kiosk or administrator
password. If offered a session chooser, they select the available full GNOME
desktop rather than the request station. Use the identified station row or
explicit username entry if no row is offered, without an account-order tour.
The prohibited result is a usable full desktop as the reserved station
UID, with desktop launch controls. A remote request-only form is not that result.

Enabling Remote Login is an administrator precondition, not a child capability:
GDM and the **system** `gnome-remote-desktop.service`, system RDP enablement,
readable configured TLS key/certificate, valid initial credentials, a reachable
listener and a compatible redirect-capable client must work. Preparation uses
the provider's public `grdctl --system` interface and maintained VM routes; do
not enable anything in this review. Wrong initial credentials, absent service,
failed TLS/redirect or a blank/unusable desktop supply no kiosk-denial credit.

Exclude this provider's user desktop-sharing and single-user headless modes:
they attach to a separately established user session and do not exercise this
fresh system-login path. xrdp, VNC and other providers are outside this single
provider selection. SSH is separately owned; an SSH PAM result proves nothing
about this RDP route. An administrator-planted kiosk desktop or changed kiosk
password is outside the reviewed child-access premise.

### Authentication and selected execution boundary

The actual remote display is not the local greeter transported over SSH:

- [RDP session](https://github.com/GNOME/gnome-remote-desktop/blob/50.0/src/grd-session-rdp.c)
  `grd_session_rdp_new`/`init_rdp_session` supply the configured credentials to
  FreeRDP NLA. [Server](https://github.com/GNOME/gnome-remote-desktop/blob/50.0/src/grd-rdp-server.c)
  `on_session_post_connect` reaches [system daemon](https://github.com/GNOME/gnome-remote-desktop/blob/50.0/src/grd-daemon-system.c)
  `on_incoming_new_connection` → `serialize_remote_display_properties` → GDM
  `CreateRemoteDisplay`. Its `on_gdm_remote_display_session_id_changed`,
  `on_handle_start_handover` and `on_handle_take_client`, with
  [handover daemon](https://github.com/GNOME/gnome-remote-desktop/blob/50.0/src/grd-daemon-handover.c)
  `start_handover`, redirect/transfer the connection to the remote session.
  These credentials and handover checks do not authenticate a desktop account.
- [GDM remote factory](https://github.com/GNOME/gdm/blob/50.0/daemon/gdm-remote-display-factory.c)
  `handle_create_remote_display` calls `gdm_remote_display_factory_create_display`
  with no autologin user. [Shell verifier](https://github.com/GNOME/gnome-shell/blob/50.0/js/gdm/util.js)
  `begin` → `_getDetectedDefaultService`/`_beginVerification` → `_startService`
  selects `gdm-password` for ordinary password verification and calls
  `BeginVerificationForUser`/`BeginVerification`. GDM session handlers and
  `gdm_session_setup_for_user`/`initialize` send that service and account to
  the worker. The actual installed service must be observed, not inferred.
- [GDM remote display](https://github.com/GNOME/gdm/blob/50.0/daemon/gdm-remote-display.c)
  `gdm_remote_display_new` marks it non-local and Wayland-capable.
  [Manager](https://github.com/GNOME/gdm/blob/50.0/daemon/gdm-manager.c)
  `create_user_session_for_display` passes that identity to the login session.
  Its `are_sessions_compatible` prevents remote reauthentication from simply
  adopting an existing local kiosk session; local presence is not a desktop pass.
  `gdm_manager_handle_open_session`'s allowed-user check protects the greeter
  IPC caller, not a list of accounts permitted to receive desktops.
- [GDM worker](https://github.com/GNOME/gdm/blob/50.0/daemon/gdm-session-worker.c)
  `gdm_session_worker_initialize_pam` sets `password_is_required` for non-local
  displays and supplies `PAM_RHOST`. `gdm_session_worker_authenticate_user` and
  `gdm_session_worker_authorize_user` pass `PAM_DISALLOW_NULL_AUTHTOK` to real
  authentication/account callbacks; `gdm_session_worker_open_session` opens PAM
  before `gdm_session_worker_start_session` executes the selected program.
  Reauthentication still authenticates, but its account error is ignored by
  the vendor; an account-only barrier must not claim to protect that branch.
- [GDM session](https://github.com/GNOME/gdm/blob/50.0/daemon/gdm-session.c)
  `get_session_name` prefers current selection over saved preferences;
  `get_session_command_for_file` requires remote Wayland headless capability
  and resolves `Exec`. `gdm_session_start_session` wraps the resolved command
  in `gdm-wayland-session`. Its `set_up_session_environment` runs after PAM
  opening; do not presume `GDMSESSION` or `DESKTOP_SESSION` is a PAM input.
  The packaged [station entry](../../data/wayland-sessions/oh-no-parent-control.desktop)
  already declares `X-GDM-CanRunHeadless=true`; that flag is availability, not
  an account-specific desktop barrier.

Checkout owners are the [native module](../../tools/pam_oh_no_parent_control.c)
`kiosk_identity` → `admission`, `pam_sm_acct_mgmt` → `run_kiosk_check`, and
`pam_sm_open_session`, plus the [login helper](../../tools/oh-no-parent-control-login-check)
`main`/`verify_identity`. They bind identity and lifecycle ownership, not a
remote selected command, and deny only the qualified `su-l` service explicitly.
The [kiosk profile](../../data/pam-configs/oh-no-parent-control-kiosk-only) adds
required account/session checks; the [time profile](../../data/pam-configs/oh-no-parent-control-session-limits)
skips only product time authentication for the station, not vendor authentication.
[Distro verification](../../packaging/distro_pam.py) `verify`/`verify_time_policy`
and [Fedora configuration](../../packaging/fedora_pam.py) `configure` preserve
the vendor stack. Neither verifies every vendor authentication shortcut.
The reviewed [Ubuntu GDM PAM file](https://git.launchpad.net/ubuntu/+source/gdm3/plain/debian/gdm3.gdm-password.pam?id=ca51eed279d9f91f4400451884f888fa74392f5b)
includes `common-auth`/`common-account`/`common-session`. The upstream
[Red Hat GDM PAM file](https://github.com/GNOME/gdm/blob/50.0/data/pam-redhat/gdm-password.pam)
uses `password-auth`/`postlogin` and has an early `pam_selinux_permit` success
path; verify the effective Fedora stack and caller context before treating the
null-token flag as an unconditional gate. Preserve vendor/admin authority.

**Disposition: existing vendor password barrier to qualify; no demonstrated
missing product barrier.** The worker requests rejection of empty passwords,
but actual distro PAM ordering/success shortcuts must honor it. Do not turn
the flag, an unfamiliar PAM name, saved routing, `nologin` or an account-only
probe into a claimed refusal. If the remote login reaches execution, record
the actual service, selected desktop/command, UID and public result; the
smallest missing owner would be that demonstrated provider authentication or
selected-execution boundary. D02 must choose from the observed failure rather
than pre-authorize a service-name denylist or an invented PAM session variable.
If the vendor gate works, C07 retains it without duplicate product code.

### Finite checks, restoration and D02 handoff

| History | Required public result and distinguishing observation |
| --- | --- |
| Ordinary-account positive | With Jordan (the standard fixture) logged out of other graphical sessions and permitted to use the desktop, connect through the system credential, authenticate Jordan at remote GDM and reach a usable full GNOME desktop. Use one normal desktop launch/control and observe its result through the same remote connection, tied to the remote session and Jordan UID. A local desktop, successful handshake or process census alone is insufficient. Log out only this owned remote session. |
| Deliberate kiosk attempt | Reconnect through the same working provider, identify the station and attempt login without a kiosk password, selecting a full desktop if publicly offered. Require the specific authentication refusal and no station desktop, or an observed usable request-only destination. If authentication refuses before selection, record that no desktop command was started; do not invent a selected command. Incomplete observation, timeout and generic connection failure are inconclusive. |
| Permitted use and recovery | After the attempt, repeat the ordinary remote positive and preserve any unrelated local session. Run the existing both-target short confinement usability history for local passwordless entry, genuine approval, rejection/Cancel, exit and fresh request. A transient provider outage is a preparation/recovery failure: restore the owned dependency and repeat public use, never count the outage as protection. |

Use the [short usability binding](../TestAutomation/E2E-Building-Blocks.md#short-confinement-usability-history)
unchanged. Missing remote transport, remote-GDM ownership/credential delivery
and remote desktop/result bindings need installed qualification **before C07
product editing**, with explicit targets and finite deadlines. The catalogue
separates these small prerequisites; D02 allocates them before that consumer,
and D03 only audits delivered bindings. C11f/C12f retain the complete provider
positive/negative acceptance; this review supplies neither selector nor credit.

Existing [admission engineering checks](../../tests/integration/system_kiosk_admission.py)
`pam_callback`/`verify` use account probes or authentication flags zero, not the
remote worker/transport. Existing [native/profile host coverage](../../tests/unit/test_prepared_kiosk_pam.py)
protects account/session binding and ordinary policy; it does not exercise RDP.
Local [GDM variation](../../tests/e2e/gdm_service_variation.py) explicitly selects
the dedicated session. [Session control](../../tests/e2e/session_control.py)
`local_graphical`/`source_session` and the [UI adapter](../../tests/e2e/accessible_ui.py)
greeter discovery require local `seat0`; local qualification cannot be relabeled
remote. Reuse shared guards/mechanics, not a second runner. No new test of this
map, task briefs or historical queue entries is warranted by the test-scope mandate.

Future preparation/attempts must record original service enablement/activity,
RDP settings, credential/TLS ownership, scoped network changes and created
remote session/client identities. Restore only their owned changes through
public provider/system interfaces, preserve foreign sessions/settings, remove
owned secrets and verify ordinary remote and local kiosk use before final
restoration to the original enabled/disabled state. Capture no credential values
in the map or reports. D01r changed no provider state and allocated no VM,
product process, client or temporary input needing cleanup.

## D02 minimal desktop design decision

D02 independently reviewed the D01/D01r maps and complete affected admission,
request-action and shutdown callers. **Retain existing mechanisms; no new product
barrier is justified by the evidence currently available.** This approves a
finite conditional design, not implemented desktop prevention or installed
qualification. Trust completed baseline/cleanup work without reopening reports.

### Frozen implementation boundaries

| Consumer and route | Reviewed disposition and allowed change | Distinguishing result and adjacent control |
| --- | --- | --- |
| C07a: local GDM alternate desktop selection | **Unproven reachability; no missing barrier established.** First qualify the child's public chooser interval and current selection. If it reaches a full station desktop, fix only that actual selected-launch boundary using a supported vendor mechanism or direct owner fix. Native PAM has no selected-command input; do not invent one from saved routing, service names or session environment. | Tie the public choice to the resolved command, station UID/session and usable desktop result. Pair with the same desktop working for Jordan and dedicated passwordless request entry. Test the ordinary chooser → Cancel → station sequence without artificially delaying authentication or granting the child greeter-process authority. If no alternate route is exposed, record the exact target/action disposition and request-only result; do not claim an alternate executable was blocked. |
| C07s: request-session shortcuts | **Existing GNOME Kiosk boundary; C07s1 supplied the finite both-target qualification.** Preserve `Kiosk=true` and the vendor shortcut handling. Super, Super-A, Alt+F2 and Ctrl+Alt+T are the finite attempts; add a barrier only for a demonstrated chain to a full station desktop, at that action/launch owner. | The usable request remained without a desktop/run surface after each distinct attempt, with all corresponding ordinary-desktop controls working on both targets. Fedora uses its permanently prepared terminal chord. C07s retains its own installed usability and directly affected controls. A terminal-only result retains its remaining-plan owner. No repeated shortcut matrix across approval outcomes is needed merely to qualify the shared binding. |
| C07s: information, reports, Preferences and normal exit | **Source-effective fixed-action/shutdown barriers; retain them.** The complete methods/callers in the D01 map omit or guard external handlers/choosers, restrict notification actions, restart only the fixed agent, and shut down the session on app exit. No additional session-admission condition is justified. | Keep readable/dismissible information, useful reports, Preferences and genuine approval. Normal Parent/overlay links and Parent attachments/export remain permitted. Cancel/Escape/result/approved exit must return to GDM, followed by a fresh usable request. Exercise only directly affected controls if an owner changes. |
| C07: fresh system Remote Login over RDP | **Existing vendor password barrier to qualify; no missing product barrier established.** Use the D01r provider and actual distro authentication/launch path. If its real password requirement suffices, retain it without code. A demonstrated escape permits one fix at its narrow authentication or selected-launch owner. | Working Jordan remote desktop/control → station attempt without a kiosk password → repeat Jordan positive. Bind the remote greeter/session and actual PAM/launch result. Authentication refusal before selection means no command started, not a fabricated selected-command denial. Preserve local passwordless request use and unrelated sessions. |

Standalone terminal/TTY, SSH, other remote providers, user desktop sharing,
arbitrary station-code execution and trusted loader exploitation remain excluded
from this desktop slice for the reasons in D01/D01r and the threat boundary.
An absent provider, failed positive, timeout or incomplete observation is
**inconclusive**, never effective protection. Record applicability and results
per target; an unreachable public action is distinct from an exercised refusal.

### Refusal, default and recovery review

The [admission refusal audit](#admission-refusals-and-recovery-owners) remains the
branch inventory. D02 checked native `kiosk_identity`, `admission`, `lock_current`,
`run_kiosk_check`, all PAM entrypoints and helper `main`/`verify_identity`, including
their defaults and error returns. Ordinary accounts bypass kiosk checks;
`systemd-user` retains its lease path; unfamiliar services still receive identity/
ownership checks. The qualified `su-l` refusal is retained under its existing
non-desktop owner, not generalized to remote or unknown graphical services.

No desktop predicate may be added to the saved-routing/provisioning readbacks,
NSS lookup, optional presentation, PAM options/data, helper allocation/fork/exec/
wait/25-second timeout, lease identity/open/lock, or removal-marker error branches.
These are configuration, operational or authority results, not evidence of intent.
Keep foreign/live state, same-handle account authorization and explicit admin
denial intact. Never turn a PAM error into success or clear foreign state.
If a proposed fix touches one of these branches, freeze its representative
fault/restoration control before editing: owned dependency restoration or writer
completion must permit fresh public entry without manual product-state deletion.
Wider lifecycle/availability defects retain their existing owners and are not
closed by this review.

Pair a future local predicate with benign unfamiliar service dispatch, stale/
empty saved routing and actual dedicated execution, using the delivered D00a2/
D00a3 bindings only where affected. A discovery outage cannot become a new login
dependency. Pair an action-level predicate with useful in-app information and
the permitted ordinary/overlay action; optional content failure must not veto
the request. Pair a remote predicate with the working ordinary remote positive,
local dedicated use and owned provider restoration, never global null-password
changes or an allowlist of PAM layouts. Reuse unchanged lease/lifecycle controls;
add a new fault case only for a changed failure boundary.

Request-side review covered `RequestWindow._build`, `_result_dismissed`,
`_show_about`, `_load_users`/account callbacks, `_request_access` →
`_preferences_saved` → `_agent_prepared` → `_request_done`/`_request_failed`,
Escape/result/approval logout callers and complete `KioskLogout` fallback.
The D01 action-owner map names their shared callees. Parent denial and independent
authentication Cancel preserve the request and grant nothing; service errors
must not masquerade as approval or a successful desktop defense. No edit to
these authorization/feature paths is allocated merely to harden desktop entry.

### Qualification allocations before product edits

These are finite installed slices, each on `onpc-Ubuntu26.04` and
`onpc-Fedora44`, with a 20–30 minute budget including its owned restoration.
Public selection and shortcut results were delivered by C07a1 and C07s1 below;
remote preparation and repeated exact restoration passed on both targets in C07r1;
the other remote slices are planned, not registered selectors or completed
prerequisites. At the selected
future consumer, insert its missing slices immediately before it under the
[prerequisite contract](../Execution-Plans.md#execution-and-delegation), with
valid briefs and backward Requires links. D02 needs no live prerequisite and
does not insert or execute later consumers' work. Split a slice further before
implementation if its safe implementation/qualification cannot fit that budget.

- **Before C07a: Check public desktop selection — delivered by C07a1.** The
  [qualified binding](#c07a1-public-selection-qualification) pairs ordinary public
  chooser selection/cancellation with independent current command/session/process
  observations and restored usable request entry on both targets. Both station
  histories have an exact no-public-chooser disposition, not alternate-command
  denial credit. Privileged `gdm_service_variation.peer_selection` remains outside
  this public input route. C07a's own acceptance is unchanged.
- **Before C07s: Check desktop attempts from the request session — delivered by
  C07s1.** `check_e2e_station_shortcuts` and its shared
  `station_shortcuts.StationShortcutsJourney` / `onpc_station_shortcuts::run`
  passed on both targets; exact provider scope and limits are in the
  [building-block owner](../TestAutomation/E2E-Building-Blocks.md#request-session-shortcut-results).
  Each target observed ordinary overview, app grid, Run dialog and terminal,
  paired with four request-only usable station results. Fedora's Ctrl+Alt+T
  control is permanently configured by baseline preparation; Ubuntu retains
  its existing binding. The adapter resolves the unnamed Run dialog by its
  public label and closes it before testing the terminal chord. No request-session
  desktop-launch chain was demonstrated. Normal closure, Cancel/fresh entry,
  exact public settings restoration and runner cleanup passed on both targets.
  C07s still owns its unchanged installed usability and directly affected controls;
  this qualification grants no consumer or complete-case acceptance. Reuse
  `restricted_station.py` cases 50–52, `onpc_station::restrictions` and their
  shared entry/results, including the qualified Alt+F2 operation and both-target
  ordinary-desktop witnesses. `AccessibleUI.kiosk_restrictions` is a complete
  observed UI-tree/control census with a two-second observation interval, not
  an already-qualified universal desktop fence. Product reads/actions must use
  the Application UI API; keep external desktop observations/input at their
  qualified provider owner. New missing bindings need their own qualification
  before consumption; do not replace public outcomes with a process census or
  private state.
- **Before C07: Prepare remote sign-in; connect safely; check ordinary remote
  desktop use; check the station attempt and recovery.** The four finite slices
  and their return conditions live in the
  [remote qualification owner](../TestAutomation/E2E-Building-Blocks.md#remote-login-qualification-gap).
  Complete them before any provider product edit, not at D03 or final acceptance.

For new bindings, freeze machine-stage deadlines at 120 seconds for connection,
challenge acquisition, post-input result and each owned cleanup operation.
Human reading/decision/authentication think time is not a machine-startup test.
Preserve the existing 1800-second worker envelope as its outer limit; do not
claim its watchdog is pause-aware or add timer machinery in this review.
Timeouts remain inconclusive and uncertain input is never replayed. If safe
cleanup cannot complete, retain the owner and leave the consuming task open.

Every product fix still owns the unchanged
[short usability history](../TestAutomation/E2E-Building-Blocks.md#short-confinement-usability-history)
on both targets for its final candidate: Riley/Jamie, 900 seconds daily, zero
initial grant, 75-second soft-included request, independent zero-grant rejection/
Cancel endpoints, genuine 975-second approval, exit/reentry and public restoration.
Reuse its exact binding and 1800-second envelope. Add ordinary desktop login
when shared admission changes, a shared-overlay request only when that caller
changes, and affected enforcement controls only when authorization/enforcement
can change. Keep each fix plus review/build and this gate within 30–60 minutes;
split independent defects before editing rather than postpone a target's gate.

Affected host owners remain `test_kiosk_login.py`, `test_prepared_kiosk_pam.py`
and `test_kiosk_rendering.py` linked in D01; only a changed owner receives its
scoped regressions. Retain installed 267/268 as composition/account engineering
checks, not selected-desktop acceptance. Reuse the existing About, Preferences,
feedback and Cancel/Escape bindings for affected actions; no general feature
campaign, duplicate guard matrix, task/history tests, new registry or proof
archive is allocated. Effective barriers need qualification, not replacement.

### Independent design review result

Independent Astra xHigh review: **Usability priority: passed. Threat scope:
passed. Denylist/default access: passed.** Approval is for the conditional
no-code design above, with no new protective rejection approved. The actionable
review findings are incorporated: separate ordinary remote desktop qualification
from the station/recovery slice; qualify public chooser access rather than
privileged selection; limit the UI-tree census claim and add the missing
shortcut/ordinary-desktop witnesses; distinguish target-specific unreachable,
inconclusive and effective results; keep machine deadlines distinct from human
time and the existing worker limit. Existing availability gaps remain open under
their owners. D02 performs no product edit, VM/provider operation or live
acceptance and owns no runtime state needing restoration.

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
