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

**Next phase: 4 — Qualify confinement lifecycle and close. Step 2a2 is next.**

For **"execute next step in confinement.md"** or **"execute next Phase in
confinement.md"**, execute only the first unchecked step in the active phase,
including validation, owned cleanup and close-out, then stop. Preserve the existing step
numbers. Planning, a blocker or a partial result never closes a step or phase.
Record only useful current inputs, evidence, limits and remaining work here.
After each completed step, commit and push its changes, including this plan's
completion update, before stopping. Stage only changes belonging to that step.
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
| [x] | **5a — Installed execution matrices** | On both targets, qualify the current candidate's complete confinement matrix, active namespace callbacks and platform integration checks; reuse retained evidence only after verifying exact input applicability. Prove allowed native execution before denials, actual final GDM execution restrictions, real credential/teardown confinement and policy-loss refusal/recovery. Finish owned cleanup. |
| [x] | **5b — Installed admission coverage** | Add and pass maintained installed coverage on both targets for rejected alternate-session, terminal and SSH admission, with successful allowed controls before denials. Exercise the installed account/routing boundary: the execution matrix's final-session fixture and host login tests do not prove this assertion. Preserve the final-exec restrictions qualified in 5a. Record any remaining admission assertion gap and close only after its maintained installed coverage passes. Finish owned cleanup. |
| [x] | **5c — Real waiting-session census** | On both targets, pass the strict census in the real waiting kiosk session against current matching inputs. Require every kiosk process/thread's enforcing current label, private namespace and matching generation, including the required manager, app, service, Wellbeing and PipeWire roles. Requalify affected 5a/5b results after any product fix. Finish owned cleanup. |
| [x] | **6a — Approved kiosk request** | Complete restricted-station case 50 on both targets under its existing recipe: usable request/authentication, no desktop/terminal/management escape, and normal return to sign-in after approval. Preserve the complete case's assertions and finish owned cleanup. |
| [x] | **6b — Denied kiosk request** | Complete restricted-station case 51 on both targets: authentication denial leaves the kiosk confined and normal exit returns to usable sign-in. Preserve the complete case's assertions and finish owned cleanup. |
| [x] | **6c — Cancelled kiosk request** | Complete restricted-station case 52 on both targets: cancellation leaves the kiosk confined and normal exit returns to usable sign-in. Preserve the complete case's assertions and finish owned cleanup. |
| [x] | **7a — About restrictions** | On both targets, pass the complete registered kiosk About case 192 with its existing assertions: readable in-app information, no external handler, file chooser, management or arbitrary-program action, unchanged request choices on return and normal exit to sign-in. Use applicable retained evidence first and finish owned cleanup. |
| [x] | **7b — Preferences restrictions** | On both targets, prove the kiosk Preferences surface, including all exposed pages and nested dialogs, cannot launch external handlers, file choosers, management controls or arbitrary programs. Add only missing confinement coverage through maintained shared operations, preserving normal return to the request form; full preference/reminder feature histories remain outside this step. Finish owned cleanup. |
| [x] | **7c — Error reporting and required services** | On both targets, prove error reporting and its in-app privacy disclosure cannot launch external handlers, file choosers, management controls or arbitrary programs. Verify usable editable in-app reporting and diagnostics without sending feedback, the confined native WebKit/scanner route and required service roles. Reuse applicable qualification first, retain real scanner proof and add only missing confinement coverage. Finish owned cleanup. |
| [x] | **8a — Ordinary login and desktop availability** | On both targets, verify real fresh graphical login and usable ordinary administrator and standard-user desktops through the maintained guarded entry and desktop observations. Preserve account identity and secret-recipient checks. Full Parent/child/overlay feature acceptance is outside this step. Finish owned cleanup. |
| [x] | **8b — AccountsService metadata collateral** | On both targets, verify preserved AccountsService cache/icon metadata for both ordinary administrator and standard-user roles throughout the maintained kiosk provisioning, daemon restart and reboot history. Extend only the missing role coverage, preserve the complete selector's assertions and finish owned cleanup. |
| [x] | **8c — Shared PAM and policy scope** | On both targets, verify preserved vendor PAM callbacks and effective kiosk-only scope of changed units/policies, including both ordinary account roles. Reuse applicable matrix evidence and add only missing collateral checks. Full Parent/child/overlay feature acceptance is outside this step. Finish owned cleanup. |

Step 5 replaces the former natural-reminder step under the scope decision above.
The 2026-10-13 coverage audit split it into 5a–5c after finding no installed
alternate-session/terminal/SSH admission assertion. The final-exec fixture uses
only the native final session callback, bypassing the installed account/routing
stack. This split preserves every original step 5 assertion; no slice alone
completes that step's execution/admission and real-session qualification.
Reminder editing/delivery, fullscreen banner behavior, child time exhaustion and
Wellbeing settings/lifecycle are no longer prerequisites of confinement. Their
remaining implementation, acceptance and message-value decisions stay with their
existing catalogue/queue owners. The earlier scope-only documentation change
supplied no installed pass and closed no execution step. The 5a results below
qualify only that slice.

The step 7 coverage audit split its independent About, Preferences and
error-reporting installed histories into 7a–7c. The three slices preserve every
original surface, native execution and required-service assertion; none alone
completes the original step 7 scope. Step 7b adds a dedicated installed
Preferences confinement qualifier; the existing feedback qualifier must account
for its in-app privacy surface before 7c can close. Case 192 supplies the
registered About history without new feature coverage.

| Done | Remaining phase | Required exit gate |
| --- | --- | --- |
| [x] | **3 — Qualify kiosk isolation** | Current-candidate execution/admission and namespace checks, real-session census, essential request outcomes, exposed-surface restrictions, required native/service positives and bounded ordinary-user collateral checks pass on both targets. Keep engineering and customer results separate. |
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
| [x] | **1 — Coverage and verified inputs** | Map remaining confinement lifecycle obligations to registered routes and assertions; record missing installed coverage explicitly. Prepare latest-version DEB and RPM assets through the maintained builder. Record source provenance, package hashes, returned allocations, affected selectors and report-retention needs. Preparation proves no installed lifecycle behavior. |
| [x] | **2a1 — Ubuntu native activation and reboot boundary** | Extend and pass the maintained DEB fresh-install/reboot history against exact inputs: required-reboot policy refusal, exact loaded/enforcing confinement policy and matching manager generation, allowed native execution before execution/admission denials, missing/stale/unenforced-policy refusal/recovery, and preserved account identity/classification and admission gates after AccountsService restart and a new boot. Reconcile observed automatic APT transaction interference through the maintained baseline fixture owner, refresh the Ubuntu baseline and finish owned cleanup. |
| [ ] | **2a2 — Fedora native activation and reboot boundary** | Pass the corresponding complete RPM fresh-install/reboot history with enforcing SELinux, exact matching inputs and all 2a1 native/account/admission/refusal/recovery assertions. Refresh stale preparation through the maintained route, account for any observed automatic package transaction interference through its baseline owner and finish owned cleanup. |
| [ ] | **2b — Real GDM activation readiness** | On both targets, observe the real kiosk admission/execution boundary in the fresh-install/reboot history: before required reboot entry is safely refused or confined with the restart-required presentation; after a new boot the real waiting session passes the strict enforcing-label/private-namespace/matching-generation census with all required roles and usable kiosk readiness. Retain applicable 2a proof, use exact matching inputs and finish owned cleanup. General notice wording and saved-data migration acceptance remain with their owners. |
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


The step 2 coverage audit splits native installed activation from the real GDM
presentation/session history. The first cold Ubuntu attempts exposed automatic
APT transactions changing the generation during the matrix, requiring a shared
baseline fixture change. Native qualification is consequently bounded per
distro in 2a1–2a2. These slices preserve the original step's policy,
account, admission, execution and readiness obligations; no slice alone closes
step 2. Native final-session fixtures do not establish real GDM entry or the
restart-required presentation, and an app-snapshot restore cannot substitute
for the fresh-install/reboot transition in either slice.

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
It also rechecks installed enforcement for every configured profile/domain;
SELinux's global enforcing mode alone does not exclude a permissive domain.
Manager, app, service, Wellbeing and PipeWire roles must be present. Pending
labels or process names cannot substitute for current confinement. Diagnostics
use fixed categories and role/thread counts, without account names, command
lines or arbitrary exception/stderr text.

Keep only evidence needed to qualify or reproduce the remaining confinement work.
The earlier references below are candidates for reuse, not current passes.
Verify retained reports, manifests, exact input applicability and final-source changes before
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
These differ from the current 5a candidate below; retained manifests own
their full package/helper/fixture identities. No row alone completes Phase 3.
The recorded execution and namespace report/allocation locations were unavailable
to the maintained artifact reader during 5a; neither historical row was reused.

Current 5a product candidate: package-source SHA-256
`b0c09311fe1b52b87bebd7699caab30829edc3c789329e50ae550c38eeb7b6c5`,
DEB `daa9c180960e1dfc72e026a7019bb71b2b63db3bd4c867a62e300f05f81b94fa`,
RPM `630ab36562dd7f85d1a2b4f0cbf2f359972b6ac29fe4dcb2e5a051f5723afaf4`.
This reference does not identify a later checkout automatically; prepare or
verify current format-specific inputs before execution.

