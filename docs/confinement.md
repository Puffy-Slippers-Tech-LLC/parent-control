# Kiosk confinement: execution plan

The reserved kiosk account may run only the product's kiosk session and its
explicitly required services. It must never gain arbitrary execution or a normal
desktop, including through another graphical session, terminal or SSH login.
Confinement remains unfinished. This plan owns qualification of that boundary;
completion does not establish full product release acceptance.

Product expectations belong to the
[specification](Specification.md); implementation details belong to
[Lifecycle](SystemDesign/Lifecycle.md) and
[Package removal](SystemDesign/Package-Removal.md).

## Phased execution plan (current)

**Next phase: 3 — Qualify kiosk isolation. Step 5 is next.**

For **"execute next step in confinement.md"** or **"execute next Phase in
confinement.md"**, execute only the first unchecked step in the active phase,
including validation and owned cleanup, then stop. Preserve the existing step
numbers. Planning, a blocker or a partial result never closes a step or phase.
Record only useful current inputs, evidence, limits and remaining work here.
After the active phase's last step passes, check its exit gate and set the next
phase/step for the following session; do not start that phase in the same session.
If a step exposes substantial implementation or multiple independent installed
histories, split its unchecked row into bounded numbered steps before execution,
preserving its confinement assertions. Update the next-step marker and execute
only the first resulting step.

