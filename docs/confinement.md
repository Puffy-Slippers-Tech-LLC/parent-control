# Kiosk confinement: technical continuation brief

Confinement remains unfinished and is not release-qualified. This brief keeps
the execution plan, technical boundaries, remaining acceptance and evidence
needed for continuation. Historical session logs and intermediate progress
counts are omitted. Product expectations belong to the
[specification](Specification.md); implementation details belong to
[Lifecycle](SystemDesign/Lifecycle.md) and
[Package removal](SystemDesign/Package-Removal.md).

## Phased execution plan (current)

**Next phase: 3 — Qualify security and required functions. Step 5 is next.**

For **"execute next step in confinement.md"** or **"execute next Phase in
confinement.md"**, execute only the first unchecked step in the active phase,
including validation and owned cleanup, then stop. Preserve the existing step
numbers. Planning, a blocker or a partial result never closes a step or phase.
Record only useful current inputs, evidence, limits and remaining work here.

| Done | Phase 3 step | Required result before stopping |
| --- | --- | --- |
| [x] | **4 — Public workflows** | Current-package customer cases 53–57, 151, 191, 192, 254 and 259 pass on both targets under their existing recipes and acceptance contracts. |
| [ ] | **5 — Natural reminders** | Resolve unregistered tasks 311/311b and complete required natural-delivery, reminder persistence and Wellbeing lifecycle acceptance. Resolve the message-value contract and all prerequisites; preview, documentation and unresolved dependencies supply no acceptance. |