### Step 5a qualification — 2026-10-13

All three complete `enforcement` selectors passed on each target:
`test_kiosk_execution_confinement`, `test_kiosk_namespace_guard_callbacks`
and `test_kiosk_platform_integrations`. No product or test code changed.

| Current engineering result | Ubuntu report / allocation | Fedora report / allocation |
| --- | --- | --- |
| Execution matrix, real teardown and six bootstrap substitutions | `20261013T223121Z-4f8c4f9d` (category 1 only) / `onpc-system-35n9gv0g` | `20261013T223557Z-78f6da8b` / `onpc-system-172m0c6j` |
| Active namespace callbacks | `20261013T223340Z-49e0d3bf` / `onpc-system-pooys6eh` | `20261013T223854Z-14054b99` / `onpc-system-w39waamn` |
| Platform integration and native service APIs | `20261013T223440Z-f4bf1efe` / `onpc-system-_x7ycddn` | `20261013T224024Z-759b5400` / `onpc-system-ar8n7l_8` |

The format-specific builder returned
`output/test-runs/host/allocations/onpc-test-artifacts-w9ad5p2m` (DEB) and
`output/test-runs/host/allocations/onpc-test-artifacts-gts9ocwz` (RPM).
Both verified manifests bind the candidate above to revision
`f84b688281f27ade9e737b2b6a2930646db3541c` and fixture SHA-256
`b605097e70b69abb86e32142a36ab762185d80f8df2e160dbdded5329d5d82ab`.
Each attempt validated package sources and matched its retained app snapshot.
The corresponding selected-input hashes were identical across targets:
execution `a99731e6082624a16a53232a0a90dcb19185ecc81006d5ba43d9a49c90ffef9a`,
namespace `49ed0ef821e94e1a365857b01806e02af84b5aa36dbf00cc963b0b1f909c3a2b`,
platform `3799fb4b2e13e180ca40e91b0671776fe1c0fc5c29ae8cdf6c920cb909b6eaf4`.
Attempt `evidence/result.json` owns baseline and complete input identities;
platform `evidence/guest/enforcement.xml` retains actual distro package,
mapped-native and script identities.

Both execution matrices proved native positives before manager/final-exec
denials, replacement/reexec isolation, stale-state refusal, six bootstrap
substitutions and policy-loss refusal/recovery. Establish, close, delete-credential
and end callbacks all returned zero, with post-parent-exit execution denials.
Namespace checks proved ordinary callbacks run while the kiosk skips them.
Platform checks proved trusted native loading before an independently observed
kernel mapping denial for the user-owned copy, restricted Lua startup paths and
service profile/context restrictions; Fedora's denial recorded `permissive=0`.

The first Ubuntu invocation passed its execution case, then refused the distinct
namespace selector with infrastructure category `selection:resume-inventory-changed`;
its third selector did not run. Namespace and platform checks subsequently passed
as separate invocations with unchanged assertions. The grouped report is not an
overall pass. Use one system selector per invocation for this continuation.

All six attempt results report passing product, infrastructure and cleanup
outcomes with `cleanup_phase=complete`. Each restored and verified its outer
baseline using metadata-only checks; both pinned VMs were confirmed powered off.
Markdown links passed. Only this plan changed, outside `PACKAGE_SOURCE_FILES`
and build-tool dependencies, so no additional `make build` was required.

These are engineering execution results, not installed alternate-session/terminal/
SSH admission or a real waiting-session census. Step 5b below adds the installed
account/routing proof; the census remains in 5c. No complete customer request
journey or Phase 3 exit gate was closed.

### Step 5b qualification — 2026-10-13