The 2026-10-13 scope decision removes general product qualification from this
plan. Previously completed broad functional work supplies only reusable evidence
for the assertions it actually proves. General feature tasks remain with the
[E2E execution plan](TestAutomation/E2E-Execution-Plan.md) and
[task queue](TestAutomation/E2E-Task-Queue.md#ordered-task-queue); this plan neither
changes their next-task pointer nor closes their tasks. Earlier completed steps
are omitted; the remaining step numbers are preserved.

| Done | Phase 3 step | Required result before stopping |
| --- | --- | --- |
| [ ] | **5 — Execution boundary and real-session census** | On both targets, qualify the current candidate's confinement matrix, active namespace callbacks and platform integration checks; reuse retained evidence only after verifying exact input applicability. Prove allowed native execution before denials, actual final GDM execution restrictions, rejected alternate-session/terminal/SSH admission, policy-loss refusal, and the strict real waiting-session census. Record any assertion missing from the registered routes and close only after its maintained installed coverage passes. Finish owned cleanup. |
| [ ] | **6a — Approved kiosk request** | Complete restricted-station case 50 on both targets under its existing recipe: usable request/authentication, no desktop/terminal/management escape, and normal return to sign-in after approval. Preserve the complete case's assertions and finish owned cleanup. |
| [ ] | **6b — Denied kiosk request** | Complete restricted-station case 51 on both targets: authentication denial leaves the kiosk confined and normal exit returns to usable sign-in. Preserve the complete case's assertions and finish owned cleanup. |
| [ ] | **6c — Cancelled kiosk request** | Complete restricted-station case 52 on both targets: cancellation leaves the kiosk confined and normal exit returns to usable sign-in. Preserve the complete case's assertions and finish owned cleanup. |
| [ ] | **7 — Exposed surfaces and required services** | On both targets, prove About, Preferences and error reporting cannot launch external handlers, file choosers, management controls or arbitrary programs. Verify the confined editor's native WebKit/scanner route and required service roles; retain real scanner proof and usable in-app error reporting without sending feedback. Use existing applicable qualification first; add only missing confinement coverage, not full feature histories. Finish owned cleanup. |
| [ ] | **8 — Shared-integration collateral checks** | On both targets, verify ordinary administrator and standard-user login/desktop availability, preserved vendor PAM callbacks and AccountsService metadata, and kiosk-only scope of changed units/policies. Reuse applicable matrix evidence. Add only missing checks for collateral effects of confinement changes; full Parent/child/overlay feature acceptance is outside this step. Finish owned cleanup. |

Step 5 replaces the former natural-reminder step under the scope decision above.
Reminder editing/delivery, fullscreen banner behavior, child time exhaustion and
Wellbeing settings/lifecycle are no longer prerequisites of confinement. Their
remaining implementation, acceptance and message-value decisions stay with their
existing catalogue/queue owners. This documentation change supplies no new
installed pass and closes no execution step.

| Done | Remaining phase | Required exit gate |
| --- | --- | --- |
| [ ] | **3 — Qualify kiosk isolation** | Current-candidate execution/admission and namespace checks, real-session census, essential request outcomes, exposed-surface restrictions, required native/service positives and bounded ordinary-user collateral checks pass on both targets. Keep engineering and customer results separate. |
| [ ] | **4 — Qualify confinement lifecycle and close** | Latest-version activation/reboot and removal/reinstall/purge/retry preserve kiosk execution/admission barriers and account ownership on both targets. Final security review and affected confinement regressions pass; every in-scope escape route and acceptance gap is reconciled. |

### Phase 4 session steps

Phase 4 follows Phase 3's exit gate and requires separate sessions. Once selected,
execute only the first unchecked row below. The
[removal design](SystemDesign/Package-Removal.md) and
[installed runner](../tests/integration/README.md#running-the-current-installed-suite)
own mechanics and expectations.

Phase 4 tests only the latest version. Historical package-upgrade testing and
predecessor package assets are not required. Lifecycle qualification covers
security transitions that could leave the reserved account usable without its
confinement, plus restoration of shared login integration. General saved-data
migration is not a closure gate; run targeted migration regressions only when a
confinement change affects that code or state, following the
[data migration design](SystemDesign/Data-Migration.md).

| Done | Phase 4 step | Required result before stopping |
| --- | --- | --- |
| [ ] | **1 — Coverage and verified inputs** | Map remaining confinement lifecycle obligations to registered routes and assertions; record missing installed coverage explicitly. Prepare latest-version DEB and RPM assets through the maintained builder. Record source provenance, package hashes, returned allocations, affected selectors and report-retention needs. Preparation proves no installed lifecycle behavior. |
| [ ] | **2 — Latest-version activation and reboot boundary** | On both targets, verify policy loading, safe refusal before required reboot, and confined kiosk readiness after a new boot against exact inputs. Verify account identity/classification and admission gates survive restart. Check only activation behavior needed to prevent an unrestricted kiosk session; general notice wording and saved-data migration acceptance remain with their owners. |
| [ ] | **3 — Ubuntu removal history** | Pass the complete registered `removal::test_remove_reboot_reinstall` history on current DEB input: active-kiosk and foreign hook/PAM refusals, successful inactive removal/account finalization, reboot, retained-state reinstall, packaged purge, reboot and fresh reinstall. Establish durable kiosk denials until owned account deletion, correct PAM/policy restoration, ordinary login/desktop availability and other-account preservation. |
| [ ] | **4 — Fedora removal history** | Pass the same complete maintained history on current RPM input, including native DNF removal and packaged purge, restored authselect, enforcing SELinux, account finalization, retained/fresh reinstall behavior and ordinary-user preservation. |
| [ ] | **5 — Ubuntu interruption and recovery gaps** | Complete the additional installed histories identified in step 1 for interrupted/aborted cleanup, rollback and safe retry, durable admission barriers across payload erasure, and foreign/substituted ownership state. Prove preservation on refusal and successful owned finalization after resolution. Account for prior step 3 assertions without counting host-only fault fixtures as installed proof. |
| [ ] | **6 — Fedora interruption and recovery gaps** | Complete the corresponding RPM histories, including failed post-erase recovery through normal reinstall/reboot and repeated packaged purge. Preserve foreign state and recovery records until successful owned cleanup; verify the same confinement/account barriers and ordinary-user invariants. Reuse valid step 4 evidence only for the assertions it actually covers. |
| [ ] | **7 — Independent native-boundary review** | Review the original partial fix against `697a4c30` and all subsequent tracked/untracked confinement changes affecting GDM/PAM, credentials/teardown, locks/leases, executor roles, MAC transitions, private mounts/inodes/FDs, reexec and namespace callbacks on both distros. Apply the [independent-review checklist](#primary-source-routes-and-independent-review-checklist); record findings and resolve demonstrated defects with affected checks before closing this review slice. |
| [ ] | **8 — Independent lifecycle/security review** | Review the remaining confinement change set: package/install/activation/removal ownership, account metadata/recovery, vendor drift, executable/plugin/service APIs, kiosk surface restrictions and collateral effects on ordinary accounts. Include test/harness ownership, provenance and evidence quality. Reconcile both review slices with the five scoped work groups; keep demonstrated defects and unproven confinement behavior open until resolved. |
| [ ] | **9 — Final candidate and host validation** | After the final confinement fix, run affected host regressions and `make build` for package-affecting changes; prepare and verify final format-specific package inputs and matching snapshots. Record exact candidate identities and which earlier installed/customer results remain applicable. Schedule every invalidated confinement history as a bounded follow-up before closure; include schema regressions only if affected. |
| [ ] | **10 — Final Ubuntu qualification** | On the final DEB input, pass the confinement and namespace matrices, strict real waiting-session census and affected confinement/public kiosk regressions. Retain applicable lifecycle proof and Phase 3 results; repeat invalidated in-scope histories through their complete maintained routes. Record remaining limits and finish owned cleanup. |
| [ ] | **11 — Final Fedora qualification** | Perform the corresponding final RPM confinement, census and affected public kiosk qualification, with enforcing SELinux and applicable lifecycle proof. Retain applicable Phase 3 results, complete required in-scope follow-ups and finish owned cleanup. |
| [ ] | **12 — Reconcile and close** | Reconcile the five scoped work groups against retained evidence: kiosk-only admission/execution, confined essential flows/surfaces/services, safe lifecycle transitions, shared-integration collateral checks and both final review slices. Verify report retention and completed owned cleanup; update this plan and deliver the independent-review handoff covering the preceding partial fix. Check Phase 4 only when its confinement exit gate passes. Broader product acceptance remains separate. |


The maintained removal selector owns a continuous five-phase reboot history;
steps 3 and 4 keep one complete history per distro. Do not split its private
phases into apparent independent passes. Steps 5 and 6 address remaining
confinement recovery obligations without duplicating proven refusals. A shared
selector may also check general product behavior: preserve its complete
assertions, but do not add unrelated feature implementation as a prerequisite
of this plan. Independently proven confinement results retain their exact scope;
failures follow the owning regression contract.

Later source/package changes require affected requalification. Preserve useful
historical evidence while reopening or adding bounded follow-ups. Final checks
remain per distro and per history where further subdivision is needed.
Historical package-upgrade coverage is outside Phase 4's scope and does not
block closure. A required in-scope acceptance gap or unaccepted scope limit
keeps closure open.

## Scope and review baseline

The five work groups define the confinement scope and closure obligations:

1. Kiosk-only login/session admission and durable owned account routing/classification.
2. Actual execution boundaries for GDM, the user manager and every required role,
   including service APIs, writable configuration/code, plugins, loaders and FDs.
3. Usable essential request/authentication/exit flows and confinement throughout
   exposed dialogs and required WebKit/scanner, notification and Wellbeing services.
4. Safe latest-version activation/reboot/removal/reinstall/purge/retry transitions:
   the reserved account never remains usable without its execution/admission barrier.
5. Independent confinement review on both distributions and bounded collateral
   checks for ordinary accounts affected by shared PAM, policy, units or metadata.

General reminder CRUD/delivery/text/fullscreen/persistence, child screen-time
exhaustion, Wellbeing settings/lifecycle correctness, Parent/overlay information
and diagnostic-download workflows, multilingual feature histories and the full
parental-preference migration chain are outside confinement acceptance. Their
product requirements remain unchanged under their existing owners. AccountsService
repair of the reserved kiosk's classification/routing remains in scope.

Each added check or prerequisite must prove a confinement obligation, enable its
necessary observation, or protect identity/ownership/input safety. Regressions
directly affected by a confinement fix still require scoped validation. Report
unrelated feature defects to their owner without silently expanding this plan.

Closure requires installed proof on both targets that:

- Only the dedicated product session and explicitly required executable roles
  can run as the kiosk account; alternate sessions, terminals, SSH, arbitrary
  programs and interpreter/plugin/configuration/FD/service-API escape routes deny.
- The actual GDM executor, user manager and every kiosk process/thread retain
  the required enforcing boundary, including authentication and teardown.
- Missing, permissive, stale, substituted or interrupted security state denies
  admission/execution safely; reboot, reexec and package lifecycle cannot expose
  an unrestricted surviving account or manager.
- Essential request/authentication/exit flows work under that same boundary,
  and every exposed product surface retains its restrictions.
- Independent review covers the complete confinement change set and original
  partial fix; no demonstrated bypass or unproven required boundary remains.

An absent desktop window, failed command, preview or host test is insufficient
security proof. Require successful allowed controls and independently observed
enforcement. Missing coverage, a setup failure or an inconclusive negative stays
open; do not close a step by weakening its assertion. Completion establishes
the tested confinement guarantee within the attacker model below, not an
absolute guarantee against every future vulnerability.

The kiosk account may use only the request app and its necessary services.
Broker/D-Bus/Polkit authorization still owns data access and parent authority.
Compromised root/kernel policy and administrator credentials are outside the
attacker model; service APIs, user unit files and interpreter/plugin injection
remain in scope. Owned product workarounds are allowed; no upstream campaign or
published upstream fix is a prerequisite.

The original partial fix is `3e0f2af6f9c49e9da0df816f08f39b5c2a2b56fc`,
`Harden kiosk PAM session routing and admission diagnostics`, against parent
`697a4c30`. Review it and every subsequent confinement change, including
untracked files; a latest-commit diff or this prose alone is insufficient.
Preserve unrelated work. Do not install on the development host or return to
the released incident machine.

The incident admitted the reserved account into ordinary Ubuntu GNOME while
AccountsService recorded `Session="ubuntu"`. The exact initiating event is
unproven. Preferred-session provisioning did not enforce execution; GDM 50.1
does not invoke the legacy PreSession hook. The partial fix added native PAM
routing checks and a serialized login lock, but its save-timing marker did not
constrain the final exec or systemd user manager. Current admission removes that
marker: correct preferences are read-only checks; wrong preferences are repaired
and that attempt is denied. The final native/MAC gate enforces the actual exec.

The v1.4 kiosk release note in [Version history](VersionHistory.md) describes
the intended fix, not acceptance. What's New synchronization still requires
the explicit request under [Localization](SystemDesign/Localization.md#whats-new-translation-workflow).

## Technical boundaries

### Native PAM and private executable view

[Native PAM](../tools/pam_oh_no_parent_control.c),
[native confinement](../tools/kiosk_confinement.h),
[preparation](../tools/kiosk_confinement.py) and
[PAM integration](../packaging/kiosk_confinement.py) apply the final session gate
in the actual `gdm-password`/`systemd-user` caller, after vendor callbacks,
including systemd's parent executor. A helper-only transition is insufficient.

The caller validates the root-0600 lock and root-0700 runtime tree, invokes
bounded preparation, creates a private recursively read-only executable view,
clears PAM-granted ambient capabilities and installs the MAC boundary.
No subprocess runs after the final MAC operation; failed prerequisites deny.

Ubuntu immediately applies `aa_change_profile` and verifies the enforcing label.
An unconfined caller's `change_onexec` did not provide the required initial exec
check. Fedora GDM verifies a pending raw exec context whose private entrypoint
type constrains the actual next executable. Fedora's single-threaded systemd
executor clears vendor pending context and uses `setcon_raw` to enter
`onpc_kiosk_manager_pam_t` before returning from PAM. Its surviving `sd-pam`
child inherits current confinement through teardown. Only private manager/
executor entrypoints can transition onward; no reverse dynamic transition or
`init_t` census exception is allowed.

Preparation verifies package-created account identity, enforcing policy and
successful policy-load attestation, then copies a finite native ELF inventory
to independent root-owned inodes. It never hardlinks or relabels global distro
executables. Canonical aliases are deduplicated and conflicting roles refused;
content/canonical-path identity supports identical-byte reinstall.

An owned directory skeleton supplies independent dentries from `/usr` to every
protected executable/library/plugin parent. Trusted siblings are recursively
read-only binds; private copies occupy owned entries. The completed tree is
attached over `/usr` last, using descriptor-pinned source/target bindings.
Do not revert to individual mounts on shared global directory dentries:
package unlink/rename can detach those mounts across namespaces and expose new
bytes. Exact versioned `libsystemd-*.so` libraries are pinned with systemd for
coherent reexec; the GStreamer plugin parent is reserved even when its Python
plugin is absent.

Preparation bounds are four completed generations per boot, 512 MiB of input
per generation and 32,768 directory entries. Reclaim only owned incomplete
preparation under its lock; completed generations survive until reboot.
GDM requires a live manager with the expected UID, exact enforcing label and
matching private generation. Stale managers deny with reboot-required
diagnostics; configuration never kills or silently restarts them.

### PAM ownership and callbacks

Integration preserves exact original/generated PAM bytes, trusted distro
symlinks and vendor-derived override identity. Foreign edits, unsafe files,
pending changed `.dpkg-dist`/`.rpmnew` inputs and unsupported vendor changes
require reconciliation. Interrupted updates retain the still-published owned
generation. All audits share logical-line parsing for spaces, tabs,
continuations and includes; dangling local overrides and unsupported spellings
fail closed.

Expand session control flow, includes and substacks to reject early success or
jumps bypassing the final gate. Direct vendor keyring and namespace callbacks
receive a kiosk-only guard:

```text
session [success=1 auth_err=ignore default=die] pam_succeed_if.so quiet user = oh-no-parent-control
```

Ordinary users retain original callbacks/options. Nested unsupported callbacks,
unknown modules and jumps crossing guard insertion are refused. Namespace open,
close, init scripts and cleanup remain unreachable for the kiosk.

Supported vendor `systemd-user` stacks have no auth group; added auth/setcred
callbacks, including through `@include`, are refused. The owned native
auth-group rule performs only kiosk service/account identity checks and
credential setup/deletion; it never authenticates the kiosk. Ordinary users
return `PAM_IGNORE` and retain explicit `auth include other` fallback.
This prevents implicit global credential callbacks before confinement and in
surviving teardown helpers. Real establish/close/delete/end statuses and
post-parent-exit denials remain required engineering assertions.

### Fixed launchers and distro integration

[Policy generation](../tools/kiosk_confinement_policy.py) separates executable
roles; [native fixed launchers](../tools/kiosk_session.c) reject caller arguments
and clear startup injection. SELinux declarations use deterministic role order.

| Launcher | Fixed purpose |
| --- | --- |
| session | `gnome-session --no-reexec --session=oh-no-parent-control` |
| app | `python3 -I /usr/bin/oh-no-parent-control` |
| notifications / notification-client | Installed notification script / fixed-tag `gnome-service-client`, using isolated Python |
| wellbeing | `gjs -m` with the installed service script |
| cleanup | `systemctl --user unset-environment` for declared display variables |
| audio | WirePlumber with system-only config/data and disabled default Lua/native fallback search |
| packages | Fixed 20-package RPM diagnostics query, root-only configuration/macros, `HOME=/` |
| dbus | Fedora `dbus-broker-launch --scope user` after clearing startup configuration in the service domain |

No generic shell, Python, GJS, GNOME Shell or arbitrary WirePlumber route is
available to the manager/general service role. Fixed GJS entry includes Ubuntu's
canonical `gjs-console` alias. GIO uses the local filesystem backend to avoid
unneeded GVfs activation. The optional GStreamer Python plugin cannot acquire
executable mappings in the confined view. WirePlumber's trusted custom Lua
searcher remains available; Lua is not itself the security boundary. Renew
bounded source/installed qualification when reviewed distro/module inputs change;
existing review does not attest to every optional plugin.

The kiosk manager alone receives the private `SYSTEMD_UNIT_PATH` ending in a
colon to retain vendor search paths. Ubuntu's Wellbeing override disables
`NoNewPrivileges`. WirePlumber additionally disables its measured implicit-NNP
settings: `LockPersonality`, `MemoryDenyWriteExecute`, `SystemCallArchitectures`
and `SystemCallFilter`. Other accounts retain vendor hardening. PipeWire retains
NNP/seccomp and stacks its zero-exec AppArmor profile; WebKit and scanner stack
additional profiles whose intersection removes bootstrap mount/user-namespace
authority. Do not replace these with broad interpreter execution or unrestricted
shared `ix`.

Ubuntu masks six finite Snap activation units only in the kiosk unit path.
Private D-Bus Settings/Launcher definitions point to the masked session agent
and retain an inert fallback, preventing direct vendor `snap userd` activation
around the mask. Ordinary sessions retain vendor units and activation.

Fedora's manager needs object-identity permission for vendor-labelled runtime
sockets, with no process-identity or executable-file creation/relabel grant.
The intermediate PAM domain can write systemd's inherited `kernel_t` datagram
handoff socket and has `noatsecure` only for its private-manager transition,
preserving trusted `XDG_RUNTIME_DIR`. The separate same-domain native dbus
launcher needs no such grant. Inherited Unix-stream I/O preserves journaling;
confined names may be acquired on the service-domain user bus, not arbitrary
system-bus labels. Private nosuid mounts require `nosuid_transition`.
Optional generator/BPF denials do not justify speculative permissions.

### Native authentication helper identity

Both distros independently bind the vendor native
`/usr/lib/polkit-1/polkit-agent-helper-1` read-only, retaining its original inode
and privilege metadata outside the copied inventory. Required mode is `04755`
on Fedora and `0755` on Ubuntu; file capabilities are refused. Native binding
checks inode, size, timestamps and metadata before/after mount. Missing,
substituted or duplicate entries fail preparation.

Fedora's finite `policykit_auth_t` census role requires an enforcing domain,
every thread's exact mixed UID tuple, pinned native executable/metadata,
read-only file bind, private namespace/generation, live confined Polkit parent
and stable PIDFD/starttime/task snapshots. Unknown labels and `init_t` remain
rejected. Vendor `unix_chkpwd` keeps vendor executable/shadow policy and receives
only private-tree traversal/metadata needed by PAM. Ubuntu's socket-activated
root helper runs outside the kiosk account and is not a kiosk census exception.

### AccountsService classification

Nologin accounts can be hidden by distro classification. Fresh accounts use
public `CacheUser` and verified saved/visible properties. Retained hidden
accounts use the owned versioned cache adapter at `accounts-daemon` start-pre,
before cache reading. Only the unchanged package-created UID/home qualifies.

The adapter changes only unambiguous `[User] SystemAccount`, preserving other
bytes, owner, mode, xattrs and Fedora label. It pins trusted directories and
singly linked files without symlink traversal; root-group-writable distro
parents are accepted. One fixed transaction slot and an identity/digest/metadata
xattr support exact pre/postcommit recovery. Foreign or changed slots refuse;
no directory sweep, unrelated setter toggle or retained metadata deletion is
allowed. Hook failure preserves ordinary daemon availability; provisioning
independently verifies public visibility, saved state and durable cache.

The reviewed cache schema is 23.13.9. Fedora's runtime banner `26.03.0`
additionally requires exact reviewed package `accountsservice 23.13.9-16.fc44`.
Unknown versions require renewed review/qualification. The
[Lifecycle owner](SystemDesign/Lifecycle.md#startup-login-and-update-lifecycle)
defines fresh/retained routing, icon and setter behavior.

### WebKit, Glycin and scanner

[The native bubblewrap launcher](../tools/kiosk_bwrap.c) prepends a read-only
`/usr/bin` bind and forwards arguments, environment and inherited descriptors
to independently pinned distro bubblewrap. Admission swaps only its two private
bootstrap destinations; source/destination identities enter the generation.
App/services/authentication cannot invoke it directly. This supplies WebKit's
proxy inode without allowing writable executable-path placeholders.

Bootstrap policy is finite: trusted usr-merge aliases, inventory-derived WebKit
helpers/injected bundles, scanner/PTP, timezone/fonts, runtime/home roots,
observed DMA-buffer device and `/bindfileXXXXXX` metadata only to
`.flatpak-info`. Glycin has a separate finite native-decoder route with pinned
loader directories and no decoder onward exec. Only native bootstraps perform
private loopback setup and required mounts. Fedora repeat file binds retain
source types; no `bin_t` execution or payload mount/network-administration
authority is added. Never use debug/no-sandbox settings to supply acceptance.

Scanner observation begins before station login/request `Gst.init` and waits
for the actual native manager, with a bounded 300-second startup observation.
Proof requires the pinned scanner executable, enforcing scanner/parent threads,
matching generation/namespace, stable snapshots and live PIDFDs. Missing,
`not-observed`, rejected, malformed or naturally exited observations supply no
positive proof. Do not delete caches or synthesize scanner execution to pass.

The substitution canary requires a real sandboxed proxy and independent native
positive before six proxy/scanner bind/data/file attacks. Setup failures cannot
count as denials. Its own PID namespace supplies fresh `/proc`; app-role, UID,
namespace and generation proof precede every negative result.

### Exposed surfaces and required services

About, Preferences and error reporting must remain inside the restricted kiosk.
They must not provide an external-handler, file-chooser, management or arbitrary
execution route. Use public product actions/results for those customer-facing
restrictions and engineering probes for native execution boundaries.

The existing kiosk feedback qualifier supplies usable in-app editor and actual
native scanner evidence without sending feedback or invoking a kiosk file chooser.
Reuse only the assertions relevant to confinement. General editor feature
matrices and ordinary Parent diagnostic Download/Save remain with their owners.

Notification and Wellbeing services remain required confined roles. Qualify their
fixed entrypoints, startup-injection restrictions and actual enforcing processes;
preview appearance, reminder timing/text/urgency and Wellbeing preference
suppression/restoration are not confinement exit gates. Existing shared helpers
still own invocation identity, environment preservation and safe cleanup.

### Activation, installation and removal

PAM, launchers, confinement preparation/policy and login integration classify
as **reboot** because a user manager can survive graphical logout. The display
manager orders policy loading, while admission independently verifies loaded
enforcement. Both package formats share lifecycle templates.

Checkout installation/reinstallation/upgrade uses frozen `make install` with
the exact literal `INSTALL_PACKAGE` exported as `ONPC_INSTALL_PACKAGE`.
Validate actual package identity before APT/DNF; RPM package-name equality must
not be inferred from a NEVRA prefix. Keep paths as argv values, including spaces
or shell-looking bytes. See
[guest install recipe](../tests/integration/guest_install_recipe.py),
[system runner](../tests/integration/system_runner.py) and
[snapshot identity](../tests/e2e/app_snapshot.py).

Removal takes exclusive admission/routing/preparation locks and refuses live
kiosk admissions, threads, pending MAC state or stale native mappings without
signalling them. Before unloading policy it publishes durable distro-PAM
kiosk-only denials that survive payload erasure. Finalization restores exact
original PAM only after verified owned-account deletion. Abort reloads policy
before restoring gates; interrupted/foreign state retains barriers and recovery
records. Old generations without lifetime leases require the recorded boot to
end before policy removal.

Account/home deletion validates recorded identity, ownership, symlinks and
mounts and uses public AccountsService uncache. Ordinary remove retains saved
preferences/logs; purge uses the packaged action and deletes only owned data
after integration/account restoration succeeds. Retained choices do not imply
replay of cleared live restrictions or grants. RPM post-erase failure requires
normal reinstall, conflict resolution, reboot and repeated packaged purge.
[Package removal](SystemDesign/Package-Removal.md) owns the full refusal,
rollback, policy baseline, purge and reboot-notice contracts.

## Qualification and reusable evidence

The installed matrix requires an allowed native-service positive before exec
failure 203 denials, then exercises copied aliases, privilege-prefixed units,
private executable/library/plugin replacement and reexec, actual final GDM
exec/loader/open-FD/memfd routes, stale state and enforcing-policy loss/recovery.
Active/inactive removal preflights are non-destructive and prove no package
removal history.

The real-session census inspects every process/thread with any kiosk UID field,
requiring enforcing current labels, private namespace and matching generation.
Manager, app, service, Wellbeing and PipeWire roles must be present. Pending
labels or process names cannot substitute for current confinement. Diagnostics
use fixed categories and role/thread counts, without account names, command
lines or arbitrary exception/stderr text.

Keep only evidence needed to qualify or reproduce the remaining confinement work.
The references below are candidates for reuse, not current passes. Verify retained
reports, manifests, exact input applicability and final-source changes before
reuse; rerun an affected or unproven slice. Engineering probes do not establish
complete customer cases, and preparation/builds establish no installed behavior.

| Confinement evidence | Ubuntu report / allocation | Fedora report / allocation |
| --- | --- | --- |
| Execution matrix, real teardown and six bootstrap substitutions | `20261013T065344Z-87bafee5` / `onpc-system-rukm46k5` | `20261013T062323Z-b90f02cd` / `onpc-system-bvglnb3d` |
| Actual scanner and kiosk feedback editor | `20261013T065541Z-84ce3666` / `onpc-graphical-smoke-czkn9pv7` | `20261013T062642Z-e0eaa977` / `onpc-graphical-smoke-b_k883nh` |
| Active namespace callbacks and ordinary-user preservation | `20261013T033021Z-8f6970e8` / `onpc-system-1m801bty` | `20261013T033134Z-7cd26e1b` / `onpc-system-x2rfahhz` |

The first two rows used package-source SHA-256
`12fe615cecc2f796133e44951a13aeca5b0ac657368fd2193b574d4bcd3a045a`;
the namespace row used
`f06b80cb6e496850e47fbb00661054b68cbb205aaff1f53e63a8a674d93ae346`.
These differ from the last recorded candidate below; retained manifests own
their full package/helper/fixture identities. No row alone completes Phase 3.

Last recorded product candidate: package-source SHA-256
`b0c09311fe1b52b87bebd7699caab30829edc3c789329e50ae550c38eeb7b6c5`,
DEB `d9cf7f7418b3f73caedd05e04d3dc26f76284d21417a5c6cb2a0b26601f372da`,
RPM `630ab36562dd7f85d1a2b4f0cbf2f359972b6ac29fe4dcb2e5a051f5723afaf4`.
This reference does not identify a later checkout automatically; prepare or
verify current format-specific inputs before execution.

Report roots are `output/test-runs/host/reports/`; privileged allocations are
under `output/test-runs/privileged/allocations/`. System evidence includes
`evidence/guest/enforcement.xml`. Use maintained readers/exporters.

## Operating and qualification routes

Follow [AGENTS.md](../AGENTS.md), [Approval tools](Approval-Tools.md) and the
[test documentation map](TestAutomation/README.md). Read the
[VM](Mandates/VM-Mandate.MD),
[UI automation](Mandates/UI-Automation-Mandate.MD) and
[test storage](Mandates/Test-Storage-Mandate.md) mandates when their work is
triggered. This brief adds no alternate ownership or approval route.

Use registered `onpc-Ubuntu26.04` and `onpc-Fedora44`, exclusive ownership per
target and the maintained queue within its configured cap. Diagnose failures
live and validate future fixes live before full E2E; stop owned maintenance before
installed/customer runs. Use bounded independent review/diagnosis subagents
when needed, with one editor for shared policy. Never use raw SSH/libvirt or
discard foreign state to recover a test.

Run affected host checks and `make build` after the final package-affecting edit,
then verify format-specific inputs and normal snapshot matching. Subsequent
product changes require affected qualification again. Documentation/test-only
changes outside package/build dependencies do not require a package rebuild.

### Continuation order and qualification routes

For Phase 3 step 5, first verify the current candidate and retained evidence,
map every required admission/execution assertion to its registered route, then
run the missing or affected security matrices and real-session census on both
targets. Record exact inputs, results, gaps and owned cleanup before deciding
whether that step passes. This documentation update executes none of those checks.

Use `tools/run-tests --help`, `--list` and scoped system/E2E listings to verify
actual registered selectors. The commands below are routes for their owning
steps, not a batch to run in every session. The installed confinement/namespace/
platform selectors cover engineering assertions; `check_e2e_kiosk_entry` supplies
the strict waiting-session census. Cases 50, 51 and 52 independently own the
approved, denied and cancelled restricted-station journeys. The kiosk feedback
qualifier supplies native scanner/editor boundary evidence; existing case 192
can supply the kiosk About slice when its retained evidence applies. Preferences
and other uncovered surface restrictions must be mapped to actual maintained
coverage in step 7 before claiming acceptance. Documentation is not registration.

```bash
tools/run-tests system --artifacts '<current DEB or RPM allocation>' --area 'enforcement' --test 'test_kiosk_execution_confinement' --vm '<matching target>'
tools/run-tests system --artifacts '<current DEB or RPM allocation>' --area 'enforcement' --test 'test_kiosk_namespace_guard_callbacks' --vm '<matching target>'
tools/run-tests system --artifacts '<current DEB or RPM allocation>' --area 'enforcement' --test 'test_kiosk_platform_integrations' --vm '<matching target>'
tools/run-tests system --artifacts '<current DEB or RPM allocation>' --area 'removal' --test 'test_remove_reboot_reinstall' --vm '<matching target>'
tools/run-tests integration 'check_e2e_kiosk_entry' --vm 'onpc-Ubuntu26.04,onpc-Fedora44'
tools/run-tests e2e --id '50' --vm 'onpc-Ubuntu26.04,onpc-Fedora44'
tools/run-tests e2e --id '51' --vm 'onpc-Ubuntu26.04,onpc-Fedora44'
tools/run-tests e2e --id '52' --vm 'onpc-Ubuntu26.04,onpc-Fedora44'
tools/run-tests integration 'check_e2e_kiosk_feedback_confinement' --vm 'onpc-Ubuntu26.04,onpc-Fedora44'
```

Both phases use latest-version manifests only; no upgrade-assets preparation or
`--previous-artifacts` route is required. General schema compatibility and full
feature histories are separate product obligations. Saved account routing,
classification and confinement ownership/recovery records remain in this plan.

Ordinary artifact preparation uses one explicit target per invocation; keep
Ubuntu DEB and Fedora RPM inputs separate. Preparation/cache reuse cannot
substitute for the tested transition. Never read online snapshot
`snapshot.json`: it contains an ephemeral SSH credential. Privileged evidence
uses documented artifact readers/exporters, not direct private-file access.

## Primary source routes and independent-review checklist

Review complete relevant functions, callers/callees and shared state in the
implementation files linked above, the [Makefile](../Makefile),
[installed confinement matrix](../tests/integration/system_kiosk_confinement.py),
[engineering qualifiers](../tests/e2e/kiosk_entry.py) and
[host regressions](../tests/unit/test_kiosk_confinement.py).
Use exact reviewed distro package/source identities, not names or version
banners alone.

Primary technical routes include
[GDM 50.1's session worker](https://github.com/GNOME/gdm/blob/50.1/daemon/gdm-session-worker.c),
[systemd v259 execution/PAM lifecycle](https://github.com/systemd/systemd/blob/v259/src/core/exec-invoke.c),
[AppArmor stacking](https://www.apparmor.net/advanced/AppArmorStacking/),
[Linux-PAM SELinux close](https://github.com/linux-pam/linux-pam/blob/master/modules/pam_selinux/pam_selinux.c)
and [namespace callbacks](https://github.com/linux-pam/linux-pam/blob/master/modules/pam_namespace/pam_namespace.c).
The owning Lifecycle module links AccountsService and distro integration sources.

Final review must cover:

- Actual GDM timing and final exec; serialized routing/repair and lock lifetime.
- Parent executor, sd-pam forks, PAM control flow, credential/close callbacks and
  ordinary-user preservation.
- Exact loaded enforcing policy, permissive/missing-policy refusal,
  namespace/mount/FD lifetimes, executable/library replacement and reexec/reboot.
- Every role/transition, fixed argv/environment/import/plugin boundary, NNP
  tradeoffs, WebKit/Glycin mounts and Polkit privilege transitions.
- Public broker/D-Bus/systemd APIs, writable user units and command prefixes.
- Package dependencies/activation/removal ownership, vendor drift, durable
  barriers, account metadata, interrupted retry, bounds and cleanup.
- Essential kiosk request/authentication/exit flows, exposed-surface restrictions
  and required service/native-helper boundaries on both distributions; bounded
  ordinary-user collateral checks for the changed shared integration.
- Test/harness isolation and evidence: successful positives before denials,
  actual kernel errors, frozen inputs, retained report scope and honest limits.

Distinguish demonstrated defects, plausible untested gaps and harness defects.
Resolve every required confinement gap before closure; retain unresolved gaps
explicitly with their return conditions. Release notes, preview, source review
and host tests cannot substitute for installed security/public-kiosk acceptance.