**Dependency gate before step 5:** the
[natural-reminder queue rows](TestAutomation/E2E-Task-Queue.md#ordered-task-queue)
retain pending 312a/312b, 311a/311b/311c and 135a prerequisites. Task 311 requires
[135a's genuine no-action update](TestAutomation/E2E-Tasks/135a-update-no-action.md).
Phase 4's v1.2 upgrade requires reboot and cannot satisfy that prerequisite.
Reconcile actual routes and dependency order before executing step 5, preserving
all natural-delivery, persistence and upgrade assertions. Select any earlier
prerequisite work explicitly in the plan and keep Phase 3 open; this gate does
not authorize Phase 4 work during step 4.

The existing preview/Wellbeing qualification covers default-state settings
suppression/restoration and environment preservation. Explicit original
true/false settings, natural delivery, crash/restart/login/upgrade and complete
customer acceptance remain outside that result and must be accounted for in
step 5. Preserve the 311b threshold-value versus live-balance contract blocker;
canonical threshold seconds and emitted body text must remain distinct.

| Done | Remaining phase | Required exit gate |
| --- | --- | --- |
| [ ] | **3 — Qualify security and required functions** | Applicable current-package security, active namespace and ordinary-user checks on both targets; actual scanner proof, usable editor/diagnostic download without sending feedback; remaining public cases and complete natural-reminder/Wellbeing acceptance. Keep engineering and customer results separate. |
| [ ] | **4 — Qualify package lifecycle and close confinement** | Genuine v1.2 DEB upgrade/activation/reboot; complete removal/reboot/reinstall/purge/retry/foreign-state history and final affected regressions on both targets; review all confinement changes and the preceding partial fix; reconcile every obligation and limitation before closure. |

### Phase 4 session steps

Phase 4 follows Phase 3's exit gate, subject to explicit dependency-order
reconciliation above. Its scope requires separate sessions. Once selected,
execute only the first unchecked row below. The
[removal design](SystemDesign/Package-Removal.md),
[upgrade acceptance](Publishing.md#upgrade-acceptance) and
[installed runner](../tests/integration/README.md#running-the-current-installed-suite)
own mechanics and expectations.

| Done | Phase 4 step | Required result before stopping |
| --- | --- | --- |
| [ ] | **1 — Coverage and verified inputs** | Map every remaining group 3/5 lifecycle obligation to its actual registered route and assertions; record missing installed coverage explicitly. Prepare genuine v1.2/current DEB assets through `check_e2e_upgrade_assets` and current RPM assets through the maintained builder. Record source/tag provenance, package hashes, returned allocations, affected selectors and report-retention needs. Preparation proves no upgrade or removal. Preserve the absent genuine prior RPM as unavailable coverage. |
| [ ] | **2 — Genuine DEB upgrade** | On Ubuntu, perform the actual v1.2-to-current transition without intervening removal/purge. Verify retained parental settings, required migration/retry behavior, activation notice, pre-reboot restrictions, new boot and broker/kiosk readiness against exact inputs. Extend missing guarded coverage identified in step 1 before claiming it; the existing changed-payload/reboot route alone does not establish every older-version/settings assertion. This result supplies no task 135a no-action acceptance. |
| [ ] | **3 — Ubuntu removal history** | Pass the complete registered `removal::test_remove_reboot_reinstall` history on current DEB input: active-kiosk and foreign hook/PAM refusals, successful inactive removal/account finalization, reboot, retained-state reinstall, packaged purge, reboot and fresh reinstall. Verify PAM/policy restoration, ordinary login/desktop health, other-account preservation and reboot notices throughout. |
| [ ] | **4 — Fedora removal history** | Pass the same complete maintained history on current RPM input, including native DNF removal and packaged purge, restored authselect, enforcing SELinux, account finalization, retained/fresh reinstall behavior and ordinary-user preservation. This is RPM lifecycle evidence, not historical-version RPM upgrade acceptance. |
| [ ] | **5 — Ubuntu interruption and recovery gaps** | Complete the additional installed histories identified in step 1 for interrupted/aborted cleanup, rollback and safe retry, durable admission barriers across payload erasure, and foreign/substituted ownership state. Prove preservation on refusal and successful owned finalization after resolution. Account for prior step 3 assertions without counting host-only fault fixtures as installed proof. |
| [ ] | **6 — Fedora interruption and recovery gaps** | Complete the corresponding RPM histories, including failed post-erase recovery through normal reinstall/reboot and repeated packaged purge. Preserve foreign state and recovery records until successful owned cleanup; verify the same confinement/account barriers and ordinary-user invariants. Reuse valid step 4 evidence only for the assertions it actually covers. |
| [ ] | **7 — Independent native-boundary review** | Review the original partial fix against `697a4c30` and all subsequent tracked/untracked confinement changes affecting GDM/PAM, credentials/teardown, locks/leases, executor roles, MAC transitions, private mounts/inodes/FDs, reexec and namespace callbacks on both distros. Apply the [independent-review checklist](#primary-source-routes-and-independent-review-checklist); record findings and resolve demonstrated defects with affected checks before closing this review slice. |
| [ ] | **8 — Independent lifecycle/function review** | Review the remaining complete change set: package/install/activation/removal ownership, account metadata/recovery, vendor drift, executable/plugin/service APIs, ordinary-user isolation and required public functions. Include test/harness ownership, provenance and evidence quality. Reconcile findings from both review slices with all five work groups; keep demonstrated defects and unproven required behavior open until resolved. |
| [ ] | **9 — Final candidate and host validation** | After the final product fix, run the affected host regressions and `make build`; prepare and verify final format-specific package inputs and matching snapshots. Record exact candidate identities and which earlier installed/customer results remain applicable. Schedule every invalidated upgrade, lifecycle or functional history as a separate bounded follow-up before final closure. |
| [ ] | **10 — Final Ubuntu qualification** | On the final DEB input, pass the confinement and namespace matrices, strict real waiting-session census and affected installed/public regressions. Retain current-input upgrade/lifecycle proof and all applicable Phase 3 results; repeat invalidated histories through their complete maintained routes. Record remaining limits and finish owned cleanup. |
| [ ] | **11 — Final Fedora qualification** | Perform the corresponding final RPM security, census and affected installed/public qualification, with enforcing SELinux and current-input lifecycle proof. Preserve the genuine prior-RPM limitation explicitly. Retain applicable Phase 3 results, complete required follow-ups and finish owned cleanup. |
| [ ] | **12 — Reconcile and close** | Reconcile every obligation in all five work groups against retained evidence, including Phase 3 natural-reminder/Wellbeing acceptance and both final review slices. Verify report retention and completed owned cleanup; update this record and deliver the detailed independent-review handoff covering the preceding partial fix. Check Phase 4 only when its unchanged exit gate passes; required acceptance gaps or unaccepted scope limits keep confinement open. |


The maintained removal selector owns a continuous five-phase reboot history;
steps 3 and 4 keep one complete history per distro. Do not split its private
phases into apparent independent passes. Steps 5 and 6 address remaining
recovery obligations without duplicating proven refusals. If an audit or review
exposes substantial implementation or multiple independent live histories,
split that unchecked row into narrower numbered steps before execution,
preserving every assertion and the phase exit gate.

Later source/package changes require affected requalification. Preserve useful
historical evidence while reopening or adding bounded follow-ups. Final checks
remain per distro and per history where further subdivision is needed.
An absent genuine prior RPM remains unavailable historical-upgrade coverage;
never fabricate a predecessor. A required acceptance gap or unaccepted scope
limit keeps closure open.

## Scope and review baseline

The five work groups define the complete confinement scope:

1. Public authentication, station eligibility and required customer workflows.
2. Durable AccountsService kiosk classification with metadata preservation.
3. Execution/security boundaries, ordinary-user isolation and package lifecycle.
4. WebKit/scanner, feedback/diagnostics, notifications and Wellbeing.
5. Genuine upgrade, bounded distro integration and final independent review.

The child must be able to use only the request app and its necessary services.
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

### Wellbeing and feedback qualification

Notification preview proves literal rendering/urgency/countdown and Cancel
behavior only. The ordinary-user qualifier preserves existing
`XDG_CONFIG_HOME`/`GSETTINGS_BACKEND` values, supplies fixture-home `.config`
and `dconf` defaults only if absent, and preserves presence/absence of
`DCONF_PROFILE` in the actual service environment. Do not force
`DCONF_PROFILE=user`: Ubuntu's baseline lacks that named profile.

Stop only the recorded Wellbeing invocation before changing the owned manager
environment. Include manager startup/readiness in cleanup ownership, capture
valid newly created InvocationID even on startup failure, and refuse malformed
or replaced identities. Verify backup, suppression, exact unset/default
restoration and recovery-record removal. Environment additions expire with the
owned manager; no persistent profile is created.

The kiosk editor qualifier checks editable document readback, prepared
`diagnostic-logs.zip`, ready Send and hidden/absent Download, attachment and
collection-failure controls. It never sends feedback or invokes a kiosk file
chooser. Ordinary Parent Download/Save uses receipt-bound exported ZIP inspection
and shared owned cleanup. Full customer histories remain separate.

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

These references preserve useful qualification inputs and limits, not a new
retention audit or universal acceptance. Revalidate manifests, actual retained
results and applicability before reuse. Preparation/builds do not establish
installed behavior; engineering probes do not establish complete customer cases.

Earlier engineering product inputs share package-source SHA-256
`12fe615cecc2f796133e44951a13aeca5b0ac657368fd2193b574d4bcd3a045a`,
348 files, revision `2f7bb34d3fe20d1a2b44f0d5903953cc29b8393c` and fixture digest
`6aa1707b82f35caa902cd048e3c6bb6a37ff034044be2d92ff23b81dbfbbddd0`.

| Target | Package SHA-256 | Latest named package allocation |
| --- | --- | --- |
| Ubuntu 26.04 | `edf72880b638036f942a8bc99d5180442db0a022c76eca04d502d9332297085f` | `onpc-parent-setup-onpc-Ubuntu26.04-12fe615cecc2f796133e44951a13aeca5b0ac657368fd2193b574d4bcd3a045a` |
| Fedora 44 | `891d3b8ff07a2e493f694fa88e865c458667a5d625feef8d10866a8279a9be78` | `onpc-parent-setup-onpc-Fedora44-12fe615cecc2f796133e44951a13aeca5b0ac657368fd2193b574d4bcd3a045a` |

| Scope | Ubuntu report / result allocation | Fedora report / result allocation |
| --- | --- | --- |
| Confinement matrix, including real teardown and six bootstrap substitutions | `20261013T065344Z-87bafee5` / `onpc-system-rukm46k5` | `20261013T062323Z-b90f02cd` / `onpc-system-bvglnb3d` |
| Actual scanner and kiosk feedback editor | `20261013T065541Z-84ce3666` / `onpc-graphical-smoke-czkn9pv7` | `20261013T062642Z-e0eaa977` / `onpc-graphical-smoke-b_k883nh` |
| Ordinary Parent diagnostic Download/Save | `20261013T064620Z-ffad67c3` / exported result below | `20261013T064620Z-fceb90fb` / `onpc-graphical-smoke-b3zo1eri` |
| Notification preview and default-state Wellbeing settings/environment | `20261013T151852Z-4cb0f9f4` / `onpc-graphical-smoke-gb6_iioz` | `20261013T151852Z-32f09eb2` / `onpc-graphical-smoke-2oh3sctn` |

Ubuntu's complete diagnostic-export result survives its expired original
allocation at
`output/test-runs/host/exports/onpc-artifact-export-agcro4c1/result.json`.
System evidence includes `evidence/guest/enforcement.xml`. Report roots are
`output/test-runs/host/reports/`; privileged allocations are under
`output/test-runs/privileged/allocations/`. Use maintained readers/exporters.

The final security helper digest is
`4d1eb8d70bcd3e77dab048013fafb88af18b1f7919e0e3e4b991ceed830c2610`,
with selected guest-input digest
`a99731e6082624a16a53232a0a90dcb19185ecc81006d5ba43d9a49c90ffef9a`.
Notification/Wellbeing results record helper digest
`701420854a5368cfc50f175c668e5ae4170f6d4ad5f414c9ca2d71bca739ac3f`
and qualification-source digest
`55b919dd31f8c92b171ddc4558ceb69638ae0bb6ad1af5f1af21e2c95f241309`.
Their customer product category is `not-run`; natural delivery and explicit
original true/false settings are not proved.

Active namespace callbacks have separate earlier-input evidence:
Ubuntu `20261013T033021Z-8f6970e8` / `onpc-system-1m801bty` and
Fedora `20261013T033134Z-7cd26e1b` / `onpc-system-x2rfahhz`.
Their package-source digest is
`f06b80cb6e496850e47fbb00661054b68cbb205aaff1f53e63a8a674d93ae346`,
with DEB `4a9659a2eeaae3c9e8d3fe5672245c8d3d56f57a1c0608df0fe10ba1868bc064`
and RPM `e2ddc426f48ad9ed443cd6c88dc462cd3f0bcb4a6794ddf922a7fa461c320664`.
The controls exercise ordinary/root open/init/close/credential callbacks, kiosk
suppression and parent namespace preservation. These identities differ from
the latest product inputs; determine affected requalification rather than
claiming byte-identical coverage.

Both targets' last recorded owned operations finished with baseline restoration
and VM off. Reconnect through maintained ownership checks before any new work;
a recorded terminal state is not current authorization or a live status probe.

### Public workflows (Phase 3 step 4)

Cases **53–57, 151, 191, 192, 254 and 259** passed on both targets on
2026-10-13. Each invocation retained ten independent complete attempts; product,
infrastructure, collection and cleanup all passed, including final suite closure.
Cases 254 and 259 used genuine product-free installation/reboot histories.

| Target | Report | Invocation evidence allocation |
| --- | --- | --- |
| Ubuntu 26.04 | `20261013T160314Z-d12f0a04` | `onpc-e2e-evidence-gqj6zt35` |
| Fedora 44 | `20261013T160314Z-dccb8cc0` | `onpc-e2e-evidence-j74_y5g7` |

The verified inputs retain package-source digest
`12fe615cecc2f796133e44951a13aeca5b0ac657368fd2193b574d4bcd3a045a`
(348 files), revision `ae1ae256253174d2dc224c9762e9aedef124c8cd` and fixture
digest `b605097e70b69abb86e32142a36ab762185d80f8df2e160dbdded5329d5d82ab`.
DEB SHA-256 is
`34ffdee65689db43d8b32989a1c0c299ef5dd38c16bc10ebc3dce6e6280db622`;
RPM SHA-256 remains
`891d3b8ff07a2e493f694fa88e865c458667a5d625feef8d10866a8279a9be78`.
The DEB archive differs from the earlier engineering input; package-source
identity is unchanged. Reports and all ten attempt records per invocation were
confirmed retained after final coverage generation. Both VMs were confirmed off
after successful baseline restoration.

The initial case 54 setup failed before product execution because the account
fixture filtered out the kiosk's required nologin identity. The shared fixture
now preserves that identity and excludes the reserved transient-greeter UID
range, retaining its existing mutation and preservation guards. Live probes of
all three station account profiles passed on both VMs before the clean rerun;
223 affected host checks and independent fixture review passed. Fixture helper
SHA-256 is `80ca3104d435628ede10a188e970a538d7b90ff9af85a41ae0998d4c366a6937`.
Implementation changes affect test code only; package/build inputs are
unchanged. Step 5 and its dependency gate remain open.

## Operating and qualification routes

Follow [AGENTS.md](../AGENTS.md), [Approval tools](Approval-Tools.md) and the
[test documentation map](TestAutomation/README.md). Read the
[VM](Mandates/VM-Mandate.MD),
[UI automation](Mandates/UI-Automation-Mandate.MD) and
[test storage](Mandates/Test-Storage-Mandate.md) mandates when their work is
triggered. This brief adds no alternate ownership or approval route.

Use registered `onpc-Ubuntu26.04` and `onpc-Fedora44`, exclusive ownership per
target and the maintained queue within its configured cap. Diagnose failures
live and validate fixes live before full E2E; stop owned maintenance before
installed/customer runs. Use bounded independent review/diagnosis subagents
when needed, with one editor for shared policy. Never use raw SSH/libvirt or
discard foreign state to recover a test.

Run affected host checks and `make build` after the final package-affecting edit,
then verify format-specific inputs and normal snapshot matching. Subsequent
product changes require affected qualification again. Documentation/test-only
changes outside package/build dependencies do not require a package rebuild.

### Continuation order and qualification routes

Use `tools/run-tests --help`, `--list` and scoped system/E2E listings to verify
actual registered selectors. Planned 311/311b/135a selectors must be implemented
and qualified before execution; documentation is not registration.

```bash
tools/run-tests system --artifacts '<current DEB or RPM allocation>' --area 'enforcement' --test 'test_kiosk_execution_confinement' --vm '<matching target>'
tools/run-tests system --artifacts '<current DEB or RPM allocation>' --area 'enforcement' --test 'test_kiosk_namespace_guard_callbacks' --vm '<matching target>'
tools/run-tests system --artifacts '<current DEB or RPM allocation>' --area 'enforcement' --test 'test_kiosk_platform_integrations' --vm '<matching target>'
tools/run-tests system --artifacts '<current DEB or RPM allocation>' --area 'removal' --test 'test_remove_reboot_reinstall' --vm '<matching target>'
tools/run-tests integration 'check_e2e_kiosk_feedback_confinement' --vm 'onpc-Ubuntu26.04,onpc-Fedora44'
tools/run-tests integration 'check_e2e_kiosk_notification_wellbeing' --vm 'onpc-Ubuntu26.04,onpc-Fedora44'
tools/run-tests integration 'check_e2e_diagnostic_export' --vm 'onpc-Ubuntu26.04,onpc-Fedora44'
tools/run-tests --vm 'onpc-Ubuntu26.04' integration 'check_e2e_upgrade_assets'
```

The upgrade-assets route uses `named_input(upgrade_source=True)` and returns
verified genuine v1.2/current manifests. The older source `4318ff…` lacks the
release tag and cannot qualify genuine upgrade. Use returned manifests and the
installed runner's `--previous-artifacts` route only for its documented scope;
its reboot assertions alone do not establish every older-version/settings
migration requirement or the no-action update profile.

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
- Required public workflows and ordinary parent/child/overlay behavior,
  notifications/Wellbeing, editor/diagnostics and both distributions.
- Test/harness isolation and evidence: successful positives before denials,
  actual kernel errors, frozen inputs, retained report scope and honest limits.

Distinguish demonstrated defects, plausible untested gaps and harness defects.
Resolve every required acceptance gap or retain it explicitly; release notes,
preview, source review and host tests cannot substitute for installed/customer
acceptance.