Added and passed `enforcement::test_kiosk_login_admission` on both targets.
The [installed admission helper](../tests/integration/system_kiosk_admission.py)
uses bounded libpam workers against the installed `gdm-password`, `login` and
`sshd` account stacks, rather than a private PAM configuration. Its maintained
scope belongs to the [installed runner](../tests/integration/README.md#running-the-current-installed-suite).

| Installed admission result | Ubuntu report / allocation | Fedora report / allocation |
| --- | --- | --- |
| Account/routing controls, denials and recovery | `20261013T225524Z-637ea3a2` / `onpc-system-d9b4nb5q` | `20261013T225720Z-5cba4746` / `onpc-system-gkfo7btz` |

Both retained `evidence/guest/enforcement.xml` files record successful ordinary
account controls for all three services and dedicated kiosk GDM admission before
denials. Selecting the installed alternate Wayland session (`ubuntu` or `gnome`)
or saving an invalid `x11` transport returned exactly `PAM_PERM_DENIED` (6),
repaired the dedicated/Wayland defaults and permitted a fresh successful retry.
Kiosk terminal and SSH account checks returned the same exact denial; ordinary
controls still passed afterward. Every transaction's `pam_end` returned zero.
Effective SSH configuration selected PAM and the tested `sshd` service.
The ordinary account's routing remained unchanged.

Live maintenance probes first established dedicated admission, ordinary terminal/
SSH controls and kiosk service denials on both targets. Both maintenance owners
finished cleanup before the installed attempts. The format-specific builder
returned `output/test-runs/host/allocations/onpc-test-artifacts-m3vjp4df` (DEB)
and `output/test-runs/host/allocations/onpc-test-artifacts-9vyjmxo4` (RPM).
Their package-source, package and fixture hashes exactly match the 5a candidate
above; both installed attempts validated those inputs and reused matching app
snapshots. The common selected-input SHA-256 was
`93f2ae1881a5ecc514500dded544357f03c00995ebaca3e64768a0f232098dcb`.
Both `evidence/result.json` files report passing product, infrastructure,
collection and cleanup outcomes with `cleanup_phase=complete`. Outer baseline
verification passed and both pinned VMs were confirmed off.

No product or final-exec fixture changed. The two 5a execution result files were
verified before this qualification; their older allocations subsequently expired
under normal retention. Treat those references as historical, and require retained
evidence or a fresh affected slice for later reuse. The new 5b result and JUnit
files were verified present after final validation. This account-stage proof
does not newly qualify session-stage transport changes, a real greeter login or
customer request journeys. It leaves no remaining 5b account/routing assertion
gap; the strict real-session census remains the next step.

Independent source review found no blocking defect. The scoped confinement,
runner and parallel-inventory regressions passed (532 cases), followed by all
313 documentation/inventory consistency checks. Generated coverage and Markdown
links passed. Changes are confined to tests, scheduling rationale and documents,
outside package sources/build-tool dependencies; no additional `make build` was
required. Phase 3 and the separate E2E queue remain open.

### Step 5c qualification — 2026-10-13

Passed `check_e2e_kiosk_entry` on both targets after the real public waiting form
appeared. The strict census verified every relevant process/thread's current
confined label, private mount namespace and matching manager generation.

| Waiting-session result | Ubuntu report / allocation | Fedora report / allocation |
| --- | --- | --- |
| Public station entry and strict engineering census | `20261013T230839Z-53fd7f36` / `onpc-graphical-smoke-l03ut8_z` | `20261013T230839Z-1ebca275` / `onpc-graphical-smoke-1o58jfgt` |

| Required confined thread role | Ubuntu AppArmor | Fedora SELinux |
| --- | ---: | ---: |
| Manager | 10 | 1 |
| App | 37 | 37 |
| Service | 80 | 81 |
| Wellbeing | 11 | 11 |
| PipeWire | 8 | 3 |

The census also observed the confined gate, audio, notification, notification-client
and Polkit roles. Fedora's surviving manager-PAM thread retained its confined
current domain; no `init_t` exception was used.

Independent review found a verifier gap: known SELinux label text plus global
enforcing mode did not exclude a permissive kiosk domain when no password helper
was running. The census now unconditionally reuses the installed preparation
helper's enforcement check before inspecting processes. Four host regression
variants require this gate on both backends, without a live password helper.
No product code, policy or admission/final-exec fixture changed; 5a/5b require
no affected requalification from this verifier correction.

Before clean qualification, both owned live waiting sessions passed the corrected
census. A bounded Fedora fault probe made only the Wellbeing domain permissive
while retaining global enforcing mode: the census rejected it with
`selinux-domain-not-enforcing`. The probe restored domain enforcement and passed
the census again. Both maintenance owners completed baseline restoration before
the clean attempts; these probes supply engineering diagnosis only.

Both verified input manifests retain the 5a package-source, package and fixture
hashes above. The qualification source SHA-256 was
`c9548916c49dfe4443c75acf4ef81390ba9f3cd7af537ffd7e35a0c40614ca53`.
Each attempt verified its format-specific inputs and matching online `onpc-v1.4`
snapshot, retaining saved and expected package identities separately. Ubuntu's
snapshot archive hash differs from the staged DEB, with identical verified
package-content, baseline and recipe identities; Fedora's package hashes match.
Each allocation's `result.json` owns those complete identities and census counts.

Both qualification results report overall, infrastructure, collection and cleanup
passes, with `lease_phase=complete`, stopped workers and verified shutdown.
The product ledger remains `not-run` for this engineering qualifier; no complete
customer request journey is claimed. Both outer baselines were restored and
verified, and both pinned VMs were confirmed powered off.

All 460 affected confinement/entry host checks passed after the correction;
the 117 unchanged lease/worker cleanup checks also passed. Independent diff
review found no blocking defect. Generated coverage includes the four new cases.
All 313 documentation/inventory consistency checks and Markdown links passed;
both final qualification results were verified retained after validation.
Changes are confined to tests and documents, outside package sources/build-tool
dependencies, so no additional `make build` is required. Step 5c supplies no
complete request-journey acceptance; the separate E2E queue is unchanged.

Report roots are `output/test-runs/host/reports/`; privileged allocations are
under `output/test-runs/privileged/allocations/`. System evidence includes
`evidence/guest/enforcement.xml`. Use maintained readers/exporters.

### Step 6a qualification — 2026-10-13

Complete restricted-station case 50 (`E2E-016/approved`) passed on both targets
through `tools/run-tests e2e --id '50' --vm 'onpc-Ubuntu26.04,onpc-Fedora44'`,
with its existing recipe and all assertions preserved.

| Approved request result | Ubuntu report / evidence allocation | Fedora report / evidence allocation |
| --- | --- | --- |
| Complete customer journey | `20261013T231844Z-b97d3070` / `onpc-e2e-evidence-o96g088z` | `20261013T231844Z-66b00d4f` / `onpc-e2e-evidence-qwus3zfk` |

Each journey configured zero allowance through Parent, entered the station
without a password, and independently verified that Overview, app-grid and
terminal shortcuts left only the owned request form and permitted controls.
It prepared the exact child/approver, custom 75-second duration and soft-app
choice, authenticated through the real guarded native prompt, observed explicit
approval success and automatically returned to usable sign-in with the station
absent. Product, infrastructure, collection and cleanup ledgers passed on both
targets, with no first failure and `lease_phase=complete`. Worker evidence confirms stopped
workers, closed callbacks and verified shutdown. Both outer baselines were
restored and verified; both pinned VMs were independently confirmed powered off.

The maintained builder returned
`output/test-runs/host/allocations/onpc-test-artifacts-9wwckgrw` (DEB) and
`output/test-runs/host/allocations/onpc-test-artifacts-h239fa5a` (RPM).
Their verified package-source, package and fixture hashes exactly match the 5a
candidate above. Both attempts matched the retained online `onpc-v1.4` snapshots.
The common scenario-source SHA-256 was
`9f90ccd0fad0af2456f9e8b99c04901a73c2275696696039a64083e188992c90`;
the acceptance records retain full input identities and reviewed step evidence.
Before acceptance, both maintenance probes succeeded, including Fedora's
enforcing SELinux check, and both maintenance owners completed restoration.
Those probes supply engineering observation only.

Independent source review found no missing case assertion or required code fix.
The building-block description now matches the unchanged shortcut readiness
checks, which preserve the form without focusing a control. Coverage regeneration
succeeded with no inventory change, all 313 documentation/inventory consistency
checks passed, and Markdown links passed. Both acceptance reports and evidence
allocations were verified retained after validation. Only documentation changed,
outside package sources/build-tool dependencies, so no additional `make build`
is required. Phase 3 remains open; step 6b is next. The separate E2E queue is
unchanged.

### Step 6b qualification — 2026-10-13

Complete restricted-station case 51 (`E2E-016/denied`) passed on both targets
through `tools/run-tests e2e --id '51' --vm 'onpc-Ubuntu26.04,onpc-Fedora44'`.

| Denied request result | Ubuntu report / acceptance allocation | Fedora report / acceptance allocation |
| --- | --- | --- |
| Complete customer journey | `20261013T233432Z-9b04eb86` / `onpc-e2e-evidence-12vq5q8b` | `20261013T233432Z-620138c6` / `onpc-e2e-evidence-om7vkuw4` |

Independent review found that case 51 omitted the recipe's initial shortcut
checks. Its declaration and worker now reuse the existing Overview, app-grid
and terminal checks before the request, preserving all three repeated checks
after rejection. Host regressions require both cycles, their ordering and refusal
at every stage. Case 52 remains unchanged; step 6c must address its equivalent
initial-check gap before acceptance.

Each journey configured zero allowance through Parent, entered the station
without a password, checked its restrictions, and prepared the exact child,
approver, custom 75-second duration and soft-app choice. The real guarded native
prompt explicitly rejected the wrong password. Normal prompt cancellation left
the selected request choices unchanged; repeated shortcuts retained only the
owned form and permitted controls. Form Cancel then returned to usable sign-in
with the station absent. This proves the case's confinement assertions, not a
separate frontend denial-message or backend no-grant history.

Both acceptance records report product, infrastructure, collection and cleanup
passes, no first failure and `lease_phase=complete`. Worker allocations
`onpc-e2e-evidence-hjhy26m2` (Ubuntu) and `onpc-e2e-evidence-81vjplu1` (Fedora)
confirm stopped workers, closed callbacks and verified shutdown. Both outer
baselines were restored and verified; both pinned VMs were independently
confirmed powered off. Earlier owned maintenance station-entry probes succeeded
on both targets, with Fedora SELinux enforcing, and completed restoration before
acceptance; those probes supply engineering observation only.

Verified builder inputs were
`output/test-runs/host/allocations/onpc-test-artifacts-fnt2pvca` (DEB) and
`output/test-runs/host/allocations/onpc-test-artifacts-t4ew57g_` (RPM).
Their package-source, package and fixture hashes match the 5a candidate above.
Both attempts used the retained online `onpc-v1.4` snapshots; the common
scenario-source SHA-256 was
`c5c5bee26054467b2af67e717e0ec0b154576f470b55985492c4a8237e57288a`.
The acceptance records retain full input identities and reviewed step evidence.

All 809 affected host checks and 313 final documentation/inventory consistency
checks passed. Coverage regeneration includes the six added refusal cases;
Markdown links passed. Both acceptance reports and allocations were verified
retained after final validation. Independent diff and resource review found
no blocking defect or new shared resource. Only tests and documentation changed,
outside package sources/build-tool dependencies, so no additional `make build`
is required and earlier product qualification remains applicable. Phase 3 stays
open; step 6c is next. The separate E2E queue is unchanged.

### Step 6c qualification — 2026-10-13

Complete restricted-station case 52 (`E2E-016/cancelled`) passed on both targets
through `tools/run-tests e2e --id '52' --vm 'onpc-Ubuntu26.04,onpc-Fedora44'`.

| Cancelled request result | Ubuntu report / acceptance allocation | Fedora report / acceptance allocation |
| --- | --- | --- |
| Complete customer journey | `20261014T014819Z-90a23271` / `onpc-e2e-evidence-f54les64` | `20261014T014819Z-ecc3e92b` / `onpc-e2e-evidence-f529dyxd` |

Case 52 now reuses the initial Overview, app-grid and terminal restriction cycle
required by its recipe, matching cases 50 and 51. Its declaration and worker
agree on the ordering and recorder phase boundary. Host coverage requires both
shortcut cycles and refuses at every stage, including the six added initial
cancellation stages. Independent review found no further missing case assertion.

Each journey configured zero allowance through Parent, entered the station
without a password and passed the initial restriction cycle. It prepared the
exact child, approver, custom 75-second duration and soft-app choice, then
cancelled the real native authentication prompt without an approval password.
Independent readback proved unchanged usable no-error request choices. Repeated
Overview, app-grid and terminal checks retained only the owned form and permitted
controls; form Cancel returned to usable sign-in with the station absent.
This establishes the case's confinement assertions, not a backend no-grant history.

Both acceptance records report product, infrastructure, collection and cleanup
passes, no first failure and `lease_phase=complete`. Worker allocations
`onpc-e2e-evidence-wuxod3nv` (Ubuntu) and `onpc-e2e-evidence-4zrzsqv7` (Fedora)
confirm stopped workers, closed callbacks and verified shutdown. Both outer
baselines were restored and verified; both pinned VMs were independently
confirmed powered off. Before acceptance, maintained station-entry reproductions
and guest process-label probes succeeded on both live maintenance VMs, with
Fedora SELinux enforcing. Both maintenance owners completed restoration before
acceptance; those probes supply engineering observation only.

Verified builder inputs were
`output/test-runs/host/allocations/onpc-test-artifacts-s3wlqdf9` (DEB) and
`output/test-runs/host/allocations/onpc-test-artifacts-7cxonl9u` (RPM).
Their package-source, package and fixture hashes match the 5a candidate above.
Both attempts used the retained online `onpc-v1.4` snapshots; the common
scenario-source SHA-256 was
`5bf22f5e2001315e1d232083bbb7b981c3f2f4687688eeb290b6ac894d2037de`.
The acceptance records retain full input identities and reviewed step evidence.

All 1,460 affected host checks and 313 final documentation/inventory consistency
checks passed. Coverage regeneration includes the six added refusal cases;
Markdown links passed. Both acceptance reports and allocations were verified
retained after final validation. Independent diff and resource review found no
blocking defect or new shared resource. Only tests and documentation changed, outside
package sources/build-tool dependencies, so no additional `make build` is
required and earlier product qualification remains applicable. Phase 3 stays
open; step 7 is next. The separate E2E queue is unchanged.

### Step 7a qualification — 2026-10-13

Complete kiosk About case 192 (`E2E-042/kiosk`) passed on both targets through
`tools/run-tests e2e --id '192' --vm 'onpc-Ubuntu26.04,onpc-Fedora44'`.

| About result | Ubuntu report / acceptance allocation | Fedora report / acceptance allocation |
| --- | --- | --- |
| Complete customer journey | `20261014T025116Z-b14fa9c6` / `onpc-e2e-evidence-5j2vg7o4` | `20261014T025116Z-2e04a946` / `onpc-e2e-evidence-ezrddoln` |

Independent coverage review found the existing complete case sufficient for
7a. Its owned, complete About snapshot rejects visible link, button, menu and
input roles outside the identified window controls, requires plain in-app website, privacy,
support, license and legal information, and rejects an offered external Help
action. The kiosk source passes `links_enabled=False`; no handler, chooser,
management or program-launch action is available from About. Normal close
returned to the independently unchanged child/approver, custom 75-second request
and soft-app choice. Form Cancel returned to usable sign-in with the station
absent. No case assertion or product code changed.

Both acceptance records report product, infrastructure, collection and cleanup
passes, no first failure and `lease_phase=complete`. Worker evidence allocations
`onpc-e2e-evidence-2s6kda4x` (Ubuntu) and `onpc-e2e-evidence-pi5hrj_s` (Fedora)
confirm stopped workers, closed callbacks and verified shutdown. Both outer
baselines were restored and verified, and both pinned VMs were confirmed off.
Before acceptance, both owned live maintenance VMs passed the installed
confinement integration's `verify` action; Fedora reported enforcing SELinux.
Both maintenance owners completed restoration before the customer attempts.

Verified execution inputs were
`output/test-runs/host/allocations/onpc-test-artifacts-s7_y885p` (DEB) and
`output/test-runs/host/allocations/onpc-test-artifacts-xoygp8ds` (RPM).
Their package-source, package and fixture hashes match the 5a candidate above.
Both attempts used matching retained online `onpc-v1.4` snapshots; the common
scenario-source SHA-256 was
`1d53d33bcf53c3533c40fe6c7c3931c4db5bdb1914eae55b2c4c5b45022bd743`.
The acceptance records retain complete input identities and reviewed step
evidence. The historical September About result predates the current UI API
and confinement implementation and was not reused.

All 659 selected host safety/composition checks and 313 documentation/inventory
consistency checks passed. Coverage regeneration after each target's successful
case produced no inventory change; Markdown links passed. Both acceptance
reports and allocations were verified retained after final validation. Only this
plan changed, outside package sources/build-tool dependencies, so no additional
`make build` is required. Phase 3 remains open; step 7b is next. Preferences and
error-report/privacy/native-service qualification remain in 7b and 7c; the
separate E2E queue is unchanged.

### Step 7b qualification — 2026-10-13

The Preferences source/control audit found no product defect. Language,
Reminders and Preset Times, including Add/Edit reminder and preset dialogs,
use fixed in-app controls and broker settings calls. No external handler,
chooser, management or arbitrary-program launch API is exposed. Reminder
Preview uses the fixed notification route; this slice does not activate or
qualify reminder delivery.

The maintained `check_e2e_kiosk_preferences_confinement` qualifier composes
shared station/request operations with a complete identified-control inventory
for each page and editor. It binds the selected child, modal ownership and
Preferences lifetime, rejects extra controls/links/surfaces, cancels drafts and
checks unchanged reminder/preset lists. Static labels must remain read-only.
The source audit complements the public API, whose inventory excludes anonymous
toolkit widgets. The final independent request comparison and strict real-session
process/thread census supplement those surface checks.

An initial Ubuntu attempt (`20261014T032826Z-0e82c29c`) timed out in the combined
Preferences operation; Fedora's initial attempt passed. Owned Ubuntu maintenance
reproduction passed in 84 seconds. A live public-API probe showed costly repeated
element reads; retaining full page/editor inspections while avoiding repeated
full inspections at unchanged input boundaries reduced reproduction to 51
seconds (`onpc-kiosk-preferences-diagnosis-q9s2a6i0`). Fresh owner, child, modal,
lifetime and page guards remain at every boundary. The transport timeout and
confinement assertions were unchanged. Both subsequent concurrent attempts
(`20261014T040454Z-869374f3`, `20261014T040454Z-0e06ee46`) still hit
`TimeoutExpired`; both completed worker cleanup and baseline restoration with
`lease_phase=complete`. Contention is a supported diagnosis hypothesis, not a
proven product defect. Maintenance reproduction supplies no acceptance credit.

The unchanged qualifier then passed through separate maintained target selections.
The contracts permit per-target qualification of the complete required target
set; these results do not qualify concurrent execution. Use the two explicit
Preferences commands below.

| Target | Passed report | Main result / qualification allocation |
| --- | --- | --- |
| Ubuntu | `20261014T041604Z-5a5c7615` | `onpc-graphical-smoke-fm1sl2pt` / `onpc-e2e-evidence-grzokrnq` |
| Fedora | `20261014T042812Z-36ac5f34` | `onpc-graphical-smoke-0g47omf8` / `onpc-e2e-evidence-q9yieq22` |

Both installed results passed all three pages and four editor routes, then the
strict census of every kiosk process/thread with enforcing AppArmor or SELinux,
private namespaces, matching generation and required manager/app/service,
Wellbeing and PipeWire roles. Independent return observations preserved the
child/approver, custom 75-second duration, soft-app choice and 1875-second
estimate. Normal form Cancel returned to usable sign-in with the station absent.

Both engineering records report overall, infrastructure, collection and cleanup
passes with `lease_phase=complete`; the product domain remains `not-run`.
Worker allocations `onpc-e2e-evidence-kq0qvax2` (Ubuntu) and
`onpc-e2e-evidence-vi7faduu` (Fedora) confirm no first failure, stopped workers,
closed callbacks and verified shutdown. Both outer baselines were restored and
verified, and both pinned VMs were confirmed off. Owned maintenance instances
also finished restoration before qualification. Their installed confinement
integration `verify` actions passed on both targets before the first attempts.

Verified package/fixture inputs were the named
`output/test-runs/host/allocations/onpc-parent-setup-onpc-Ubuntu26.04-b0c09311fe1b52b87bebd7699caab30829edc3c789329e50ae550c38eeb7b6c5`
and corresponding `onpc-parent-setup-onpc-Fedora44-b0c09311fe1b52b87bebd7699caab30829edc3c789329e50ae550c38eeb7b6c5`
allocations. Their package and fixture hashes match the 5a candidate; both
attempts used matching online `onpc-v1.4` snapshots. All 590 recorded execution
input digests match between the final attempts, including shared UI operation
SHA-256 `4ee1cc05a52d258232eeb1b52dcee08562012c9dd0293db25e9e189eccad877b`.
The records retain each attempt's complete repository provenance and input
identities. No product source changed, so earlier candidate policy qualification
remains applicable.

Affected shared API/support, composition and dispatcher/cleanup host suites
passed. The final Preferences guard selection passed 35/35
(`20261014T035751Z-f5de8705`); final plan/inventory/coverage/composition consistency
passed 313/313 (`20261014T043421Z-10065921`). Coverage regeneration added 92
unit cases and one engineering qualifier, with no customer-case inventory change.
Independent review confirmed existing private resource classifications remain
applicable. Markdown links passed. These test/tool/documentation changes are
outside package sources and build-tool dependencies, so no `make build` is
required. Both final reports and result allocations were verified retained
after validation.

This closes only Preferences confinement. Persistence, saving, reminder delivery,
and complete preference/reminder customer histories remain outside this slice.
Phase 3 remains open; error-report/privacy/native-service qualification in 7c is
next. The separate E2E queue is unchanged.

### Step 7c qualification — 2026-10-13

The report/privacy source audit found no product defect. Kiosk attachment and
download actions are hidden and independently guarded; the in-app Privacy
action consumes its link signal and hides the external privacy-notice link.
The bundled editor blocks external navigation and new-window requests, with
local formatting operations and a read-only link-preview API. Diagnostic
collection uses the broker; RPM package queries use a fixed launcher.

The existing `check_e2e_kiosk_feedback_confinement` qualifier now audits the
identified report/privacy control inventories, rejects unexpected actions,
links, surfaces and modals, reads the shared in-app disclosure, and independently
compares the edited public document after returning. Source audit supplies
completeness for anonymous toolkit controls. Report identity checks cover
logical surface ownership. The strict
census now requires notification and notification-client roles alongside
manager, app, service, Wellbeing, PipeWire and WebKit.

Historical scanner/editor reports used different package-source inputs; the
Ubuntu historical allocation was also unavailable. They were not reused for
this slice. Fresh complete engineering qualification passed through separate
maintained target selections:

| Target | Passed report | Main result / worker allocation |
| --- | --- | --- |
| Ubuntu | `20261014T045241Z-59fdb539` | `onpc-graphical-smoke-vxqo8kl0` / `onpc-e2e-evidence-ws3g9ezo` |
| Fedora | `20261014T045835Z-01c47c77` | `onpc-graphical-smoke-mie3ozdu` / `onpc-e2e-evidence-4ut_flda` |

Both results prove usable editable reporting, prepared diagnostics, confined
Privacy actions/disclosure and exact unsent draft preservation. Each retained
the actual transient scanner's pinned executable, enforcing scanner/parent
threads and matching private namespace/generation. Each strict census verified
every relevant live process/thread and all eight required roles under AppArmor
or enforcing SELinux. The separate positive observation retains scanner proof
after the transient process exits.

Both results report overall, infrastructure, collection and cleanup passes,
with `lease_phase=complete`, broker restoration, stopped workers, closed callbacks
and verified shutdown. The product ledger remains `not-run`; this engineering
history grants no complete customer-case credit. Both outer baselines were
restored and verified, and both pinned VMs were confirmed off. Earlier owned
waiting-session probes and installed confinement-integration `verify` actions
passed on both targets; their maintenance owners also finished restoration.

The verified named DEB/RPM inputs and fixture hashes match the 5a candidate.
Both attempts used matching online `onpc-v1.4` snapshots and retain saved and
expected package identities separately. All 590 recorded execution input
digests match between targets, including shared UI operation SHA-256
`ecfaa2b63d463ba07e7fc707b722879d692d8549fc49803ecd22f8701935eaf1`.
Both qualification source hashes are
`367b25b81dc0e77caaafc831d21a644f75fb86b09a64147aca2c232269835176`.
No product source changed, so earlier candidate policy qualification remains
applicable without affected requalification.

The final feedback guard module passed 54/54 (`20261014T045139Z-e85c564b`);
1,806 other scoped shared API/privacy/composition and worker-cleanup checks
passed. Bounded independent
review found no further defect, and existing resource classifications remain
applicable. Coverage regeneration added 12 unit cases with no customer-case
inventory change. Final plan/inventory/coverage/composition consistency passed
313/313 (`20261014T050633Z-0902c6d2`), and all 353 Markdown link checks passed.
Both final qualification reports and result allocations were verified retained
after validation. These test/documentation changes are outside package
sources and build-tool dependencies, so no `make build` is required.

This closes only error-report/privacy/native-service confinement. Sending,
ordinary Parent diagnostic export and general editor/notification/Wellbeing
feature histories remain with their existing owners. Phase 3 remains open;
step 8's shared-integration collateral checks are next. The separate E2E queue
is unchanged.

### Step 8a qualification — 2026-10-13

The coverage audit split step 8's independent ordinary-desktop and shared
integration histories into 8a–8b, preserving all original assertions. Source
review found the existing `check_e2e_fresh_desktop` sufficient for 8a; no product,
test, inventory or generated-coverage source changed.

The maintained two-target selection passed separate restored administrator and
standard-user attempts on each target. Each selected the intended GDM account,
performed two fresh secret-recipient checks before password input, and
independently observed that account's normal Shell desktop with a unique
visible enabled Activities control and complete prompt-free snapshots stable
for two seconds.

| Target / ordinary role | Passed report | Main result / worker allocation |
| --- | --- | --- |
| Ubuntu / administrator | `20261014T051633Z-8d7df320` | `onpc-graphical-smoke-zecz043f` / `onpc-e2e-evidence-hfl1tr0e` |
| Ubuntu / standard user | `20261014T051633Z-8d7df320` | `onpc-graphical-smoke-ec404eoy` / `onpc-e2e-evidence-0qz4sii9` |
| Fedora / administrator | `20261014T051633Z-23090eca` | `onpc-graphical-smoke-ua9sbw_6` / `onpc-e2e-evidence-ry7c702u` |
| Fedora / standard user | `20261014T051633Z-23090eca` | `onpc-graphical-smoke-6ay2z_xc` / `onpc-e2e-evidence-yeyb3c4n` |

Main and worker allocations live under
`output/test-runs/privileged/allocations/`. All four results report overall,
infrastructure, collection and cleanup passes, `lease_phase=complete`, stopped
workers, closed callbacks and verified shutdown. Each restored and verified
its outer baseline; both pinned VMs were independently confirmed off. The
queue result `onpc-vm-queue-o7sxc95f/results.json` reports zero status and no
handoff for either target. Live installed-confinement `verify` probes passed
on both owned online maintenance guests before qualification; those owners
also finished restoration.

The verified named DEB/RPM inputs retain the 5a package-source, package and
fixture identities. All four attempts matched their online `onpc-v1.4`
snapshots, retaining saved and expected package identities separately.
All 590 execution-input digests match across the four attempts; shared
`fresh_desktop.py` SHA-256 is
`aa1689184493e50a5190c743d3f745d2411b62a1cf7bfa736d6fce3a623e4805`.
The results retain complete baseline, source and package provenance.

Final plan/inventory/coverage/composition consistency passed 313/313
(`20261014T052152Z-364b2cc2`). Markdown links and whitespace checks passed;
the four acceptance result allocations remain retained. Only this plan changed,
outside package sources and build-tool dependencies, so no `make build` is
required. The product ledger remains `not-run`: this engineering qualification
proves ordinary login/desktop availability without completing a customer case
or broader Parent/child/overlay feature acceptance.

At 8a close-out, shared integration still required applicable vendor PAM
preservation, metadata for both ordinary roles and effective kiosk-only
unit/policy scope. The source audit identified ordinary manager
labels/namespaces/unit paths, private masks/drop-ins and shared launcher
environments as installed scope checks; the metadata qualifier then
fingerprinted only the ordinary administrator's cache/icon. The 8b–8c split
below retains those assertions. No shared-integration assertion or Phase 3 exit
gate closed with this desktop result. The separate E2E queue remained unchanged.

### Step 8b qualification — 2026-10-13

The complete registered
`package::test_kiosk_account_classification_survives_reboot` history passed
both installed and rebooted phases on each target, preserving its existing assertions.

| Target | Passed report | Retained system allocation |
| --- | --- | --- |
| Ubuntu | `20261014T053421Z-46b46446` | `onpc-system-s9d7_ae2` |
| Fedora | `20261014T053957Z-fec23e97` | `onpc-system-u1tqx2dd` |

Allocations live under `output/test-runs/privileged/allocations/`.
Both installed JUnit files record fresh-cache retry/restart, retained-visible
and hidden preservation, unsafe refusal/recovery, all three atomic interruption
recoveries and explicit administrator/standard-user metadata preservation.
Both rebooted files record retained kiosk and ordinary-role preservation after
the controller's real reboot. All four executions have zero errors, failures or
skips. Each result reports passing product, infrastructure, collection and
cleanup outcomes, `cleanup_phase=complete` and verified outer-baseline
restoration with metadata-only checks. Both pinned VMs were independently
confirmed off. The acceptance results remain retained.

The coverage audit split the original shared-integration step into the
independent metadata history (8b) and shared PAM/effective-policy scope (8c).
The maintained classification selector now captures both declared ordinary
administrator and standard-user AccountsService cache/icon fingerprints before
kiosk mutations, then compares them throughout its existing provisioning,
restart, interruption recovery and reboot history. Baseline UID/role and icon
route checks remain mandatory; diagnostics expose only fixed role labels and
bounded metadata differences. No ordinary account receives a fixture write.
The complete kiosk metadata and recovery assertions remain unchanged.

Both owned online maintenance guests passed `exercise-live`, then
`verify-reboot` after a real reboot, including explicit administrator and
standard-user preservation properties. These diagnostics omit only the
atomic subprocess injections and supply no installed-selector acceptance.
Both maintenance owners completed guarded stop and outer-baseline restoration
before the installed runs.

The helper SHA-256 is
`e580826c444c4b1a08ba54c229a91c8bc7aef745b74d573249aa47134ca17538`.
The verified named inputs are
`output/test-runs/host/allocations/onpc-parent-setup-onpc-Ubuntu26.04-b0c09311fe1b52b87bebd7699caab30829edc3c789329e50ae550c38eeb7b6c5`
and
`output/test-runs/host/allocations/onpc-parent-setup-onpc-Fedora44-b0c09311fe1b52b87bebd7699caab30829edc3c789329e50ae550c38eeb7b6c5`.
Their package-source, package and fixture hashes exactly match the 5a candidate.
Both installed attempts retain the same selected-input SHA-256
`65ff04d9801e0bc972d3fbdb64c111c530a861a72bf6933c85dde9c5d16f4a00`,
including the helper digest above. Both artifact verification checks passed.
No product, policy or build input changed, so earlier product qualification
needs no repetition for this test-only
extension and `make build` is not required.

Scoped metadata, runner and host-inventory regressions passed 251/251
(`20261014T053025Z-09ca27b4`); plan/inventory/coverage/composition consistency
passed 313/313 (`20261014T054400Z-70462751`). The expanded unit cases use the same
private files and command/account doubles, retaining the reviewed compatible
resource classification. Independent bounded source review found no blocking
issue. Generated coverage was refreshed without changing E2E bindings or readiness.

Step 8b closes only the metadata slice. Phase 3 remains open; step 8c must
qualify preserved vendor PAM callbacks and effective kiosk-only unit/policy
scope for both ordinary roles before its exit gate can close. No customer
case or broader Parent/child/overlay feature acceptance is claimed, and the
separate E2E queue remains unchanged.

### Step 8c qualification — 2026-10-13

The new registered `enforcement::test_kiosk_shared_integration_scope` passed on
both targets. Its maintained contract belongs to the
[installed runner](../tests/integration/README.md#running-the-current-installed-suite).
It verifies original vendor PAM callback bytes/options and the explicit ordinary
manager credential fallback, then reuses the complete namespace qualifier and
checks both prepared ordinary account roles through real user-manager lifetimes.

The namespace fixture now retains its original root and kiosk workers and adds
the prepared administrator and standard user. All three ordinary controls run
the real namespace open/init/close callbacks; the kiosk still skips their
activity. Credential setup/deletion, parent isolation and inode/content-checked
configuration cleanup remain mandatory. The shared-integration selector includes
these complete assertions so its final retained result owns every PAM collateral
check without requiring a second acceptance report.

Both ordinary managers retain their measured ordinary security labels, global
generation and executable inodes, vendor unit hardening and normal unit paths.
Private compositor, audio, Wellbeing and bus overrides do not leak to either
role; all six Ubuntu Snap masks leave ordinary vendor units loaded. Shared audio
and Wellbeing launchers preserve ordinary startup/settings environments, and
the bus retains vendor execution and data paths. Shell, Python and GJS transient
services succeed. Fedora's vendor bus uses the explicitly measured
`unconfined_dbusd_t` domain; its ordinary managers, audio and Wellbeing use
`unconfined_t`. Cleanup stops only each newly recorded manager invocation.

| Retained installed result | Ubuntu report / allocation | Fedora report / allocation |
| --- | --- | --- |
| Shared integration, including complete namespace callbacks | `20261014T061547Z-ad573776` / `onpc-system-4_fwcj_m` | `20261014T061633Z-12ac818b` / `onpc-system-eqxjjzxe` |
| Complete execution matrix and actual PAM teardown | `20261014T060738Z-07152ff1` / `onpc-system-pqk2_3rx` | `20261014T060903Z-8fc79945` / `onpc-system-yp5giezn` |
| Complete platform/native-service API matrix | `20261014T061225Z-a5e65c7a` / `onpc-system-0hq7oqw6` | `20261014T061327Z-d1ded39a` / `onpc-system-pgap5djp` |

Allocations live under `output/test-runs/privileged/allocations/`. All six
results report product, infrastructure, collection and cleanup passes,
`cleanup_phase=complete`, and successful acquisition/restoration baseline checks.
All six JUnit files have one passed test with zero errors, failures or skips.
Both pinned VMs were independently confirmed powered off. These are the final
three retained engineering attempts per target, preserving the required evidence
within the maintained retention window.

The complete matrices refresh expired 5a raw reports without changing their
assertions. They again prove native positives before kernel-enforced execution,
mapping and service-API denials, real credential/teardown confinement, private
generation isolation and policy-loss refusal/recovery. Earlier recorded passes
remain historical; missing raw reports were not represented as verified reuse.
All four ordinary graphical-login records from 8a were independently checked for
matching package, baseline and snapshot applicability before this qualification.
Keyring callback/options preservation is proven; no separately observed keyring
autostart or new complete customer journey is claimed.

Expired named package inputs caused pre-acquisition `assets:source-missing`
refusals. The maintained builder recreated the required DEB/RPM inputs, with
source, package and fixture hashes exactly matching the 5a candidate. Every final
allocation retains its verified frozen inputs. Both final shared-integration
attempts have selected-input SHA-256
`2d2a5bb7872d8c9df72e416cce9229aed302a6ac89288cb21af1bf5bc1a51e61`;
the refreshed execution and platform pairs respectively retain
`9f1d4ec275d9d99f5519b907739df22200c5a98662aa9ec49660b164ddd64a22` and
`03bbd25ae90508998b1e9198bb89ac7850980e3417a84c329c1b957b856b1a4a`.
The final collateral helper SHA-256 is
`69628c900304dafefe857c4240b63b6f5d65a14e22b4b8ba5002d6b24fe3cb63`.

Both owned online guests passed the ordinary-scope and extended namespace live
diagnostics before clean installed qualification; their guarded stops restored
the outer baselines. Source review found no product defect. The new host
regressions use private files and process-local doubles, retaining reviewed
compatible scheduling without a cleanup/UI resource owner. Confinement/inventory
checks passed 404/404; the final collateral, runner and import-closure checks
passed 222/222 (`20261014T061508Z-cfa49ca5`). Generated coverage was refreshed.
Final plan/inventory/coverage/composition consistency passed 313/313
(`20261014T061929Z-6ece1d93`), and Markdown links and whitespace checks passed.
All six final reports and result allocations were verified retained afterward.
No product, policy or build dependency changed, so no additional `make build`
was required.

Step 8c closes the remaining ordinary-user collateral slice. The unchanged
candidate's completed admission, waiting-session census, essential request,
surface/service and ordinary-login/metadata histories remain applicable;
the Phase 3 exit gate passes. Phase 4 step 1 is next and requires a separate
session. The separate E2E queue and its next-task pointer remain unchanged.

### Phase 4 step 1 — coverage and verified inputs — 2026-10-13

This audit maps the remaining lifecycle obligations to executable assertions;
it supplies no installed activation, removal or recovery pass. Registry listings
confirmed the four `package` selectors and the single `removal` selector on the
registered targets. The
[installed runner](../tests/integration/README.md#running-the-current-installed-suite)
owns their execution and prerequisite closure.

| Obligation / owning step | Registered coverage and assertion | Remaining installed coverage |
| --- | --- | --- |
| Latest-version activation and reboot (2) | `package::test_installed_package` runs before and after reboot: exact payload identity/permissions, active dependencies, PAM integration and a nonempty fapolicyd rule listing. Before reboot, `system_guest.verify_reboot_gate` requires the exact broker `Error.RebootRequired` and unchanged generated execution-policy files. `test_first_install_requests_reboot` and `test_reboot_applies_installation` check the product request, new boot identity and cleared request. | These assertions do not observe the actual kiosk admission/execution boundary in that same activation history or prove the exact loaded/enforcing confinement policy and generation. Pending reboot must leave policy operations unavailable and kiosk entry either safely refused or confined with the restart-required presentation; the reboot marker alone does not require blanket PAM denial. Add direct boundary observations, missing/stale/unenforced-policy refusal and post-boot readiness checks before closing 2. |
| Account identity/classification and restart (2) | `package::test_kiosk_account_classification_survives_reboot` invokes `system_kiosk_accounts.exercise` and `verify_reboot`: preserved UID/GID/nologin shell, visible/saved classification, dedicated Wayland routing, retained kiosk metadata, both ordinary roles' metadata, AccountsService restart and new-boot witnesses. It also exercises owned metadata-publication interruption/retry. | It does not call kiosk admission gates or observe confined execution after those restarts. Metadata recovery is covered; it is not removal rollback or a confinement readiness assertion. |
| Execution/admission readiness (2, 10–11) | `enforcement::test_kiosk_execution_confinement` supplies enforcing execution, real credential/teardown, stale manager/generation and policy-loss refusal/recovery; `test_kiosk_login_admission` supplies installed GDM/terminal/SSH account gates with allowed controls. `integration check_e2e_kiosk_entry` owns the strict real waiting-session census. Namespace, shared-integration and platform selectors retain their Phase 3 scopes. | These post-install routes restore a verified app snapshot. Their existing passes do not observe the freshly exercised installation/reboot transition. Reuse their maintained mechanics and exact applicable evidence without substituting a cached snapshot for step 2's transition. |
| Complete successful removal/reinstall/purge history (3–4) | `removal::test_remove_reboot_reinstall` is one continuous five-phase selector. `system_removal.verify_active_kiosk_refusal` proves allowed native execution, active-manager refusal, intact payload/PAM/records and a still-confined manager. `remove` separately preserves edited GDM hook and `gdm-password` bytes on refusal. Subsequent phases check payload/account/home/marker removal, unloaded kiosk policy, cleared restrictions/grants, ordinary account preservation, native execution, GDM desktop/password health, retained-state reinstall and fresh defaults after packaged purge. Fedora also checks original authselect selection and enforcing SELinux. | Current final PAM assertions require absent product references/barriers, not exact original `gdm-password`/`systemd-user` bytes and original local-versus-vendor disposition. Add that missing restoration assertion to the complete route before claiming the corresponding step 3/4 obligation. The successful endpoint does not prove the payload-erased, surviving-account interval. |
| In-flight admission, partial cleanup, abort and retry (5–6) | Active-manager refusal above and the execution matrix's non-destructive `check-remove` preflights are installed coverage. Host regressions exercise the root PAM admission lease, `postinst abort-remove`, uninstall snapshot rollback, confinement rearming, interrupted denial publication and failed policy unloading. | No registered installed history holds a root PAM admission/handoff before kiosk credentials appear, aborts after nontrivial cleanup, or interrupts denial publication/MAC unloading/finalization. Add bounded histories with allowed controls, refusal/interruption, preserved records and ordinary-user access, restored enforcement before guard release, and successful owned retry. Host fault fixtures are not installed proof. |
| Durable denial across payload erasure (5–6) | Production removal publishes distro-PAM account/session denials before unloading policy; embedded finalization restores original PAM only after owned account deletion. The existing installed selector observes completed cleanup only. | No registered installed history checks actual kiosk account/session denials while executable payload is absent and the kiosk identity survives, including interrupted finalization. Require those observations plus ordinary-user controls and exact restoration after verified account deletion. Private embedded-finalizer host fixtures do not close this gap. |
| Foreign/substituted ownership state (5–6) | The complete removal selector covers regular-file content edits at the GDM hook and `gdm-password`, followed by resolution and successful retry. Host ownership/cleanup fixtures cover additional refusal branches. | Installed coverage is missing for `systemd-user` edits, link substitutions, foreign confinement records, changed kiosk identity and substituted/foreign-owned or mounted home/state roots. Select finite variants under the removal ownership contract, preserve foreign state/recovery records on refusal and prove owned finalization after resolution. Apply the plan's bounded-step rule before executing independent histories. |
| Failed RPM post-erase recovery (6) | The successful Fedora removal history invokes the installed packaged purge action through native DNF and verifies its postconditions. Host purge fixtures exercise failed callbacks with mocked native transactions. | No registered installed history fails real post-erase cleanup, retains safe admission and recovery records after payload erasure, then uses normal reinstall, conflict resolution, reboot and repeated packaged purge. That complete recovery history remains required. |

Source assertions were traced through
[package tests](../tests/system/test_install_smoke.py),
[guest activation checks](../tests/integration/system_guest.py),
[account restart checks](../tests/integration/system_kiosk_accounts.py),
[admission checks](../tests/integration/system_kiosk_admission.py),
[execution checks](../tests/integration/system_kiosk_confinement.py),
[removal phases](../tests/integration/system_removal.py) and
[controller registration/order](../tests/integration/system_runner.py).
The [removal design](SystemDesign/Package-Removal.md) owns recovery expectations.
Steps 7–8 remain independent source/security reviews, not automated selectors;
steps 9–11 own final candidate validation and any invalidated confinement
histories. This audit closes neither review nor any installed coverage gap.

Both inputs were prepared through separate
`tools/run-tests artifacts prepare --for-vm --vm NAME` invocations. The pinned
baseline provenance selected DEB for `onpc-Ubuntu26.04` and RPM for
`onpc-Fedora44`. Ubuntu reused a verified matching bundle; Fedora built fresh
through the maintained RPM builder. Both preparation reports passed, and the
builder verified package and fixture digests. Independent `sha256sum` checks
matched the manifests.

| Input | Returned allocation under `output/test-runs/host/allocations/` | Preparation report under `output/test-runs/host/reports/` | Package |
| --- | --- | --- | --- |
| Ubuntu DEB | `onpc-test-artifacts-jes1rj38` | `20261014T063223Z-a52ca0a3/report.md` | `package/oh-no-parent-control_1.4+local1~ubuntu26.04.1_amd64.deb` |
| Fedora RPM | `onpc-test-artifacts-7hcj5neh` | `20261014T063230Z-b1f6a6cc/report.md` | `package/oh-no-parent-control-1.4-0.1.dev.fc44.x86_64.rpm` |

The starting checkout was clean at
`958f03c73abcb06e82e9b179b6f3807ab0978051`. Both manifests bind 348
`scope=package` inputs to revision
`f84b688281f27ade9e737b2b6a2930646db3541c` and package-source SHA-256
`b0c09311fe1b52b87bebd7699caab30829edc3c789329e50ae550c38eeb7b6c5`.
The package revision records the last commit touching the selected package/build
inputs; later test/documentation commits do not change that identity. DEB SHA-256 is
`daa9c180960e1dfc72e026a7019bb71b2b63db3bd4c867a62e300f05f81b94fa`;
RPM SHA-256 is
`630ab36562dd7f85d1a2b4f0cbf2f359972b6ac29fe4dcb2e5a051f5723afaf4`.
Both fixture digests are
`b605097e70b69abb86e32142a36ab762185d80f8df2e160dbdded5329d5d82ab`.
These match the Phase 3 candidate; preparation does not independently requalify
any earlier result or establish snapshot applicability for a future attempt.

The DEB manifest records `amd64`, source epoch `1791921826` and
`dpkg-buildpackage --build=binary --no-sign -aamd64`. RPM records `x86_64`,
source epoch `1791914313` and `tools/build_rpm.py`. Recorded build options are
`nocheck parallel=2`; package preparation supplies no regression-test pass.
Both manifests retain dpkg tool version `1.23.7` and Flatpak `1.16.6`.

Retention follows the existing
[three-run/4-GiB journal limits](../tests/README.md#aggregate-output-retention).
The two preparations and grouped final host verification fit the host window.
Verify both reports, manifests and package bytes after final validation; do not
treat these returned allocations as permanent inputs. Reprepare an expired
bundle through the maintained builder and check exact applicability before use.
Installed attempts share a separate three-run window per target: plan required
lifecycle reports, JUnit, input identities and cleanup evidence before steps
2–6, preserve needed report files through the documented artifact exporter
before rotation, and recheck exports after later exports. Missing required raw
evidence needs the affected complete history repeated; a prose reference alone
does not supply retained acceptance. Step 9 must reconcile any changed candidate.

No guest was started or mutated. Both registered targets were independently
confirmed powered off through `tools/test-vm status`. No product, policy, test
inventory or build input changed; this plan edit requires no additional
`make build`, coverage generation or customer E2E execution. The separate E2E
queue remains unchanged.

Final grouped validation passed both artifact verifications and 313/313
plan/inventory/coverage/composition consistency tests (315/315 checks total),
report `20261014T063732Z-9503cc0f`. Markdown links and whitespace checks passed.
Both preparation reports, manifests and exact package hashes were rechecked
afterward and remain retained alongside the final host report. No owned VM
cleanup was needed. Step 1 is complete; Phase 4 remains open and step 2 is next.

### Phase 4 step 2a1 — Ubuntu native activation — 2026-10-14

The maintained `package::test_kiosk_account_classification_survives_reboot`
selector now composes exact package readiness, the pending/cleared reboot
request, installed admission gates and the complete native confinement matrix
with its existing AccountsService restart, metadata and new-boot witnesses.
The runner keeps both phases in one fresh-install/reboot attempt. Routing
mutations precede the retained metadata witness; the gates after restart and
reboot do not change that routing. The preboot broker must still return the
exact `RebootRequired` error without changing generated execution rules.
Native positives, credential/teardown checks, actual execution denials and
missing/stale/unenforced-policy refusal/recovery retain their existing
assertions. This extends an existing selector; it creates no customer E2E pass.

Two cold attempts failed at `kiosk-lifecycle:waiting-generation`, before reboot,
in reports `20261014T153542Z-f7fef220` and `20261014T155140Z-b48fa55c`.
The latter's bounded, failure-only manifest diagnostic found unchanged
executable records and preserved inputs but changed layout: BIND libraries
advanced from Ubuntu `9.20.24-1ubuntu0.3` to `.4`, and
`/usr/lib/linux-tools-7.0.0-31` disappeared during an automatic APT transaction.
The required generation assertion correctly caught that drift and remains
unchanged. The temporary preparation service's ordering did not prevent APT
jobs in subsequent restored boots.

The shared baseline fixture owner now reconciles four empty regular systemd
unit masks for Ubuntu's automatic APT services/timers. Its existing whole-set
ownership preflight, atomic placement, interruption/retry and offline
verification apply; tests never stop an updater or repair those settings.
Explicit auto-mode preparation updates remain available. Fedora declares no
APT masks. The [environment guide](../tests/integration/Environment.md#reusable-preparation-ownership)
owns these reusable settings. This preparation-source change invalidates both
targets' old baseline/app-snapshot matching, even though Fedora adds no masks.

The composed live Fedora probe also exposed a fixture error: its synthetic
unconfined GDM account caller created the admission lock with the wrong SELinux
object type, causing the subsequent real `xdm_t` final-session call to refuse.
The admission probe now reuses the existing private interpreter fixture in the
actual GDM caller domain, checks that domain before libpam, and leaves runtime
labels and production policy alone. The composed live Fedora gates and full
matrix passed afterward. That diagnostic pass predates the preparation change
and does not close Fedora's separate fresh-install/reboot step 2a2.

Focused host validation passed **969/969** checks in
`20261014T160712Z-63417723/report.md`, covering the native helpers, runner and
baseline reconciliation/inspection owners. The generated coverage inventory
adds 48 unit cases (30,047 unit; 31,181 total); other counts are unchanged.
New cases use the existing modules' private/in-memory fixtures and add no host
resource or scheduling ownership. Product/package/build inputs are unchanged,
so no separate `make build` is required.

Ubuntu auto-mode baseline preparation and matching online app-snapshot capture
passed. A subsequent owned live restore verified all four APT units as
`masked` and `inactive`, the current confinement-helper bytes, and the complete
native matrix, including the previously failing generation equality. Its
nonsecret run identity was `6c0644190050431eaf49431230079127`;
maintenance cleanup restored the accepted baseline and finished successfully.
Live diagnosis supplies no fresh-install acceptance by itself.

The final Ubuntu fresh-install/reboot selector passed **2/2** executions in
`output/test-runs/host/reports/20261014T161737Z-6917aa55/report.md`.
Its retained evidence is
`output/test-runs/privileged/allocations/onpc-system-8ri3v6p2/evidence/`.
Both `guest/installed.xml` and `guest/rebooted.xml` contain one passed case,
zero errors/failures/skips, successful native positives, real credential
teardown, the complete execution denials, policy-loss refusal/recovery and
ordinary-account controls. Installed routing mutations/repair and retained
metadata recovery passed; the rebooted phase preserved the kiosk and both
ordinary roles' witnesses and repeated the nonmutating admission gates and
complete native matrix. No app snapshot substituted for either phase.
`result.json` independently records product, infrastructure, collection and
cleanup as passed, `cleanup_phase=complete`, and two successful baseline
verification calls. Both registered VMs were subsequently confirmed off.

| Qualified input | Exact identity |
| --- | --- |
| Returned DEB/fixture bundle | `output/test-runs/host/allocations/onpc-test-artifacts-2xgnqrzj` |
| DEB SHA-256 | `daa9c180960e1dfc72e026a7019bb71b2b63db3bd4c867a62e300f05f81b94fa` |
| Fixture SHA-256 | `8e053863e1b5326dbd535450b761cf47384045639d8e8bde822fa5f7b3a8c1c5` |
| Frozen selected-input SHA-256 (22 files) | `7f1297adf5a31e33b1caa61b22bae02028edd5367ee7ceb7d67533ded8fa4616` |
| Refreshed Ubuntu baseline provenance SHA-256 | `1d3a3a2f535adbde0cb3aadd4d388a1cc5c05265d1e7c885990a152ab143df81` |

The bundle was rebuilt and verified through auto-mode preparation; its package
source revision, digest and 348-file inventory match step 1. The fixture digest
above supersedes step 1's older fixture identity for this attempt. The result
and bundle manifest agree on all applicable package/source/fixture identities.

Additional attempts rotate the bounded journals. Before rotation, the documented
artifact exporter preserved three Phase 3 raw JUnits; all three were rechecked
present with matching hashes after the final run:

| Historical scope and source report | Retained file under `output/test-runs/host/exports/` | SHA-256 |
| --- | --- | --- |
| Ubuntu platform, `20261014T061225Z-a5e65c7a` | `onpc-artifact-export-re6apvzs/enforcement.xml` | `ccfccdbea43833b391f86ffd4a0b1d0dbb345268c2f47da8a675b22f415377d5` |
| Fedora platform, `20261014T061327Z-d1ded39a` | `onpc-artifact-export-6tra2cvf/enforcement.xml` | `412e475b70e489c512c6b69c01cf1f776c5ebd2366987e026d0e864196f55dd5` |
| Ubuntu shared integration/namespace, `20261014T061547Z-ad573776` | `onpc-artifact-export-gwi06axq/enforcement.xml` | `d7f688c7fafa6181915c7e8a50db0a27b2f91fbbb9254999de49da5be7578bbb` |

These exports preserve historical assertions and integrity, not matching
preparation for the changed baseline. Step 9 must reconcile exact applicability
of earlier confinement histories and schedule every required invalidated history
for complete requalification before steps 10–12 close. The export journal is
also bounded to three files; another export can retire the oldest of these.
Preserve required raw evidence through the maintained route before future
rotation, or repeat its complete history.

Changed Markdown links and whitespace checks passed. Step 2a1 is complete.
Step 2a2 is next and requires refreshed Fedora preparation
and the complete RPM fresh-install/reboot history. Step 2b's real GDM readiness
and restart-required presentation remain open, as do the original step 2 and
Phase 4 exit gate. No general customer E2E task was executed or closed.

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

For Phase 3 steps 5a–5c, first verify the current candidate and retained evidence,
map every required admission/execution assertion to its registered route, then
run only the selected slice's missing or affected checks on both targets.
Record exact inputs, results, gaps and owned cleanup before deciding whether
that slice passes. Step 5b's installed account/routing selector is registered
and qualified above; the execution matrix's `pam_start_confdir` fixture contains
only the final session gate and cannot substitute for that admission coverage.

Use `tools/run-tests --help`, `--list` and scoped system/E2E listings to verify
actual registered selectors. The commands below are routes for their owning
steps, not a batch to run in every session. The installed confinement/namespace/
platform selectors cover engineering assertions; `check_e2e_kiosk_entry` supplies
the strict waiting-session census. Cases 50, 51 and 52 independently own the
approved, denied and cancelled restricted-station journeys. The kiosk feedback
qualifier supplies native scanner/editor boundary evidence; existing case 192
can supply step 7a's kiosk About slice when its retained evidence applies.
The dedicated Preferences qualifier supplies step 7b's engineering surface and
waiting-session assertions. The error-report/privacy restrictions and
native/service positives in 7c must be mapped to actual maintained coverage
before claiming acceptance. Documentation is not registration.

The step 8 coverage audit separated its independent graphical-login (8a) and
shared integration histories (8b–8c). Together they preserve every original step 8
assertion. `check_e2e_fresh_desktop` already owns separate administrator and
standard-user GDM password-login attempts with independent prompt-free desktop
observations; reuse it for 8a without adding product-feature acceptance.
The admission matrix's ordinary account-stage success and the namespace
fixture's ordinary callbacks do not establish a real graphical desktop.
The original step 8b's vendor callback, ordinary metadata and effective
unit/policy assertions remain in the bounded 8b–8c split.
The 2026-10-13 audit found two independent installed histories: the existing
classification/restart/reboot selector, whose ordinary witness covered only the
administrator, and the missing shared-PAM/effective-policy scope qualification.
Step 8b extends and executes the metadata history; step 8c retains every vendor
callback and unit/policy assertion, including both ordinary roles. Neither slice
alone closes the original shared-integration step or Phase 3.

Step 8c's registered shared-integration selector now includes the complete
four-worker namespace qualifier and both ordinary managers' policy-scope checks.
Its retained result supplies all shared-PAM/collateral assertions together.

```bash
tools/run-tests system --artifacts '<current DEB or RPM allocation>' --area 'enforcement' --test 'test_kiosk_execution_confinement' --vm '<matching target>'
tools/run-tests system --artifacts '<current DEB or RPM allocation>' --area 'enforcement' --test 'test_kiosk_login_admission' --vm '<matching target>'
tools/run-tests system --artifacts '<current DEB or RPM allocation>' --area 'enforcement' --test 'test_kiosk_namespace_guard_callbacks' --vm '<matching target>'
tools/run-tests system --artifacts '<current DEB or RPM allocation>' --area 'enforcement' --test 'test_kiosk_shared_integration_scope' --vm '<matching target>'
tools/run-tests system --artifacts '<current DEB or RPM allocation>' --area 'enforcement' --test 'test_kiosk_platform_integrations' --vm '<matching target>'
tools/run-tests system --artifacts '<current DEB or RPM allocation>' --area 'package' --test 'test_kiosk_account_classification_survives_reboot' --vm '<matching target>'
tools/run-tests system --artifacts '<current DEB or RPM allocation>' --area 'removal' --test 'test_remove_reboot_reinstall' --vm '<matching target>'
tools/run-tests integration 'check_e2e_kiosk_entry' --vm 'onpc-Ubuntu26.04,onpc-Fedora44'
tools/run-tests e2e --id '50' --vm 'onpc-Ubuntu26.04,onpc-Fedora44'
tools/run-tests e2e --id '51' --vm 'onpc-Ubuntu26.04,onpc-Fedora44'
tools/run-tests e2e --id '52' --vm 'onpc-Ubuntu26.04,onpc-Fedora44'
tools/run-tests e2e --id '192' --vm 'onpc-Ubuntu26.04,onpc-Fedora44'
tools/run-tests integration 'check_e2e_kiosk_preferences_confinement' --vm 'onpc-Ubuntu26.04'
tools/run-tests integration 'check_e2e_kiosk_preferences_confinement' --vm 'onpc-Fedora44'
tools/run-tests integration 'check_e2e_kiosk_feedback_confinement' --vm 'onpc-Ubuntu26.04,onpc-Fedora44'
tools/run-tests integration 'check_e2e_fresh_desktop' --vm 'onpc-Ubuntu26.04'
tools/run-tests integration 'check_e2e_fresh_desktop' --vm 'onpc-Fedora44'
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
