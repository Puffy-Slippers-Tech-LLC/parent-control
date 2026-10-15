# Kiosk confinement: technical reference and qualification evidence

This reference preserves technical boundaries, review scope, historical inputs,
results and explicit coverage gaps. Historical next-step statements describe the
recorded session only. Current selection belongs solely to the
[execution plan](confinement.md) and its [ordered queue](Confinement-Task-Queue.md).
Historical completion does not qualify changed inputs or supply missing evidence.

## Historical qualification decomposition

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

This historical starting audit maps the then-remaining lifecycle obligations to
executable assertions; it supplies no installed activation, removal or recovery
pass. Later qualification sections record delivered coverage; use the
[current validation allocation](#validation-allocation-and-evidence-ledger) for
remaining work rather than treating this dated gap column as current readiness.
Registry listings
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

### Phase 4 step 2a2 — Fedora native activation — 2026-10-14

Fedora auto-mode baseline refresh, independent offline inspection and matching
online app-snapshot capture passed through the maintained preparation route.
The builder verified the returned RPM/fixture bundle. The RPM is byte-for-byte
identical to step 1's candidate; the refreshed fixture identity matches step 2a1.
Preparation finished with the VM off. No automatic package-transaction drift
was observed in the subsequent native lifecycle history.

The first complete attempt, `20261014T164051Z-4a9b5a67`, passed before reboot
but failed the rebooted package verification. Retained RPM output reported only
`.......T.` for `confinement/config.json` and `confinement/onpc-kiosk.cil`:
the fault fixtures restored bytes but changed modification times. A clean live
snapshot reproduced exactly those two timestamp differences after the native
matrix. This was a fixture-restoration defect; strict RPM verification and all
confinement expectations remain unchanged.

The shared native helper now restores append-only fault probes through the
original no-follow file descriptor, including bytes and nanosecond access and
modification timestamps. It preserves the inode, permissions and SELinux label.
All four config/policy/PAM append probes use the same context manager. Existing
executable/library/plugin replacement probes retain their original rename-based
restoration. Focused host validation passed **499/499** checks in
`20261014T165120Z-4de55184/report.md`. Three new private-file regressions cover
normal and exception restoration and symlink refusal. Their tiny pytest-private
files add no shared resource or cleanup owner; the existing compatible module
classification remains applicable. Generated coverage adds exactly three unit
cases (30,050 unit; 31,184 total).

Before the final installed attempt, the exact revised helper (SHA-256
`6a02d0f42c5e2d597efd1fb2c40db068959e30e5cbc61dc572491298031e79e6`)
passed the full native matrix in owned live Fedora maintenance, with strict RPM
verification both before and afterward and SELinux enforcing. That diagnostic
supplies no fresh-install acceptance. Its owner completed guarded cleanup and
baseline restoration before qualification.

The final `package::test_kiosk_account_classification_survives_reboot` attempt
passed **2/2** executions in
`output/test-runs/host/reports/20261014T165546Z-5dc4b2ba/report.md`.
Retained evidence is
`output/test-runs/privileged/allocations/onpc-system-7scvn66q/evidence/`.
Both `guest/installed.xml` and `guest/rebooted.xml` contain one passed case and
zero errors, failures or skips. The continuous fresh-install/reboot history
proved exact package readiness, preboot `RebootRequired` with unchanged execution
rules, cleared reboot request, loaded/enforcing native confinement, matching
manager/helper generations, native positives before execution denials, real
credential/teardown confinement and stale/missing/unenforced-policy refusal and
recovery. Installed alternate-session/transport refusal, routing repair and
successful retry passed before the retained witness. Gates after AccountsService
restart and the new boot preserved dedicated admission, exact terminal/SSH
denials and ordinary controls. Kiosk identity/classification and both ordinary
roles' complete metadata witnesses survived. No app snapshot substituted for
either lifecycle phase.

| Qualified input | Exact identity |
| --- | --- |
| Returned RPM/fixture bundle | `output/test-runs/host/allocations/onpc-test-artifacts-rpkjnrlo` |
| RPM SHA-256 | `630ab36562dd7f85d1a2b4f0cbf2f359972b6ac29fe4dcb2e5a051f5723afaf4` |
| Fixture SHA-256 | `8e053863e1b5326dbd535450b761cf47384045639d8e8bde822fa5f7b3a8c1c5` |
| Frozen selected-input SHA-256 (22 files) | `3d2dd08e4368ecf7a09987b3e9e41fd186d570f7b6f059382a23105622ddf457` |
| Refreshed Fedora baseline provenance SHA-256 | `8d9c69f0f0c1bc1a58db150aa6081dc42ef0f3b035ff396786733b14a68fbf7f` |

The result and manifest agree on package/source/fixture identities. Package
source remains revision `f84b688281f27ade9e737b2b6a2930646db3541c`, digest
`b0c09311fe1b52b87bebd7699caab30829edc3c789329e50ae550c38eeb7b6c5`
and 348 files. Only test/helper and documentation inputs changed; the Makefile's
package sources and build dependencies are unaffected, so no separate
`make build` is required. Step 9 must reconcile the changed selected-input
identity with earlier evidence under its existing applicability gate.

`result.json` records product, infrastructure, collection and cleanup as passed,
`cleanup_phase=complete`, and two successful baseline verification calls.
Both registered VMs were independently confirmed off after owned cleanup.
Final artifact verification and 313 plan/inventory/coverage/composition checks
passed (**314/314** total) in `20261014T170427Z-ffa2fd8a/report.md`.
Changed Markdown links and whitespace checks passed. The exact RPM hash and all
three historical Phase 3 exports recorded in step 2a1 were rechecked after final
validation and still match; no new export rotated that bounded journal. Retain
this attempt's raw JUnits and result before future per-VM rotation, following
the existing evidence-retention gate.

Step 2a2 is complete. Step 2b's real GDM activation/readiness history remains
next; original step 2 and the Phase 4 exit gate stay open. No general customer
E2E task was executed or closed.

### Phase 4 step 2b — real GDM activation readiness — 2026-10-14

The registered `package::test_kiosk_account_classification_survives_reboot`
history now observes actual public GDM entry before and after its real reboot.
The shared station adapter focuses the identified account, independently proves
the fresh keyboard recipient and submits Enter once under the VM/boot guards.
Before reboot it requires the owned restart modal and unavailable policy form;
after reboot it requires the usable default request form and absent restart
modal. Each phase then runs the unchanged strict process/thread census with
manager, app, service, Wellbeing and PipeWire roles, exits through public
controls and independently observes usable sign-in. Fedora's census checks each
domain's enforcing flag, not only the global SELinux flag.

The first Ubuntu attempt, `20261014T183545Z-4618d843`, passed its native phase
but found no station row in the existing greeter; it reached no real admission
boundary and supplies no refusal credit. Separate owned maintenance confirmed
entry in the prepared instance before and after the account-interruption
fixtures. The installed consumer now renews the greeter after installation in
the same boot, refusing renewal when a personal graphical session is present.
Real preboot entry precedes deliberate metadata/fault fixtures, so subsequent
GDM writes cannot invalidate their retained reboot oracle. Postboot entry follows
the complete native matrix and metadata assertions. No app snapshot replaces
either phase, and the reboot request and execution rules remain checked around
real entry. Maintenance cleanup restored the baseline before acceptance.

Both final continuous histories passed **2/2** native executions plus both real
GDM observations, retaining every 2a admission, execution, policy-loss/recovery
and ordinary-account assertion. All four native JUnits have one passed case and
zero errors, failures or skips. The raw results also prove distinct boot hashes,
current enforcing labels, private namespaces and matching manager generations
for every relevant kiosk process/thread in all four real sessions.

| Target | Original host run | Retained allocation under `output/test-runs/privileged/allocations/` |
| --- | --- | --- |
| `onpc-Ubuntu26.04` | `20261014T185419Z-e7a362c1` | `onpc-system-06uze6y_` |
| `onpc-Fedora44` | `20261014T190220Z-c825a98a` | `onpc-system-wf9_plvf` |

Each allocation retains `evidence/result.json`, `evidence/guest/installed.xml`,
`evidence/guest/rebooted.xml` and both
`evidence/guest/attempt-installed/gdm-{installed,rebooted}.json` files.
The result records product, infrastructure, collection and cleanup as passed,
`cleanup_phase=complete` and two successful baseline checks. Both registered
VMs were independently confirmed off after owned cleanup.

Package/source/fixture identities match the accepted 2a candidate: DEB
`daa9c180960e1dfc72e026a7019bb71b2b63db3bd4c867a62e300f05f81b94fa`,
RPM `630ab36562dd7f85d1a2b4f0cbf2f359972b6ac29fe4dcb2e5a051f5723afaf4`,
fixture `8e053863e1b5326dbd535450b761cf47384045639d8e8bde822fa5f7b3a8c1c5`.
The source remains revision `f84b688281f27ade9e737b2b6a2930646db3541c`,
package digest `b0c09311fe1b52b87bebd7699caab30829edc3c789329e50ae550c38eeb7b6c5`
and 348 files. Ubuntu/Fedora baseline digests remain those recorded in 2a1/2a2.
Both final attempts bind the same selected-input digest
`8b293d3d148c9cec9471fd97777ade4efab5a2b632b076d35690508c8a0a7e0c`:
22 frozen guest files and 19 declared host observer/transport source hashes,
checked before and after entry. Verified builder returns were
`onpc-test-artifacts-2dr2gibr` and `onpc-test-artifacts-kpr_81yy`; retained
`input/` copies remain available when bounded builder caches retire.

The 2a raw results were inspected for applicability; the final histories repeat
their complete native proof against the current helpers. Required raw results
must be exported before future journal rotation under the existing
[retention gate](#phase-4-step-1--coverage-and-verified-inputs--2026-10-13).
All three historical Phase 3 exports recorded in 2a1 matched their hashes before
the final host export. That bounded journal then retired Ubuntu platform export
`onpc-artifact-export-re6apvzs/enforcement.xml`; the Fedora platform and Ubuntu
shared/namespace exports still match their recorded hashes. The existing 4-9
applicability gate and 4-10 complete Ubuntu qualification must supply the current
platform history; the retired proof supplies no final acceptance credit.
Final host verification passed **1312/1312** selected checks in
`20261014T192048Z-1f16c319`, including the scoped regressions and
plan/inventory/composition checks. Its complete report is retained at
`output/test-runs/host/exports/onpc-artifact-export-vtah4grl/report.md`.
A fake-terminal fixture now declares its ANSI mode explicitly; the correction
preserves every assertion and changes no launcher behavior. The generated
inventory was refreshed. New unit cases use private/in-memory
fixtures under their existing compatible classifications. Package/build inputs
are unchanged, so no separate `make build` is required.

Step 2b completes the original step 2 activation boundary. Step 4-3 is next;
the Phase 4 exit gate, general notice wording, saved-data migration and customer
E2E qualification remain with their existing owners.

### Phase 4 step 3 — Ubuntu removal history — 2026-10-14

The complete registered `removal::test_remove_reboot_reinstall` history passed
**11/11** executions on `onpc-Ubuntu26.04`: six installation prerequisites and
the continuous five-phase remove/reboot/retained reinstall/purge/reboot/fresh
reinstall history. Host run `20261014T205701Z-b2eaf814` retains its raw results at
`output/test-runs/privileged/allocations/onpc-system-vloayn9_/`.
All seven `evidence/guest/{installed,rebooted,removal,removed-rebooted,reinstalled-rebooted,purged-rebooted,purge-reinstalled-rebooted}.xml`
files have zero errors, failures or skips. Both
`evidence/guest/attempt-installed/gdm-{installed,rebooted}.json` observations
passed on distinct boots, including strict native confinement and public entry/exit.

The guest now captures PAM bytes, modes and local/vendor selection independently
before initial installation. All four removed/purged endpoints match that original
witness and retain `onpc.removal.pam-restored` in their JUnits:

| Service | Original selection | Mode | SHA-256 |
| --- | --- | --- | --- |
| `gdm-password` | local | `0644` | `08e1f43267a73fb6f57e58c13332d4d5c9057b3129a528479cc1287712c74ec0` |
| `systemd-user` | vendor | `0644` | `78e3e88bd7c242228040dcbcdbae383109508b89a4848b187de77db2520a22ab` |

The same history passed active-kiosk and foreign hook/PAM refusal, retained
payload/policy checks, inactive account finalization, ordinary native execution,
desktop/password health after removal and purge, retained preferences after
ordinary reinstall, cleared one-time grants and fresh defaults after purge.
Completed endpoints do not establish the payload-erased surviving-account
admission interval; that explicit obligation remains in **4-5c** on both targets.

Mechanical fixture repairs preserve those assertions. After public GDM exit, an
identity-checked read-only wait lets the preceding manager finish naturally
before the fixture starts its own manager. A refused Debian PAM transaction can
leave an intact package half-configured; absence checks now distinguish that
state, verify payload before resolving the owned edit, finish already-unpacked
configuration with native `dpkg --configure`, then require strict configured
status and unchanged policy. Separate live maintenance reproduced this transition
and confirmed the PAM module inode stayed unchanged. Actual installation and
reinstallation still use `make install`.

A later complete attempt exposed a contradictory purge oracle: real GDM language
setup creates the other account's personal-only preference record, which purge
must delete. Live reproduction showed only that record disappearing, with all
four native policy values unchanged. Ordinary removal/retained reinstall still
require the full original account witness; purge/fresh reinstall independently
require the original native policy and absent erased preferences. The corrected
helper passed against that live post-purge state, while its ordinary-retention
check still rejected the missing record. Both maintenance instances finished
baseline restoration before the final clean acceptance.

Verified input `onpc-test-artifacts-tb9d9ooy` and retained `input/` copies bind DEB
`daa9c180960e1dfc72e026a7019bb71b2b63db3bd4c867a62e300f05f81b94fa`,
fixture `8e053863e1b5326dbd535450b761cf47384045639d8e8bde822fa5f7b3a8c1c5`,
package source revision `f84b688281f27ade9e737b2b6a2930646db3541c`, digest
`b0c09311fe1b52b87bebd7699caab30829edc3c789329e50ae550c38eeb7b6c5`
and 348 files. Ubuntu baseline remains
`1d3a3a2f535adbde0cb3aadd4d388a1cc5c05265d1e7c885990a152ab143df81`.
Selected-input digest is
`957e69e472db2838d16faa66e50afb0e2d90eea7548b0e628b4e42ce98ec96f7`:
28 guest bindings and 19 host bindings, covering 45 distinct source files,
all rehashed against the current checkout after acceptance with no mismatch.

`evidence/result.json` records product, infrastructure, collection and cleanup
passed, `cleanup_phase=complete`, all expected executions collected and two
successful baseline checks. The VM was independently confirmed off. Raw evidence
is retained in that allocation; preserve it through the maintained exporter
before future journal rotation under the existing retention gate. Test/doc-only
changes do not affect package/build inputs, so no separate `make build` is required.

Final scoped host validation passed **845/845** in
`output/test-runs/host/reports/20261014T211127Z-bad2cdb2/report.md`: affected
guest/removal/runner regressions, host inventory, plan/inventory/coverage and
case-composition checks after queue close-out. New cases use private files and
process-local command/state doubles; the applicable unit, UI and cleanup
inventories retain their existing classifications. Coverage was regenerated;
changed Markdown links and whitespace checks passed. Only 4-3 was checked,
its temporary brief was removed and the master pointer advanced to **4-4**.

### Phase 4 step 4 — Fedora removal history — 2026-10-14

The complete registered `removal::test_remove_reboot_reinstall` history passed
**11/11** executions on `onpc-Fedora44`: six installation prerequisites and
the continuous five-phase native DNF removal/reboot/retained reinstall/packaged
purge/reboot/fresh reinstall history. Host report
`output/test-runs/host/reports/20261014T221836Z-debb5e46/report.md` retains the
result; raw evidence is in
`output/test-runs/privileged/allocations/onpc-system-kg6m_ocm/`.
All seven `evidence/guest/{installed,rebooted,removal,removed-rebooted,reinstalled-rebooted,purged-rebooted,purge-reinstalled-rebooted}.xml`
files have zero errors, failures or skips. Both
`evidence/guest/attempt-installed/gdm-{installed,rebooted}.json` observations
passed on distinct boots, including public kiosk entry/exit and every required
strict native census role under enforcing SELinux.

All four removed/purged endpoints retain `onpc.removal.pam-restored` and match
the independent original bytes, modes and local/vendor selection captured before
installation:

| Service | Original selection | Mode | SHA-256 |
| --- | --- | --- | --- |
| `gdm-password` | local | `0644` | `cb6415a67e63dbc99c40c4b156ebdf7956f16e180401dd35ecc2d757351f5e25` |
| `systemd-user` | vendor | `0644` | `40275c8e16f29735096248ac71d41663e73195b7ab54b4a7a98a5f186c81c9e2` |

The complete assertions passed original authselect profile/features restoration,
enforcing SELinux, active-kiosk and foreign hook/PAM refusal, payload/policy
preservation on refusal, inactive kiosk account/home/cache finalization, ordinary
desktop/password/native-execution controls, retained preferences after ordinary
reinstall, cleared one-time grants and fresh defaults after purge. The
payload-erased surviving-account interval remains explicit in **4-5c** on both
targets; failed real RPM post-erase recovery remains explicit in **4-6**.

Mechanical test repairs preserve those assertions. The account fixture's copied
icon was root-only, causing the blank greeter image observed during testing; it
now uses the packaged image's greeter-readable `0644` mode. Private metadata and
collision/ownership guards remain intact. The shared native probe waits up to
75 seconds for preceding GDM logout to settle naturally, with guest/UID guards
and no adoption or signalling. The strict census retries only an inconclusive
process-lifecycle race, discarding the entire observation within five seconds
while retaining the same manager pidfd and rechecking enforcing policy and
manager identity. Security failures still fail immediately; no partial role
counts are combined. Each repair passed separate live Fedora diagnostics before
the final clean history; those diagnostics supply no acceptance credit and their
owned maintenance cleanup finished.

Verified input `onpc-test-artifacts-qovyjxvm` and retained `input/` copies bind RPM
`a97fc5b0472a4e287f0acde7926c1679918ef0df2c5a580f7bbda77018a67005`,
fixture `8e053863e1b5326dbd535450b761cf47384045639d8e8bde822fa5f7b3a8c1c5`,
package source revision `f84b688281f27ade9e737b2b6a2930646db3541c`, digest
`c65bae1df4a0998cf13875f5be99a41a123b21ace306885c3ffb17127d4619d4`
and 348 files. Fedora baseline is
`8d9c69f0f0c1bc1a58db150aa6081dc42ef0f3b035ff396786733b14a68fbf7f`.
Selected-input digest is
`f9e1ab6bdf1dc327eaedaad52d99419f9cfdfd007e1464f23110634d03155b30`:
28 guest bindings and 19 host bindings, covering 45 distinct source files,
all rehashed against the checkout after acceptance with no mismatch.

`evidence/result.json` records product, infrastructure, collection and cleanup
passed, `cleanup_phase=complete`, all 11 expected executions collected and two
successful baseline checks. The VM was independently confirmed off. Preserve
the retained raw evidence through the maintained exporter before future journal
rotation. Only test/doc files changed, outside package/build inputs; no separate
`make build` is required. Earlier Ubuntu history remains historical evidence;
**4-10** must qualify the final Ubuntu candidate with these current shared helpers.

Final scoped host checks passed **816/816** after queue close-out in
`output/test-runs/host/reports/20261014T223603Z-8b49c522/report.md`: affected
guest/removal/account regressions, host inventory, execution-plan and
plan/inventory/coverage/case-composition consistency. Runner and existing native
confinement regressions passed **587/587** in
`output/test-runs/host/reports/20261014T221414Z-bda6fcc2/report.md` after the final
census edit. New cases use tiny private files and process-local doubles; existing
compatible classifications remain applicable, with no added cleanup owner.
Coverage was regenerated, changed Markdown links and whitespace checks passed,
and retained raw acceptance evidence was rechecked after final validation. All
workers completed before acceptance and owned cleanup. Only **4-4** was checked,
its temporary brief was removed and the master pointer advanced to **4-5**.

### Phase 4 step 5a — in-flight admission refusal — 2026-10-14

Both targets passed **11/11** executions of the complete registered
`removal::test_remove_reboot_reinstall` history: six installation/reboot
prerequisites and the continuous five-phase removal/reinstall/purge history.

| Target | Report under `output/test-runs/host/reports/` | Raw allocation under `output/test-runs/privileged/allocations/` |
| --- | --- | --- |
| `onpc-Ubuntu26.04` | `20261014T233809Z-7e96356e/report.md` | `onpc-system-o6cqara2` |
| `onpc-Fedora44` | `20261014T231536Z-7c6f85ff/report.md` | `onpc-system-f7mk50nm` |

Each `evidence/guest/removal.xml` records successful ordinary PAM/native
controls, a live root `gdm-password` PAM handle before kiosk credentials,
native removal's exact admission refusal, preserved payload/shared PAM/authselect
and ownership/recovery records, loaded enforcing confinement and effective child
denial/ordinary access. Fedora retains enforcing SELinux and checks the real
`xdm_t` caller domain. EOF releases only the owned holder through successful
`pam_end` and normal exit; exclusive removal preflight, fresh admission gates
and the same history's successful removal/finalization follow.
All seven phase JUnits have zero errors, failures or skips, including exact
original PAM restoration at every removed/purged endpoint and the retained
ordinary-user, saved-state and fresh-reinstall assertions.

Both frozen inputs have selected-input SHA-256
`96482b5a3c117bd8c2ac92c565a415737946d788af16e6fb880cca5cb7a2e207`:
28 guest and 19 host bindings, covering 45 distinct source files, all rehashed
against the checkout without mismatch. Package source is revision
`a59e9b6aa1da173114f20421b5dc24d05cb559db`, 348 files, digest
`c65bae1df4a0998cf13875f5be99a41a123b21ace306885c3ffb17127d4619d4`;
fixture digest is
`8e053863e1b5326dbd535450b761cf47384045639d8e8bde822fa5f7b3a8c1c5`.
DEB SHA-256 is
`8eceef9c9efad47800d49c754448dece0992577619dd59cf55efa80b23675057`;
RPM SHA-256 is
`a97fc5b0472a4e287f0acde7926c1679918ef0df2c5a580f7bbda77018a67005`.
Refreshed baseline digests are
`5a3aeb6e7c4867e930d534da85060915b634a863137fbe724689dd7e80aafd93`
(Ubuntu) and
`fd7774dfe68092ea8e09b8cf00046d32ad6393c06ea9b5cd3edc36f9b6c4db3c`
(Fedora). Earlier readiness refusals and preparation supply no acceptance credit;
the earlier Ubuntu pass was repeated after the assertion changes.

Both aggregate results record product, infrastructure, collection and cleanup
passed, `cleanup_phase=complete`, all 11 expected executions and two successful
baseline checks. Serial owned VM/host cleanup passed and both VMs were confirmed
off. All subagents finished before acceptance. Implementation changes are confined
to tests, documentation and test-scheduling rationale; authorized preparation also
refreshed the generated project-tool rules. No package/build input changed and no
separate `make build` is required. Coverage was regenerated; the new host cases
retain private files/process-local doubles and compatible unit/cleanup
classifications.

Final affected admission/removal/runner, cleanup, host inventory, coverage and
plan/composition consistency checks passed **1028/1028** in
`output/test-runs/host/reports/20261014T235217Z-2e6d3032/report.md` after queue
close-out. Changed Markdown links and whitespace checks passed. Retained raw
acceptance evidence was rechecked after final validation. Only **4-5a** was
checked, its temporary brief was removed and the master pointer advanced to
**4-5b**; every other row retains its status, order and scope.

### Phase 4 step 5b — aborted cleanup and rollback — 2026-10-14

Both targets passed **8/8** executions of the newly registered
`removal::test_aborted_cleanup_rollback_retry`: six fresh installation/reboot
prerequisites and two continuous recovery phases, separated by a real reboot
after native rearming. The original five-phase removal selector retains its scope.

| Target | Report under `output/test-runs/host/reports/` | Raw allocation under `output/test-runs/privileged/allocations/` |
| --- | --- | --- |
| `onpc-Ubuntu26.04` | `20261015T004820Z-a917af84/report.md` | `onpc-system-ysg11gis` |
| `onpc-Fedora44` | `20261015T004820Z-789acd8c/report.md` | `onpc-system-8mr37oij` |

Each `evidence/guest/rollback.xml` proves actual clearing of native limits, grant,
filter, extension and generated policy, with the saved snapshot matching the
pre-cleanup state. An identity-owned read-only bind mount preserves PAM bytes
while blocking atomic replacement. Retained native transaction logs show DEB
prerm failure and postinst abort-remove, or RPM preun failure and its EXIT rollback.
The observer's snapshot and durable GDM-denial witnesses remain in
`evidence/guest/attempt-rollback-installed/rollback-*-observed-*.txt`, alongside
`rollback-*-command-0001.txt`; missed transitions fail explicitly.

Before releasing the mount, both histories independently require restored exact
enforcement, child execution denial, both ordinary roles' access and preserved
account/home identities, preferences and ownership records, with admission marker
and broker mask retained. Fedora keeps SELinux and the relevant domains enforcing.
Native authselect record republication changes only its inaccessible group from
wheel to root: bytes, root owner and exact mode 0600 remain required; seven host
variants reject other changes. Native rearming then clears the guards. Fedora's
expected `legacy-pam-reboot-required` preflight is resolved by the same history's
real reboot, never by bypassing the mapped-module guard.
Each `rollback-rearmed-rebooted.xml` proves a new boot, preserved restored
protection and identities, successful native removal, verified kiosk-account/home
deletion, exact original PAM/authselect restoration and ordinary-user access.
All four JUnits per target have zero failures, errors or skips.

Both frozen selected-input manifests have SHA-256
`20fdd68112f5a2a29adb5daf0054f75cc2c48034e7a730af167959f3091bccea`:
28 guest and 19 host bindings covering 45 distinct source files, all rehashed
against the checkout without mismatch. Package source is revision
`a59e9b6aa1da173114f20421b5dc24d05cb559db`, 348 files, digest
`c65bae1df4a0998cf13875f5be99a41a123b21ace306885c3ffb17127d4619d4`;
fixture digest is
`8e053863e1b5326dbd535450b761cf47384045639d8e8bde822fa5f7b3a8c1c5`.
DEB SHA-256 is
`8eceef9c9efad47800d49c754448dece0992577619dd59cf55efa80b23675057`;
RPM SHA-256 is
`a97fc5b0472a4e287f0acde7926c1679918ef0df2c5a580f7bbda77018a67005`.
Baseline digests remain
`5a3aeb6e7c4867e930d534da85060915b634a863137fbe724689dd7e80aafd93`
(Ubuntu) and
`fd7774dfe68092ea8e09b8cf00046d32ad6393c06ea9b5cd3edc36f9b6c4db3c`
(Fedora). Each retained `evidence/result.json` records all eight exact expected
and executed identities, product/infrastructure/collection/cleanup passed,
`cleanup_phase=complete` and two successful baseline checks. Serial owned VM/host
cleanup passed; both VMs were confirmed off. All subagents finished before acceptance.

Affected controller/snapshot, input, JUnit, resume, cleanup, inventory and
plan/composition host checks passed: 1,103 unchanged cases in
`20261015T004713Z-c54561d7/report.md`, plus the repaired removal module's
**310/310** in `20261015T004751Z-b1b69e43/report.md`. The former run's one missing
test import was repaired and its entire module rerun; no product assertion changed.
Coverage was regenerated. The added host fixtures use private files and command/VM
doubles and retain compatible unit/cleanup classifications. No package/build input
changed, so no separate `make build` is required. Earlier seven-execution results
do not qualify this final eight-execution history. The old 4-5a raw allocations
have expired, and its selected helper/controller inputs differ; no full-history
reuse is claimed. Its complete repeat remains required in 4-10 under the ledger.
Final plan-launcher and coverage checks passed **121/121** in
`20261015T010155Z-2c4558ab/report.md`. Changed Markdown links and whitespace checks
passed. Only 4-5b was checked, its temporary brief was removed and the master
pointer advanced to 4-5c; every other queue row retains its status, order and scope.

### Phase 4 step 5c — interrupted finalization and durable admission barriers — 2026-10-14

Both targets passed all three registered
`removal::test_interrupted_finalization_retry` variants: **48/48** executions
and 24 complete JUnits, each with zero failures, errors or skips. Every history
keeps its six fresh installation/reboot prerequisites and two continuous recovery
phases; no snapshot or earlier result substitutes for a predecessor.

| Variant | Target | Report under `output/test-runs/host/reports/` | Raw allocation under `output/test-runs/privileged/allocations/` |
| --- | --- | --- | --- |
| `mac-unload` | `onpc-Ubuntu26.04` | `20261015T025921Z-c5e14821/report.md` | `onpc-system-4nvq425m` |
| `mac-unload` | `onpc-Fedora44` | `20261015T025921Z-36913a0e/report.md` | `onpc-system-96a78lkm` |
| `account-finalization` | `onpc-Ubuntu26.04` | `20261015T031147Z-81a1b0c5/report.md` | `onpc-system-1vjiyph_` |
| `account-finalization` | `onpc-Fedora44` | `20261015T031147Z-2577a976/report.md` | `onpc-system-4e6wvvam` |
| `denial-publication` | `onpc-Ubuntu26.04` | `20261015T032606Z-36c5f2a1/report.md` | `onpc-system-xiu888_t` |
| `denial-publication` | `onpc-Fedora44` | `20261015T032606Z-781f82d1/report.md` | `onpc-system-ftkrnizo` |

Each `evidence/guest/<variant>.xml` records real native cleanup, the independent
cleared-policy/snapshot/GDM-denial witnesses and the intended owned interruption.
The MAC fixtures retain `removal-unload-*-triggered.txt` with the exact unload
refusal. Publication and unload refusals preserve payload, ownership/foreign
state and identities, and verify restored native protection, child denial and
ordinary-user access before releasing the fault. Fedora keeps SELinux and the
relevant domains enforcing.

Both account-finalization histories prove actual payload erasure with the owned
account, home and recovery records retained. Ordinary controls precede kiosk
`pam_acct_mgmt` and `pam_open_session` denials through both `gdm-password` and
`systemd-user`: ordinary status 0, kiosk status 7, successful PAM teardown.
The distro-only barriers remain effective with the product module and MAC policy
absent. Ubuntu completes the native postrm retry, then reboots to verify removal.
Fedora uses normal reinstall to restore protection, then reboot and native removal.
The other variants rearm protection before rebooted removal. Every endpoint verifies
owned account/home deletion before exact original PAM bytes, modes and
local-versus-vendor disposition, plus Fedora authselect restoration and ordinary-user
access.

The installed Fedora recovery exposed a configure-order defect: saved execution
policy was restored before its native daemon was ready. Configure now starts and
verifies those dependencies before restoring the snapshot, then reloads MAC and
restores PAM while migration exclusion and durable denials remain. Scoped source
review found no correctness issue. A separate current-package live reboot isolated
a test identity defect: Btrfs changed only its runtime device number. Persisted
home checks now require filesystem UUID/type, Btrfs subvolume, inode, ownership and
mode; same-boot fault cleanup retains exact device/inode, descriptor and mount guards.

All six selected-input manifests have 29 guest and 19 host bindings covering
46 distinct files, rehashed against the final checkout without mismatch.
Per-variant selected-input SHA-256 (equal on both targets):

| Variant | SHA-256 |
| --- | --- |
| `mac-unload` | `ab22247194a77459eeffd540b621e948580a829e25c4647f4fac62db76b74c1a` |
| `account-finalization` | `649b17a86f925e27bc7da5c37f79b3f0c09dcdd9725b38d7bc3aec5fda434f7e` |
| `denial-publication` | `679ae980c4a625808a5fb7742122e61ecad31de36f68c8f839af8b6b51f7482f` |

Package source is revision `a59e9b6aa1da173114f20421b5dc24d05cb559db`,
348 files, digest `80972bc053b325b9fc7839265afe428a774802afce120a90645c2c3f8e278fac`.
DEB SHA-256 is `63a2fb46d000b9de7537fdc4271dccf54a02f4b31292bb5cb3db529a23265fb4`;
RPM SHA-256 is `b949151c319a7cac0ab1df36a08f944ae67845ddf32ecb4c29b2ca1879a1cef2`.
Fixture digest remains `8e053863e1b5326dbd535450b761cf47384045639d8e8bde822fa5f7b3a8c1c5`;
baseline digests are `5a3aeb6e7c4867e930d534da85060915b634a863137fbe724689dd7e80aafd93`
(Ubuntu) and `fd7774dfe68092ea8e09b8cf00046d32ad6393c06ea9b5cd3edc36f9b6c4db3c` (Fedora).

Each `evidence/result.json` has all eight exact expected/executed identities,
product/infrastructure/collection/cleanup passed, `cleanup_phase=complete` and two
successful baseline checks. All 36 result/input/JUnit files were rechecked retained
after the final run. Owned maintenance and runner cleanup completed; both VMs were
confirmed off and all subagents finished before acceptance.
Affected host checks passed **1,639/1,639** in
`20261015T025909Z-f633cc38/report.md`. `make build` passed after the final package
edit; both installed packages match the hashes above. Coverage was regenerated;
new fixtures retain private storage and reviewed compatible resource classifications.
Changed Markdown links and whitespace checks passed. Only 4-5c was checked, its
temporary brief removed and the master pointer advanced to 4-5d. Remaining ownership,
Fedora repeated-purge and final qualification obligations stay open in their owners.

### Phase 4 step 5d — PAM and confinement-record ownership refusal — 2026-10-14

Both targets passed all seven `removal::test_ownership_refusal_retry` variants:
`systemd-user-edit`, `gdm-password-link`, `systemd-user-link`, `gdm-hook-link`,
`confinement-record-owner`, `confinement-record-link` and `confinement-record-uid`.
The bare family selector keeps all seven separate baseline attempts in one
retention session per target. Each exact bracketed selector retains six fresh
installation/reboot prerequisites and two continuous recovery phases. All
**112/112 executions** and **56 complete JUnits** passed, without errors or skips.

| Target | Report under `output/test-runs/host/reports/` | Raw allocation under `output/test-runs/privileged/allocations/` |
| --- | --- | --- |
| `onpc-Ubuntu26.04` | `20261015T034922Z-6128ae5c/report.md` | `onpc-system-hulhzl4t` |
| `onpc-Fedora44` | `20261015T034922Z-3764ccaa/report.md` | `onpc-system-k5fn408k` |

Every `evidence/guest/<variant>.xml` records real native package refusal,
preserved foreign inode/metadata/bytes or link text and referent, recovery
records, loaded enforcing confinement, child execution denial and ordinary-user
access. These preflight conflicts leave removal guards absent and protection
intact. The fixture resolves only its recorded conflict, verifies owned
integration again, then keeps a real reboot and successful native removal in
the same attempt. Each `<variant>-retry-rebooted.xml` verifies owned account/home
deletion, exact original PAM bytes/modes/local-versus-vendor disposition and
ordinary-user access; Fedora also restores authselect with SELinux enforcing.
The UID variant changes only the record's `kiosk_uid`, preserving the real account.

Each retained `evidence/result.json` has exactly the 56 expected/executed
identities, 28 collected JUnits, all four outcome domains passed,
`cleanup_phase=complete` and two successful baseline checks. Both VMs were
independently confirmed off. All subagents finished before installed acceptance.
The final audit reread every result, input manifest and JUnit after the queue run.
The queue summary is `output/test-runs/host/allocations/onpc-vm-queue-axnv83b7/results.json`.

Both selected-input manifests have 30 guest and 19 host bindings, covering 47
distinct checkout files, rehashed without mismatch. Their equal SHA-256 is
`04370bd700bcd3fdada7e6eb719b8d6991b9629adf455ef2db5de063dff53c27`.
Package source is revision `8150f34484711049be9edad68107a410a13b2883`, 348 files,
digest `80972bc053b325b9fc7839265afe428a774802afce120a90645c2c3f8e278fac`.
DEB SHA-256 is `0cacd9cc5f37761ec415f9911e17fbea63e57d19b2ae6b65777f2e41b1eb8465`;
RPM SHA-256 is `b949151c319a7cac0ab1df36a08f944ae67845ddf32ecb4c29b2ca1879a1cef2`.
Fixture digest remains `8e053863e1b5326dbd535450b761cf47384045639d8e8bde822fa5f7b3a8c1c5`;
baseline digests remain `5a3aeb6e7c4867e930d534da85060915b634a863137fbe724689dd7e80aafd93`
(Ubuntu) and `fd7774dfe68092ea8e09b8cf00046d32ad6393c06ea9b5cd3edc36f9b6c4db3c` (Fedora).

Affected controller, snapshot, input, dispatch, JUnit, resume, fixture cleanup and
inventory checks passed **1,318/1,318**, report `20261015T034901Z-0d3b148e/report.md`.
Coverage/plan checks passed **123/123** again after close-out, report
`20261015T050338Z-3dcf96a3/report.md`.
Coverage was regenerated. Resource review covers private files and process-local
doubles; the new unit module has an explicit compatible classification. This
task changes tests, their scheduling and documentation, outside package/build
dependencies; no additional `make build` is required. Package inputs were verified
through the maintained builder, with their bytes independently hashed.

The existing ownership guards required no product change for these variants.
A source-only review flagged absent confinement state (`state()` returns `None`
and `remove()` returns) for the existing 4-7/4-8 reviews. These seven present-record
histories make no missing-record safety claim. Changed selected helpers and the
expired 4-5c MAC-unload raw allocations retain the complete 4-5c repeat in 4-10.
Only 4-5d is checked; its brief is removed and the master pointer advances to 4-5e.
Other queue rows and the Phase 4 exit gate retain their scope and status.

### Phase 4 step 5e — Kiosk identity and filesystem ownership refusal — 2026-10-14

Both targets passed all seven exact
`removal::test_identity_filesystem_refusal_retry` variants: `kiosk-marker-uid`,
`home-owner`, `home-link`, `home-mount`, `state-owner`, `state-link` and
`state-mount`. Each retains six fresh-install/reboot prerequisites and two
continuous recovery phases in its own baseline attempt. The family keeps all
seven attempts in one retention session per target. All **112/112 executions**
and **56 complete JUnits** passed, without errors or skips.

| Target | Report under `output/test-runs/host/reports/` | Raw allocation under `output/test-runs/privileged/allocations/` |
| --- | --- | --- |
| `onpc-Ubuntu26.04` | `20261015T052839Z-34aab307/report.md` | `onpc-system-6y3ps1zs` |
| `onpc-Fedora44` | `20261015T052839Z-2bd3ca73/report.md` | `onpc-system-pu77ev1u` |

The native package actions refused each conflict while preserving the foreign
account, root/link/referent or actual same-filesystem bind mount and the
foreign-owned sentinel. Descriptor, inode, ownership, mode, xattr and kernel
mount witnesses guard the fixture's exact resolution. State-owner/link refusals
retain payload, enforcing MAC, effective child denial and unchanged recovery
records without publishing removal guards. Marker/home/state-mount refusals
retain the surviving account, original rollback snapshot and required ownership
records after payload erasure. Both installed PAM account and session callbacks
deny kiosk admission, while ordinary-user controls succeed. Fedora's relevant
SELinux domains remain enforcing.

Each conflict and resolution/retry stays in one attempt. Ubuntu retries its
retained native finalizer after post-erase refusal; Fedora uses normal
`make install`, reboot and native removal. Every final endpoint verifies owned
account/home deletion before exact original PAM bytes, modes and local/vendor
disposition, with ordinary-user access and Fedora authselect restoration.
The existing production guards required no product change for these variants.

Each `evidence/result.json` has exactly 56 expected/executed identities, all 28
JUnits collected, all four outcome domains passed, `cleanup_phase=complete`
and two successful baseline checks. The final audit reread both results,
input manifests and every JUnit, including real mount, durable-denial, rollback
snapshot and final PAM receipts. All subagents finished before installed
acceptance. Owned maintenance and runner cleanup completed; both VMs were
independently confirmed off. The queue summary is
`output/test-runs/host/allocations/onpc-vm-queue-xctlg_u1/results.json`.

Both selected-input manifests have 31 guest and 19 host bindings covering 48
distinct checkout files, rehashed without mismatch. Their equal SHA-256 is
`f7ec623eee16e678db34f33f3f4f5a3f8787f74fdaa54d69e2eb7be6400f93af`.
Package source is revision `8150f34484711049be9edad68107a410a13b2883`, 348 files,
digest `80972bc053b325b9fc7839265afe428a774802afce120a90645c2c3f8e278fac`.
Independently hashed DEB and RPM bytes are respectively
`0cacd9cc5f37761ec415f9911e17fbea63e57d19b2ae6b65777f2e41b1eb8465` and
`b949151c319a7cac0ab1df36a08f944ae67845ddf32ecb4c29b2ca1879a1cef2`.
Verified inputs are `onpc-test-artifacts-v24r5zsu` and
`onpc-test-artifacts-uqe_x1nq` under `output/test-runs/host/allocations/`.
Fixture digest remains `8e053863e1b5326dbd535450b761cf47384045639d8e8bde822fa5f7b3a8c1c5`;
baseline digests remain `5a3aeb6e7c4867e930d534da85060915b634a863137fbe724689dd7e80aafd93`
(Ubuntu) and `fd7774dfe68092ea8e09b8cf00046d32ad6393c06ea9b5cd3edc36f9b6c4db3c` (Fedora).

Affected host checks passed **2,033/2,033**, report
`20261015T053115Z-dc51370b/report.md`. Plan/coverage checks passed **137/137**
after close-out, report `20261015T065644Z-ac4d273b/report.md`.
Coverage was regenerated. New unit work
uses private files and process-local UID, mount, command and VM doubles;
its compatible resource classification was reviewed. These test/documentation
changes do not affect package sources or build dependencies, so no additional
`make build` is required. Changed shared helper/controller inputs leave complete
4-5d repetition with 4-10; no different variant supplies its refusal proof.
Only 4-5e is checked, its temporary brief removed and the master pointer advances
to 4-6. Other queue rows and the Phase 4 exit gate retain their scope and status.

### Phase 4 step 6 — Fedora post-erase recovery — 2026-10-15

`removal::test_rpm_posterase_recovery` passed **8/8** executions on
`onpc-Fedora44`: six fresh-install/reboot prerequisites and the continuous
failed packaged purge, normal reinstall, conflict resolution, reboot and repeated
packaged purge. Report
`output/test-runs/host/reports/20261015T075754Z-faeffb31/report.md` and raw allocation
`output/test-runs/privileged/allocations/onpc-system-axjt6axc/` retain the result.
All four `evidence/guest/rpm-posterase{,-installed,-rebooted,-reinstalled-rebooted}.xml`
files have zero errors, failures or skips. The two
`evidence/guest/attempt-rpm-posterase-installed/gdm-rpm-posterase-{installed,rebooted}.json`
observations passed on distinct boots with the required SELinux role census.

The first packaged purge failed in the real RPM `%postun` callback while the
package and executable payload were erased. The surviving account retained exact
recovery records and distro-PAM account/session denials; ordinary controls passed.
The pinned home self-bind and foreign-owned sentinel survived that refusal and
normal `make install` recovery. A joined observer required exact restored native
policy, extension and rule bytes plus an actual denied child launch while the
durable admission marker remained. Loaded confinement and native gates passed
before the fixture resolved only its recorded mount and sentinel.

The same guest then rebooted and passed the repeated packaged purge. Owned
account/home deletion preceded exact original PAM bytes, modes and local/vendor
disposition; original authselect, ordinary identities/policy/extension settings,
native execution, account admission and prepared-child password authentication
passed. SELinux remained enforcing. The complete successful five-phase removal
regression and the independent 4-5 variants retain their separate scopes.

`evidence/result.json` records all eight exact expected/executed identities,
product/infrastructure/collection/cleanup passed, `cleanup_phase=complete` and
two successful baseline checks. Owned maintenance and runner cleanup completed;
the VM was independently confirmed off. All subagents finished before acceptance.
The raw results, input manifests and every JUnit were reread after execution.

The selected-input SHA-256 is
`ee9d9ccae52b006f316da12cd2b065687a30598768c21c08feea3f50cebaa185`:
31 guest and 19 host bindings cover 48 distinct checkout files, all rehashed
without mismatch. Package source remains revision
`8150f34484711049be9edad68107a410a13b2883`, 348 files, digest
`80972bc053b325b9fc7839265afe428a774802afce120a90645c2c3f8e278fac`.
RPM SHA-256 remains
`b949151c319a7cac0ab1df36a08f944ae67845ddf32ecb4c29b2ca1879a1cef2`;
this run's verified fixture digest is
`7559a7c6ebee0078c29f9dcb2f15c684ad41f52c1df226c82bbdb996ad8c119b`.
Fedora baseline remains
`fd7774dfe68092ea8e09b8cf00046d32ad6393c06ea9b5cd3edc36f9b6c4db3c`.
Earlier fixture/helper bindings are not silently relabelled as this candidate.

Mechanical test repairs preserve the required behavior: DNF can report its own
failed transaction after real post-erase refusal, the empty broker-mask marker
uses its root-owned non-writable-file guard rather than the private-record mode,
and the password probe retains its prepared-child UID guard. Separate live
diagnostics reproduced the native refusal and verified owned unmount with and
without pinned handles; they supply no acceptance credit. An initial busy
unmount during failure unwinding did not recur in the complete accepted history.

Affected host checks passed **2,144/2,144**, report
`output/test-runs/host/reports/20261015T075942Z-04c37a55/report.md`.
Close-out plan/coverage checks passed **137/137**, report
`output/test-runs/host/reports/20261015T081439Z-2cfa3735/report.md`.
Required raw results and manifests remained readable after that final check.
Coverage was regenerated. New host work uses private files and synchronous
command/thread or VM/lease doubles; its compatible resource classifications
were reviewed. Only test/documentation inputs changed, outside package sources
and build-tool dependencies, so no additional `make build` is required.
Only 4-6 is checked and its temporary brief removed; the master advances to 4-7.
The remaining rows and Phase 4 exit gate retain their scope and status.

### Phase 4 step 7 — independent native-boundary review — 2026-10-15

Accepted on both declared targets after the proof repair, affected host checks,
complete installed execution matrices and owned cleanup passed. No additional
product escape was demonstrated. All three scoped reviewers finished and were
joined before installed acceptance; the coordinator owns these conclusions.

The coordinator and two independent read-only Sol High reviewers covered the
original partial fix `3e0f2af6f9c49e9da0df816f08f39b5c2a2b56fc` against
`697a4c3032ff208feccc04eac4ad0ba363864961`, then all subsequent native changes
through `85fea6f188b27bdaeb2a9161274127192bed12e3`, plus this task's final repair.
The unrelated launcher commit `2c5a9a728a4622afdea8a5c50c4d568fb4dc8419`
adds no native/package-source changes in the reviewed scope. The starting checkout was
clean, with no untracked inputs. Complete PAM/preparation/policy/fixed-launcher
functions, their callers and shared state, packaging/PAM integration and the
installed qualifiers were reviewed. The starting 348 package-source inputs
matched the candidate recorded in
[4-5e](#phase-4-step-5e--kiosk-identity-and-filesystem-ownership-refusal--2026-10-14)
and [4-6](#phase-4-step-6--fedora-post-erase-recovery--2026-10-15).

Owned online maintenance recovered exact distro package/source identities,
rather than treating older version banners or missing platform exports as proof:

| Target | Native input | Exact source reviewed |
| --- | --- | --- |
| Ubuntu | GDM `50.1-0ubuntu0.1` | [Applied source `e2f419b82f9aeb9d89bffc7cbb41a70df0f01cb5`](https://git.launchpad.net/ubuntu/+source/gdm3/tree/?id=e2f419b82f9aeb9d89bffc7cbb41a70df0f01cb5) |
| Ubuntu | systemd `259.5-0ubuntu3.4` | [Release source `95caf9c879bc37547b3da875cf332b18d684499f`](https://git.launchpad.net/~ubuntu-core-dev/ubuntu/+source/systemd/tree/?id=95caf9c879bc37547b3da875cf332b18d684499f), including the quilt patch inventory |
| Ubuntu | PAM `1.7.0-5ubuntu3.2` | [Applied source `506b197bc10a9982dd2f0b6227af05c30aa28ff3`](https://git.launchpad.net/ubuntu/+source/pam/tree/?id=506b197bc10a9982dd2f0b6227af05c30aa28ff3) |
| Fedora | GDM `1:50.3-1.fc44` | [Package source `90a5d2a2acdcbe53a40fbb69924effaa1de3f3f2`](https://src.fedoraproject.org/rpms/gdm/tree/90a5d2a2acdcbe53a40fbb69924effaa1de3f3f2), upstream `bb0f6ad980419def9fc6fb817d32ee22a65b0820` |
| Fedora | systemd `259.9-1.fc44` | [Package source `29f902fb5a9fc3d5a5c1de5cfc1075dac7f309ec`](https://src.fedoraproject.org/rpms/systemd/tree/29f902fb5a9fc3d5a5c1de5cfc1075dac7f309ec), upstream `63c0371fa71ae32ba02f05f90658bc40aaa19168` |
| Fedora | PAM `1.7.2-2.fc44` | [Package source `7ba14030d139755c964218afd37b92674fa20df6`](https://src.fedoraproject.org/rpms/pam/tree/7ba14030d139755c964218afd37b92674fa20df6), upstream `fe03a10115c082a8486ccbab7462139d7e4bb067` |

The actual final GDM fork/exec inherits the gate; preference saving remains
best-effort. Exact systemd sources retain parent account/establish/open callbacks,
then the `sd-pam` fork and close/delete/end callbacks. Target lookup follows the
private mount gate; reviewed vendor user-manager units specify no later MAC
override. Ubuntu's PAM include/multiarch and cached-jump differences preserve
the namespace/keyring guards and ordinary-user callbacks. Admission leases,
root handoff, teardown, recursive read-only descriptor-pinned mounts, independent
dentries, library replacement/reexec, fixed role transitions and native-helper
inode/credential checks revealed no additional demonstrated product defect.

Polkit `127` uses upstream `9e4894c969eecf26a3ba762f4f7a268aa0fb3e51`.
Fedora `127-2.fc44.2` matches
[package source `fccf087ae9d5a7d28474494689a8112225982cfc`](https://src.fedoraproject.org/rpms/polkit/tree/fccf087ae9d5a7d28474494689a8112225982cfc).
Ubuntu `127-2ubuntu1.1`'s exact Debian archive was checked against SHA-256
`2f8f11ca818b9726dd8ed9f8979e0a0211edb7b9ee1949b6fb5df697333da73d`;
its complete two-patch series bounds cookie input and rejects an initial NUL.
Neither changes PAM ordering, confinement or cancellation. The helper invokes
authenticate/account/end, without session/namespace/setcred callbacks. The
strict Fedora census still requires its exact mixed credentials, pinned native
inode, private generation/namespace and live confined parent.

Finite downstream review also covered Ubuntu/Fedora bubblewrap
`0.11.1-1ubuntu0.3` / `0.12.0-1.fc44`, WirePlumber
`0.5.13-1ubuntu1` / `0.5.18-1.fc44`, Glycin
`2.1.5+ds-0ubuntu0.2` / `2.1.5-1.fc44`, WebKit
`2.52.6-0ubuntu0.26.04.1` / `2.54.1-1.fc44` and native GStreamer scanner
`1.28.2-1` / `1.28.8-1.fc44`. Ubuntu's extra vendored Glycin Snap patch can
select a direct loader when `SNAP` is nonempty; fixed launchers clear it and
the app/agent/service roles have no direct loader transition. WirePlumber's
trusted custom Lua searcher is not a security sandbox; native module loading
remains subject to the executable-mapping boundary. This review covers the
finite native interfaces, not every optional codec/plugin.

The corresponding immutable downstream package trees are:

| Source | Ubuntu commit | Fedora commit |
| --- | --- | --- |
| bubblewrap | [4442b57f802c6a6199b1c3224295e44c6bb8afa5](https://git.launchpad.net/ubuntu/+source/bubblewrap/tree/?id=4442b57f802c6a6199b1c3224295e44c6bb8afa5) | [31490fc4d0b95d0bc47cac43ae923ea3e0989573](https://src.fedoraproject.org/rpms/bubblewrap/tree/31490fc4d0b95d0bc47cac43ae923ea3e0989573) |
| WirePlumber | [42d6441cdf9f84263bccb29cf2d77747fc556c5a](https://git.launchpad.net/ubuntu/+source/wireplumber/tree/?id=42d6441cdf9f84263bccb29cf2d77747fc556c5a) | [b70cecc5256d6ad2f68569ab8942dd55408f4a71](https://src.fedoraproject.org/rpms/wireplumber/tree/b70cecc5256d6ad2f68569ab8942dd55408f4a71) |
| Glycin | [a2ab4a19993adbe98d5fee70b1602456f9d20b8a](https://git.launchpad.net/ubuntu/+source/glycin/tree/?id=a2ab4a19993adbe98d5fee70b1602456f9d20b8a) | [9076db4478deaf7063d6ad61f85cc024a6b8b9d6](https://src.fedoraproject.org/rpms/glycin/tree/9076db4478deaf7063d6ad61f85cc024a6b8b9d6) |
| WebKit | [37ad2589f9b06939ff0972990057ee80488d8d29](https://git.launchpad.net/ubuntu/+source/webkit2gtk/tree/?id=37ad2589f9b06939ff0972990057ee80488d8d29) | [5faa89c769398768d5e474a0188116e3d5161481](https://src.fedoraproject.org/rpms/webkitgtk/tree/5faa89c769398768d5e474a0188116e3d5161481) |
| GStreamer core | [12662b7e6d0c2af6d4da61543274ea7fc3d6a881](https://git.launchpad.net/ubuntu/+source/gstreamer1.0/tree/?id=12662b7e6d0c2af6d4da61543274ea7fc3d6a881), unpatched import | [a06f0c5e348e73c362290935d731e5066c3b898f](https://src.fedoraproject.org/rpms/gstreamer1/tree/a06f0c5e348e73c362290935d731e5066c3b898f) |
| GStreamer base | [00c396a916bea1dd1a8ca3cefd9869ebe4efa569](https://git.launchpad.net/ubuntu/+source/gst-plugins-base1.0/tree/?id=00c396a916bea1dd1a8ca3cefd9869ebe4efa569) | [c39d522b5c1f3b7856a670ec60432120cb17b60c](https://src.fedoraproject.org/rpms/gstreamer1-plugins-base/tree/c39d522b5c1f3b7856a670ec60432120cb17b60c) |

One demonstrated **harness proof defect**, rather than a demonstrated product
escape, required repair: the six bubblewrap substitution negatives accepted
any nonzero status without the canary token. Native startup/setup failures could
therefore satisfy a negative. The repair preserves all six attacks and controls,
captures the explicit native child identity and bounded native diagnostics, and
requires independently observed enforcement for each attack. Source review
confirmed both exact bubblewrap versions support `--info-fd` and `--as-pid-1`.
Ubuntu now requires exact child/profile/path mount denials for bind/data and
audited `mknod`/create denials for tmpfs-file. Fedora combines the exact native
final-exec error/path with its fresh child-specific enforcing execute AVC and
mode-specific object identity; a missing PATH record is not replaced by a broad
label exception. Both complete six-attack maintenance preflights passed; their
managers stopped, and Ubuntu's temporary audit instrumentation was restored.
Those probes supply no acceptance credit. The complete installed execution
matrices below passed against the final candidate.

The final affected host selection passed **532/532**, report
`output/test-runs/host/reports/20261015T155512Z-d48c111b/report.md`, with a verified
identical retained export at
`output/test-runs/host/exports/onpc-artifact-export-2cr_cbmy/report.md`.
The new regressions use private fixtures, bounded pipes and process-local mocks;
the existing compatible resource classifications remain applicable. The repair
adds auditing to the two existing AppArmor protected-code write denials,
preserving their denied permissions. `make build` passed after that final policy
edit, producing both package formats. Coverage was regenerated with the 78
additional parameterized checks.

Final execution-plan/coverage metadata checks passed **125/125**, report
`output/test-runs/host/reports/20261015T155346Z-4ba04db9/report.md`.
All 102 links in the four changed Markdown documents resolve, and
`git diff --check` passed. Unrelated launcher edits remain outside this task.

The maintained `enforcement::test_kiosk_execution_confinement` selection passed
on both targets in one dual-target invocation. Each retained JUnit contains the
one expected case with no failures, errors or skips. Both raw results report
product, infrastructure, collection and cleanup passed, two successful baseline
checks, no qualification failure and `cleanup_phase=complete`:

| Target | Retained report | Complete raw allocation | Verified package SHA-256 |
| --- | --- | --- | --- |
| `onpc-Ubuntu26.04` | `output/test-runs/host/reports/20261015T154132Z-fc4368ee/report.md` | `output/test-runs/privileged/allocations/onpc-system-h1cymw8j` | `a48ac2797a5ad44915de0611f0a168f4e4e351f6d59d093375bf0a13f987ec09` |
| `onpc-Fedora44` | `output/test-runs/host/reports/20261015T154132Z-8897d45a/report.md` | `output/test-runs/privileged/allocations/onpc-system-qbf_mmdr` | `9008b021eab03778e71eae6140bda33cc795590d9959703b61ce97053c6a56d8` |

Each allocation retains `evidence/result.json`, `evidence/guest/enforcement.xml`
and `input/selected-inputs.json`. The queue result is
`output/test-runs/host/allocations/onpc-vm-queue-l2py9ljo/results.json`.
Prepared inputs are retained at host allocations `onpc-test-artifacts-x2_2a9cc`
(Ubuntu) and `onpc-test-artifacts-ewz5nvmd` (Fedora). Both packages bind the same
348-file source digest
`d295c7258e1060afc0d0996510e1637c37167652edc54be1c411490795f758ef`
(package-source revision `8150f34484711049be9edad68107a410a13b2883`, with the
final audit-policy bytes included), fixture
`7559a7c6ebee0078c29f9dcb2f15c684ad41f52c1df226c82bbdb996ad8c119b`
and selected-input digest
`f6031f5ffd6c1e816e239d44d786a6968defaa0958b53e3540b07c864c41c720`.
All 27 guest bindings (25 distinct checkout files) and both package hashes were
independently compared with the current inputs. Target baseline provenance is
Ubuntu `5a3aeb6e7c4867e930d534da85060915b634a863137fbe724689dd7e80aafd93`
and Fedora `fd7774dfe68092ea8e09b8cf00046d32ad6393c06ea9b5cd3edc36f9b6c4db3c`.

The retained native inventories contain 29 package/47 file identities on Ubuntu
and 30 package/49 file identities on Fedora, including the versioned systemd
libraries. They match the reviewed distro sources above. All six substitution
negatives per target retain their separate untruncated native diagnostics and
fresh matching child-specific enforcement events. Allowed native and canary
controls passed first. The matrices also passed all nine final-exec denials,
native credential establish/close/delete/end and post-parent-exit denials,
private executable/library/plugin replacement and reexec, stale-manager refusal,
vendor drift and missing/stale/unenforced-policy refusal/recovery. Fedora AVCs
remain enforcing; Ubuntu's effective unit override assertions passed.

Manual maintenance sessions completed serial baseline restoration before the
formal runs. Formal cleanup completed on both targets, and independent final
status reads confirmed both powered off. Raw results, manifests and JUnits were
rechecked through the maintained artifact reader after acceptance. Only 4-7 is
checked and its temporary brief removed; the master advances to 4-8. The ledger
below preserves the other affected complete histories for 4-9/4-10; this native
matrix does not replace platform/shared-namespace, real-session census or public
kiosk journey acceptance.

### Phase 4 step 8 — independent lifecycle/security review — 2026-10-15

**Unfinished; no acceptance credit on either target.** Three independent
read-only Sol High reviewers completed lifecycle/ownership, executable/API/UI
surfaces and harness/evidence slices. The coordinator assessed their findings
and rechecked retained native results. All reviewers finished and were joined;
none edited files, allocated resources or operated a VM. The two required
repairs below are explicit prerequisites 4-8a and 4-8b immediately before the
unfinished consumer 4-8. No existing row was completed, reordered or reduced.

Review covered original partial fix
`3e0f2af6f9c49e9da0df816f08f39b5c2a2b56fc` against
`697a4c3032ff208feccc04eac4ad0ba363864961`, then all relevant subsequent
confinement changes through `f250b7dac421df530d9b258674cfb974d81e7e39`.
The initial checkout was clean, without untracked files. Complete affected
functions, callers and shared state were reviewed across package dependencies,
source/activation manifests, both distro lifecycle renderings, account/cache
transactions, confinement removal/finalization ownership, fixed launchers,
service/API boundaries, exposed kiosk screens and their engineering qualifiers.
The earlier [4-7 slice](#phase-4-step-7--independent-native-boundary-review--2026-10-15)
retains exact downstream source/native lifetime analysis; this review adds the
remaining lifecycle, surface, collateral and proof-quality analysis.

**Finding L1 — first-configuration protection ordering.** Shared
[`postinst`](../packaging/lifecycle/postinst.in) deletes the owned kiosk password
(line 106) and provisions visible/routed AccountsService state (108) before
shared PAM enablement (160) and final confinement integration (237). A pause or
failure in that interval retains an empty-password account without the product
admission/execution guards. Preinst migration/first-install markers constrain
broker activation; account validation is read-only. Display-manager ordering
does not constrain an already-running GDM. This ordering predates the original
partial fix and remains unresolved in both distro renderings.

The exact Ubuntu GDM
[PAM stack](https://git.launchpad.net/ubuntu/+source/gdm3/plain/debian/gdm3.gdm-password.pam?id=e2f419b82f9aeb9d89bffc7cbb41a70df0f01cb5)
and [worker](https://git.launchpad.net/ubuntu/+source/gdm3/plain/daemon/gdm-session-worker.c?id=e2f419b82f9aeb9d89bffc7cbb41a70df0f01cb5)
do not enforce the account's nologin shell; local authentication does not set
`PAM_DISALLOW_NULL_AUTHTOK`. The reviewed Ubuntu PAM
[Unix profile](https://git.launchpad.net/ubuntu/+source/pam/plain/debian/pam-configs/unix?id=506b197bc10a9982dd2f0b6227af05c30aa28ff3)
enables `nullok`; `pam_nologin` checks system shutdown files rather than the
account shell. Fedora's reviewed GDM
[PAM stack](https://raw.githubusercontent.com/GNOME/gdm/bb0f6ad980419def9fc6fb817d32ee22a65b0820/data/pam-redhat/gdm-password.pam)
uses `password-auth` without a shell gate; Authselect's
[profile](https://raw.githubusercontent.com/authselect/authselect/1.6.0/profiles/sssd/password-auth)
enables `nullok` unless disabled, a state the product preflight rejects.
These sources establish unsafe configuration ordering, **not a measured
successful graphical escape**. No live vulnerable-interval login was attempted.

Return condition: 4-8a establishes protection before account usability, handles
already-owned passwordless retries and passes a maintained fresh-install/
interruption/retry/reboot history on **both** targets, with native denial proof,
successful dedicated execution after recovery and ordinary-account controls.
Initial setup runs as kiosk through `runuser`; moving shared PAM activation
earlier without resolving that dependency would break setup. No particular
transaction implementation is accepted by this review in advance.

**Finding H1 — eleven generic-status negatives lack enforcement proof.**
[`verify_user_inputs`](../tests/integration/system_kiosk_confinement.py)
accepts status `203` for two copied-executable/interpreter-alias attacks (1201)
and the writable `ExecStart=+` unit (1220); `verify` does the same for six
manager commands (1616).
[`verify_service_api`](../tests/integration/system_kiosk_platform.py)
accepts `203`/`229`/`231` for two profile/context attacks (354). A successful
earlier native command establishes manager/API availability, but missing
targets/loaders or case-specific setup failures can also produce these statuses.
Inventory hashes establish file identity, not why a particular attack failed.
None of these eleven assertions requires its own explicit native error and
independently correlated enforcing-boundary observation. This is a demonstrated
**harness proof defect**, not a demonstrated product escape.

Return condition: 4-8b preserves all eleven attacks and controls, uses shared
identity-bound native/error/kernel observation mechanics, and passes the complete
registered `enforcement::test_kiosk_execution_confinement` and
`enforcement::test_kiosk_platform_integrations` selectors on **both** targets.
Missing or inconclusive witnesses must fail. The 4-7 bubblewrap repair already
requires its successful controls, exact child identity, native diagnostic and
fresh enforcing events; H1 does not discard those independently proved results.

The two review slices reconcile against the five scoped groups as follows:

| Scoped group | Reviewed boundary and remaining acceptance |
| --- | --- |
| 1 — Dedicated admission/account ownership | 4-7 covers native routing, leases and final execution; 4-8 covers account/cache recovery and lifecycle callers. L1 keeps first configuration open. Final admission and real-session proof on both targets remains with 4-9/4-10. |
| 2 — Actual execution and APIs | Native/PAM/MAC/namespace lifetime review combines with fixed argv/environment/import/plugin/loader, writable user-unit, command-prefix, broker/D-Bus/systemd and native service review. H1 keeps eleven negative proofs open until 4-8b. Final platform/shared-integration/census obligations remain unchanged. |
| 3 — Essential flows and exposed surfaces | Request/authentication/exit, About/Help suppression, Preferences/nested dialogs, release notes, error reporting/privacy/editor navigation, WebKit/Glycin/scanner, Polkit, notification and Wellbeing roles were reviewed. No additional demonstrated escape was found. Per-target public journeys and real role/scanner evidence still require exact applicability/retention reconciliation in 4-9 and missing/affected repeats in 4-10. |
| 4 — Safe lifecycle | Both package formats, activation/reboot classification, durable payload-erasure denials, policy-before-PAM rollback, exact restoration after owned deletion and account/home/cache ownership were reviewed. No additional demonstrated removal/recovery defect was found; L1 requires 4-8a. Every existing invalidated continuous lifecycle/recovery history stays required. |
| 5 — Independent review and ordinary accounts | All three reviewers completed; shared PAM/units/environment preservation, AccountsService metadata, fixture isolation, identity/cleanup ownership, positive controls, frozen provenance and raw evidence were assessed. Ordinary login/desktop/metadata/shared-integration proof remains separate from kiosk negatives. Both findings prevent review acceptance; source review supplies no missing installed or public result. |

Retained predecessor evidence was rechecked through the maintained artifact
reader without exports or journal rotation. Both 4-7 allocations
`onpc-system-h1cymw8j` (Ubuntu) and `onpc-system-qbf_mmdr` (Fedora), under
`output/test-runs/privileged/allocations/`, retain `evidence/result.json`,
`evidence/guest/enforcement.xml` and `input/selected-inputs.json`. Each complete
JUnit names the one expected execution case, with zero failures/errors/skips;
both result records report product/infrastructure/collection/cleanup passed and
`cleanup_phase=complete`. Both selected manifests match; all 27 bindings
(25 distinct checkout paths) were directly hash-compared with current files.
The prepared package bytes at host allocations `onpc-test-artifacts-x2_2a9cc`
and `onpc-test-artifacts-ewz5nvmd` match the exact SHA-256 values recorded in
[4-7](#phase-4-step-7--independent-native-boundary-review--2026-10-15).
Their manifests and raw results agree on the recorded 348-file package-source
digest, fixture and target-specific baseline identities. No product, helper,
fixture or package input was changed by this review. This verifies retained
historical outcomes and input bindings; H1 still prevents reuse of the nine
generic-status manager assertions as independently proved denials. Current/final
baseline and full-history applicability remain explicit 4-9 obligations.

Maintained list-only inspection confirmed the four current `package` selectors
and both affected `enforcement` selectors. No registered package selector
observes the newly identified interrupted first-configuration interval; 4-8a
must implement and register that history. The existing evidence ledger retains
all expired/invalidated activation, complete removal, rollback, finalization,
PAM/record, identity/filesystem and Fedora post-erase histories. No new blanket
installed/E2E batch was run and no existing gap was removed.

Blocker: L1 and H1 require the declared prerequisite repairs and their installed
acceptance; resume 4-8 after **4-8a and 4-8b pass on both targets**, then review
their changes and consolidate affected evidence decisions. This is authorized
prerequisite work, not a developer behavior/access decision. All owned work here
was read-only except the task/reference/queue documents. No guest was started or
mutated, no process or VM lease was acquired, and independent maintained status
reads confirmed both targets powered off. Owned cleanup is complete. The 4-8
brief and unchecked row remain; the sole master pointer moves to 4-8a.

## Phase 4 step 8a — First-configuration protection — 2026-10-15

Resolved [L1](#phase-4-step-8--independent-lifecyclesecurity-review--2026-10-15)
through native account expiry. Fresh accounts are created expired; reconfiguration
quarantines an owned account before other configure work. A private, durable,
UID-bound record preserves its original expiry across interruption and retry.
Configuration restores that expiry only after shared PAM verification and final
confinement integration. Initial home setup drops identity directly with
`setpriv`; it does not require opening the restricted PAM admission route.
Removal validates and retains the journal until verified owned account/home
deletion. Foreign identities, unsafe journals and unrelated expiry changes refuse.
The owning behavior is in [Lifecycle](SystemDesign/Lifecycle.md#startup-login-and-update-lifecycle)
and [Package removal](SystemDesign/Package-Removal.md#pam-and-kiosk-ownership).

Live retry diagnosis also found that RPM reinstallation could replace the original
activation comparison with the already-unpacked candidate and lose the required
first-install reboot. Pre-installation now durably retains the original manifest
or its deliberate absence until successful configuration consumes it. A retained
first-install marker remains authoritative; substituted bookkeeping paths refuse
before mutation. Later completed unchanged reinstalls retain their existing
behavior under the [activation owner](Publishing.md#activation-levels).

The maintained `package::test_first_configuration_interruption_retry` history
now owns a separate product-free baseline attempt, exact frozen format-specific
inputs, `first-configure` and `first-configure-rebooted`, whole-history resume,
failure stopping and a real reboot. Owned read-only GDM-directory and exact
policy-loader faults reach both incomplete-configuration intervals. Ubuntu's
first-interval fixture defers only automatic default-profile activation through
native public flags; explicit product activation remains intact. Payload installs
and RPM retries use `make install`; DEB retry finishes the verified already-unpacked
half-configured payload through native `dpkg --configure`.

Both complete installed histories passed, two expected/executed cases per target,
with each raw JUnit reporting one test and zero failures, errors or skips:

| Target | Raw allocation under `output/test-runs/privileged/allocations/` | Host report under `output/test-runs/host/reports/` | Package SHA-256 | Baseline provenance SHA-256 |
| --- | --- | --- | --- | --- |
| onpc-Ubuntu26.04 | `onpc-system-gpmzey9c` | `20261015T172839Z-d0a557b5/report.md` | `e79ce75a5fa7a8b596e7b7c7789f2f7d04846c5fe4020b107cfb1675f8a0774d` | `5a3aeb6e7c4867e930d534da85060915b634a863137fbe724689dd7e80aafd93` |
| onpc-Fedora44 | `onpc-system-22di3qrn` | `20261015T172839Z-2ad5b654/report.md` | `89e6bb8c462922fa6a99e18ab65ff3df21e55a7e66580de94fa488c59ca327d6` | `fd7774dfe68092ea8e09b8cf00046d32ad6393c06ea9b5cd3edc36f9b6c4db3c` |

Each allocation retains `evidence/result.json`, `input/artifact-manifest.json`,
`input/selected-inputs.json`, installed-file/input records and complete
`guest-results/attempt-first-configure/{first-configure.xml,first-configure-rebooted.xml}`
with command streams, exact fault witnesses and the continuity state. Both bind
package-source SHA-256
`9454f190377353cf7e299b5c0a2c1bad0a971dad8942d70ddee50f1cf51656e4`
(348 unique files, revision `f250b7dac421df530d9b258674cfb974d81e7e39`),
selected-helper SHA-256
`c195fea32a23cc798b80c7d27772a01922d1b273a35373e7836d29c890090d90`
(31 frozen files), and fixture SHA-256
`7559a7c6ebee0078c29f9dcb2f15c684ad41f52c1df226c82bbdb996ad8c119b`.
Both selected-input manifests are identical, and every frozen source-file hash
was compared with the final checkout. Runner source/package/fixture verification
passed, and retained package bytes were independently hashed. Subsequent close-out
documentation is outside the package-source map.

Native results establish empty-token authentication success independently from
account refusal: Ubuntu account status 7 throughout incomplete configuration;
Fedora status 13 before shared activation, then 6 for GDM/login/SSH and 13 for
`systemd-user` before final confinement. Both ordinary roles passed the same
native boundary before negatives. Each interval retained expiry day 1 and the
exact private UID journal, and a real manager-start attempt left `MainPID=0`.
Final retry and reboot admitted the dedicated route, preserved account/home/cache
identity and passed native enforcing execution plus both ordinary roles' shared
PAM/namespace/manager/policy controls. Only the already established native
AccountsService cache-mode and broker state-directory group normalization were
accepted; cache bytes/owner/group/xattrs and marker inode/root/private mode/bytes
remained exact. Fedora stayed globally and per-domain enforcing; the reboot
endpoint reuses the continuously enforcing execution portion of the shared matrix,
preserving the standalone matrix's separate policy-loss faults. Six independent
native replacement denials per target retain AppArmor/SELinux kernel witnesses.
Generic manager-status negatives supply no new H1 credit; 4-8b remains open.

Scoped host regressions passed with retained reports:

- `output/test-runs/host/exports/onpc-artifact-export-gj6rley5/report.md`:
  1,698 cases, including unchanged provision/quarantine and mount-fault mechanics.
- `output/test-runs/host/exports/onpc-artifact-export-o4j31ihv/report.md`:
  648 cases after final product edits, including configuration, activation,
  removal and packaging; later helper changes are covered below.
- `output/test-runs/host/exports/onpc-artifact-export-xfkxkjjn/report.md`:
  149 first-configuration/account-metadata cases after the native cache-oracle repair.
- `output/test-runs/host/reports/20261015T172619Z-f6289a56/report.md`:
  1,668 cases after the final helper split, covering the first-configuration helper,
  runner, snapshots, confinement and ordinary scope.

`make build` passed after the final package-affecting edit, producing both formats
(`output/deb/`, `output/rpm/build.log`). Resource review classifies the added unit
fixtures as private process-local work with bounded waited children; they do not
change host accounts, mounts, services, VM state or shared caches. `git diff --check`
and changed-Markdown link checks passed. All workers joined and owned maintenance
probes stopped before acceptance. Both installed results report passed product,
infrastructure, collection and cleanup, `cleanup_phase=complete`, and two baseline
verification calls with zero failures. Fault restorations and runner restoration
finished; no task-owned VM, mount or process remains running.

This result covers the newly required first-configuration history. It does not
replace the complete five-phase removal chain or the other focused recovery
histories. Account creation/quarantine/setup, activation-origin handling,
journal-aware removal and selected PAM/fault/controller helpers changed. Earlier
activation/GDM, successful removal, rollback, finalization, ownership and Fedora
post-erase results therefore retain their existing complete-repeat obligations
in 4-10 under 4-9's applicability gate. The historical 4-7 package/helper inputs
also no longer match; 4-8b must pass its complete affected execution/platform
selectors, and 4-10 retains final matrix/census qualification. Task 4-8 remains
unchecked for its resumed independent review.

## Validation allocation and evidence ledger

This section allocates remaining confinement validation. The
[test-maintenance contract](../tests/README.md#all-established-regressions)
owns launcher selection, and [retention](../tests/README.md#aggregate-output-retention)
owns evidence lifetime. Keep detailed results and identities in their existing
qualification sections and runner artifacts; this ledger links them once rather
than copying hashes or creating another task queue.

### Remaining validation allocation

| Owner | Required validation | Reuse and duplication boundary |
| --- | --- | --- |
| 4-5b | Implement and qualify focused native rollback/retry histories on both targets, including the controller contract below. | Reuse applicable successful lifecycle evidence; do not make the five-phase removal regression or unrelated public kiosk cases the automatic wrapper for each new fault. |
| 4-5c | Three focused interruption histories qualified on both targets in [4-5c](#phase-4-step-5c--interrupted-finalization-and-durable-admission-barriers--2026-10-14). | Reuse only verified matching retained complete histories; this does not close ownership or repeated-purge coverage. |
| 4-5d | Seven focused PAM/link/confinement-record ownership histories qualified on both targets in [4-5d](#phase-4-step-5d--pam-and-confinement-record-ownership-refusal--2026-10-14). | Reuse only verified matching complete histories; final applicability remains with 4-9 and affected repeats with 4-10. |
| 4-5e | Seven focused identity/home/state-root ownership histories qualified on both targets in [4-5e](#phase-4-step-5e--kiosk-identity-and-filesystem-ownership-refusal--2026-10-14). | Reuse only verified matching complete histories; final applicability remains with 4-9 and affected repeats with 4-10. |
| 4-6 | Complete Fedora native failed-post-erase/reinstall/conflict/reboot/repeated-purge chain qualified in [4-6](#phase-4-step-6--fedora-post-erase-recovery--2026-10-15). | Reuse only the verified matching complete history; 4-9 checks final applicability and 4-10 retains affected repeats. Independent 4-5 variants are not replaced by this history. |
| 4-7–4-8 | Independent reviews and affected host/installed validation for demonstrated fixes. | Review-only changes need no automatic installed/E2E batch. Validate fixes before accepting the review; record other invalidated histories for 4-10. |
| 4-8a | First-configuration protection and complete interrupted-install/retry/reboot histories passed on both targets in [4-8a](#phase-4-step-8a--first-configuration-protection--2026-10-15). | Exact matching raw inputs, native admission/execution, ordinary controls and cleanup verified. Existing invalidated complete-history repeats remain with 4-9/4-10; this new history replaces none of them. |
| 4-8b | Repair eleven manager/service API negative proofs and pass both complete affected execution/platform selectors on both targets. | New prerequisite from [H1](#phase-4-step-8--independent-lifecyclesecurity-review--2026-10-15); retained generic statuses supply no enforcing-boundary proof. Keep independently witnessed native/bubblewrap results within their exact scope; 4-8 reviews the accepted repair before closing. |
| 4-9 | Final affected host/build checks, exact input preparation and evidence applicability/retention reconciliation. | Reuse unchanged valid task-local host results where their exact scope and inputs cover the final candidate; run missing/affected checks. No blanket schema or VM/E2E run. |
| 4-10 | Final execution/admission/namespace/platform qualification, strict waiting-session census, affected public kiosk histories and every invalidated in-scope complete history on both targets. | Keep this final gate. Choose a covering registered route once: the shared-integration selector already includes the complete namespace qualifier, so a second standalone namespace run adds no coverage when that result applies. |
| 4-12 | Reconcile all five groups, both reviews, raw evidence and completed cleanup. | No unchanged live rerun merely for close-out; missing/invalid required evidence needs the affected complete history. |

For each selected task, identify changed product/helper/fixture/baseline inputs
and the assertions they affect before launching tests. Group exact affected host
selectors in one supported invocation after the final relevant edit. Additional
edits or failures can require another check; task boundaries alone do not.
Run `make build` after package-affecting edits under the repository build contract.
Prepare and verify inputs before live acceptance where possible and reuse matching
inputs/snapshots only through maintained guards. Preparation is not acceptance.
Use both-target scheduling where supported and the existing serial Preferences
exception. Keep separate attempts, evidence and cleanup for each target/history.

### Focused recovery controller deliverable

The current registered `removal::test_remove_reboot_reinstall` selector has six
installation/reboot prerequisite executions and five continuous removal phases.
It now includes 4-5a's held-admission refusal. Preserve that selector's complete
assertions, phase order, failure stopping and ordinary-user controls. Do not add
every new fault to its unconditional path merely to obtain installed acceptance.

The initial focused selector `removal::test_aborted_cleanup_rollback_retry` is
registered and qualified in [4-5b](#phase-4-step-5b--aborted-cleanup-and-rollback--2026-10-14).
Its explicit history metadata owns six package prerequisites and the `rollback`
and `rollback-rearmed-rebooted` recovery phases. It starts from the product-free
baseline to preserve the independent pre-installation PAM oracle; app-snapshot and
previous-package starts refuse. Broad selections isolate it in a separate attempt,
and resume replays its complete unfinished history.
Task 4-5c registers `test_interrupted_finalization_retry` with the exact variants
`denial-publication`, `mac-unload` and `account-finalization`. Each has separate
baseline package phases and two recovery phases, with a real reboot before its
owned retry endpoint. All three are qualified on both targets in
[4-5c](#phase-4-step-5c--interrupted-finalization-and-durable-admission-barriers--2026-10-14).
Task 4-5d registers `test_ownership_refusal_retry` and its seven exact bracketed
variants, qualified on both targets in
[4-5d](#phase-4-step-5d--pam-and-confinement-record-ownership-refusal--2026-10-14).
The bare family selects 56 exact executions in seven separate baseline attempts
within one retention session. Resume replays each unfinished complete history.
Task 4-5e registers `test_identity_filesystem_refusal_retry` and its seven exact
bracketed variants, qualified on both targets in
[4-5e](#phase-4-step-5e--kiosk-identity-and-filesystem-ownership-refusal--2026-10-14).
Its bare family likewise selects 56 exact executions in seven separate baseline
attempts within one retention session, with complete unfinished-history replay.
Task 4-6 registers Fedora-only `test_rpm_posterase_recovery`, with six baseline
package prerequisites and the continuous `rpm-posterase` and
`rpm-posterase-reinstalled-rebooted` phases, qualified in
[4-6](#phase-4-step-6--fedora-post-erase-recovery--2026-10-15). Explicit selection
on another package format refuses before VM work; broad selections omit it there.
Extend `case_phases`,
prerequisite closure, snapshot grouping, dispatch and `resume_selection` together,
using shared mechanics rather than another runner or an enforcement-area shortcut.

Before using the new route, cover exact listing/selection and prerequisite closure,
frozen source inputs, verified starting state, guest/controller dispatch, timeouts,
continuous execution, failure stopping, replay/resume, JUnit/result identities and
owned cleanup in the affected runner/snapshot host regressions. Qualify the initial
installed rollback history on both targets through that same maintained route.
Later tasks extend these contracts only for their additional histories.

A verified installed snapshot may supply a focused history's initial state only
when fresh installation/reboot is not the assertion under test. Every variant
keeps its allowed controls, real native callback/fault, independently observed
protection, foreign-state preservation, restoration before guard release and
successful owned retry/finalization in one attempt. Retain exact original PAM
restoration after owned-account deletion and relevant ordinary-user controls.
Do not splice prior passes into a state-changing history or skip its predecessors
on resume. The Fedora post-erase chain remains indivisible. Diagnostics such as
`exercise-live-refusals` supply no acceptance. If the focused route is unavailable,
keep its implementation/acceptance open; an unregistered command is not a shortcut.

### Evidence applicability ledger

The entries below identify recorded evidence candidates, **not newly verified
reuse**. Their linked sections own package/source/helper/fixture/baseline identities
and raw result locations. At each task's close-out update only affected entries
with verified raw paths, exact applicable identities, covered assertions and cleanup,
or a concrete invalidation/missing-evidence reason plus the required follow-up owner.
Use `execution pending` for unqualified new histories, and `reuse verified`,
`verification pending` or `repeat required` for recorded results. A checked queue
row alone never establishes current applicability. Keep per-target decisions explicit.

| Assertion scope | Target | Recorded evidence | Current reuse decision / follow-up owner |
| --- | --- | --- | --- |
| Fresh activation/reboot, account classification, native boundary and GDM readiness | Ubuntu | Historical [4-5e prerequisites](#phase-4-step-5e--kiosk-identity-and-filesystem-ownership-refusal--2026-10-14), covering the corresponding earlier activation assertions | Repeat required in 4-10: 4-7 changed package policy and the selected native helper; 4-6 also changed selected controller/fixture inputs. The retained 4-5e prerequisites passed for their historical candidate. 4-9 maps complete matching activation/GDM prerequisite coverage; the 4-7 standalone matrix supplies no fresh-install/reboot history. |
| Fresh activation/reboot, account classification, native boundary and GDM readiness | Fedora | Historical [4-6 prerequisites](#phase-4-step-6--fedora-post-erase-recovery--2026-10-15), covering the corresponding earlier activation assertions | Repeat required in 4-10: 4-7 changed package policy and the selected native helper. The retained six prerequisites, GDM observations and cleanup passed with enforcing SELinux for the 4-6 candidate. 4-9 maps complete matching activation/GDM prerequisite coverage; the 4-7 standalone matrix supplies no fresh-install/reboot history. |
| Complete successful removal/reinstall/purge, exact PAM restoration and held-admission refusal | Ubuntu | Historical [4-5a](#phase-4-step-5a--in-flight-admission-refusal--2026-10-14), superseding [4-3](#phase-4-step-3--ubuntu-removal-history--2026-10-14) | Repeat required in 4-10: selected helper/controller inputs changed and 4-5a raw allocation expired. No full-history reuse or replacement by focused rollback evidence. 4-9 retains this follow-up. |
| Complete successful removal/reinstall/purge, exact PAM/authselect restoration and held-admission refusal | Fedora | Historical [4-5a](#phase-4-step-5a--in-flight-admission-refusal--2026-10-14), superseding [4-4](#phase-4-step-4--fedora-removal-history--2026-10-14) | Repeat required in 4-10: selected helper/controller inputs changed and 4-5a raw allocation expired. No full-history reuse or replacement by focused rollback evidence. 4-9 retains this follow-up. |
| First-configuration protection before account usability, interruption and owned retry/reboot | Ubuntu | [4-8a](#phase-4-step-8a--first-configuration-protection--2026-10-15), raw `onpc-system-gpmzey9c` | Reuse verified for the recorded candidate: both complete phases, exact package/source/helper/fixture/baseline inputs, independent native admission/execution, identity/ordinary controls and cleanup passed. 4-8 reviews the repair; 4-9 checks final applicability. |
| First-configuration protection before account usability, interruption and owned retry/reboot | Fedora | [4-8a](#phase-4-step-8a--first-configuration-protection--2026-10-15), raw `onpc-system-22di3qrn` | Reuse verified for the recorded candidate: both complete phases and all exact inputs, native admission/execution, identity/ordinary controls and cleanup passed with SELinux enforcing throughout. 4-8 reviews the repair; 4-9 checks final applicability. |
| Independent native review, execution/credential/bootstrap substitution matrix and drift refusal/recovery | Ubuntu | [4-7](#phase-4-step-7--independent-native-boundary-review--2026-10-15), raw `onpc-system-h1cymw8j` | Historical exact inputs, complete expected JUnit, native inventory, six direct enforcement witnesses and outcome/cleanup checks were reverified in 4-8. Repeat required: 4-8a changed the package and selected shared PAM/execution helpers, so those inputs no longer match. H1 still leaves nine manager negatives and two platform profile negatives unproven; 4-8b must repair/pass both complete affected selectors. 4-9 checks final applicability; 4-10 retains its final gate. |
| Independent native review, execution/credential/bootstrap substitution matrix and drift refusal/recovery | Fedora | [4-7](#phase-4-step-7--independent-native-boundary-review--2026-10-15), raw `onpc-system-qbf_mmdr` | Historical exact inputs, complete expected JUnit, native inventory, six direct enforcing AVC witnesses and outcome/cleanup checks were reverified in 4-8. Repeat required: 4-8a changed the package and selected shared PAM/execution helpers, so those inputs no longer match. H1 still leaves nine manager negatives and two platform profile negatives unproven; 4-8b must repair/pass both complete affected selectors with enforcing SELinux. 4-9 checks final applicability; 4-10 retains its final gate. |
| Execution/admission/platform, namespace/shared-PAM scope and ordinary metadata/desktop controls | Ubuntu and Fedora, separately | Historical [Phase 3 qualifications](#qualification-and-reusable-evidence), including the complete [shared-integration/namespace result](#step-8c-qualification--2026-10-13) | Repeat required for missing/invalidated scope in 4-10: the six Phase 3 execution/platform/shared raw allocations and both platform exports are absent. The incomplete Ubuntu shared JUnit export lacked complete input/native provenance and also expired under bounded export rotation. The current 4-7 matrix covers only its named native assertions; 4-9 maps uncovered admission/platform/shared/ordinary controls and 4-10 retains its final matrix/census gate. |
| Approved/denied/cancelled kiosk journeys and About/Preferences/error-report/service restrictions | Ubuntu and Fedora, separately | [6a](#step-6a-qualification--2026-10-13), [6b](#step-6b-qualification--2026-10-13), [6c](#step-6c-qualification--2026-10-13), [7a](#step-7a-qualification--2026-10-13), [7b](#step-7b-qualification--2026-10-13), [7c](#step-7c-qualification--2026-10-13) | Verification pending per target/journey; only affected, invalidated or missing proof runs again at its required owner, including 4-10. |
| Native aborted cleanup, guarded enforcement restoration and owned reboot/retry/finalization | Ubuntu | Historical [4-5b](#phase-4-step-5b--aborted-cleanup-and-rollback--2026-10-14) | Repeat required in 4-10: package configure and selected helper inputs changed, and the 4-5b raw allocation expired. No complete 4-5b reuse is claimed from another fault variant. 4-9 retains this follow-up. |
| Native aborted cleanup, guarded enforcement restoration and owned reboot/retry/finalization | Fedora | Historical [4-5b](#phase-4-step-5b--aborted-cleanup-and-rollback--2026-10-14) | Repeat required in 4-10: package configure and selected helper inputs changed, and the 4-5b raw allocation expired. No complete 4-5b reuse is claimed from another fault variant. 4-9 retains this follow-up. |
| Interrupted publication/MAC unload/account finalization, payload-erased account/session denials and owned reboot/retry | Ubuntu | Historical [4-5c](#phase-4-step-5c--interrupted-finalization-and-durable-admission-barriers--2026-10-14) | Repeat required in 4-10: selected helper/controller inputs changed and the MAC-unload raw allocation expired. Preserve all three complete histories and their assertions; 4-9 retains this follow-up. |
| Interrupted publication/MAC unload/account finalization, payload-erased account/session denials and owned reboot/retry | Fedora | Historical [4-5c](#phase-4-step-5c--interrupted-finalization-and-durable-admission-barriers--2026-10-14) | Repeat required in 4-10: selected helper/controller inputs changed and the MAC-unload raw allocation expired. Preserve all three complete histories and their enforcing-SELinux assertions; 4-9 retains this follow-up. |
| PAM/link/confinement-record ownership refusal, preservation and resolved reboot/retry/finalization | Ubuntu | Historical [4-5d](#phase-4-step-5d--pam-and-confinement-record-ownership-refusal--2026-10-14) | Repeat required in 4-10: selected shared helper/controller inputs changed in 4-5e. Preserve all seven complete histories; no identity/root variant replaces their refusal proof. 4-9 retains this follow-up. |
| PAM/link/confinement-record ownership refusal, preservation and resolved reboot/retry/finalization | Fedora | Historical [4-5d](#phase-4-step-5d--pam-and-confinement-record-ownership-refusal--2026-10-14) | Repeat required in 4-10: selected shared helper/controller inputs changed in 4-5e. Preserve all seven complete histories and enforcing SELinux; no identity/root variant replaces their refusal proof. 4-9 retains this follow-up. |
| Kiosk identity/home/state-root ownership refusal, preservation and resolved reboot/retry/finalization | Ubuntu | Historical [4-5e](#phase-4-step-5e--kiosk-identity-and-filesystem-ownership-refusal--2026-10-14), retained raw `onpc-system-6y3ps1zs` | Repeat required in 4-10: 4-6 changed four selected module/controller files and the fixture; 4-7 changed the package policy and selected native helper. The retained historical result passed all 56 executions and cleanup, but no longer matches. Preserve all seven complete histories; 4-9 retains this follow-up. |
| Kiosk identity/home/state-root ownership refusal, preservation and resolved reboot/retry/finalization | Fedora | Historical [4-5e](#phase-4-step-5e--kiosk-identity-and-filesystem-ownership-refusal--2026-10-14) | Repeat required in 4-10: selected module/controller, fixture, package policy and native-helper inputs changed, and raw `onpc-system-pu77ev1u` is absent. Preserve all seven complete histories and enforcing SELinux; 4-9 retains this follow-up. No replacement by the distinct 4-6 history. |
| Failed native RPM post-erase/reinstall/conflict/reboot/repeated-purge history | Fedora | Historical [4-6](#phase-4-step-6--fedora-post-erase-recovery--2026-10-15), retained raw `onpc-system-axjt6axc` | Repeat required in 4-10: 4-7 changed package policy and the selected native helper. The historical eight exact executions, four complete JUnits and cleanup remain readable and passed with enforcing SELinux, but do not match the final candidate. 4-9 retains this complete-history follow-up. |

Changes outside a result's required inputs do not automatically invalidate it.
Conversely, equal package bytes do not excuse changed selected helpers, fixtures,
baseline or installation recipe. Preserve all manifest/snapshot/runtime guards;
do not relabel stale inputs or weaken matching to permit reuse. An unexplained
input difference or uncertain assertion coverage remains unproven and requires
the affected complete history. One complete result may cover multiple ledger
assertions only when its actual checks and exact inputs establish each assertion.

Before each preparation/run/export, account for the required raw evidence set
and upcoming rotation in both execution and export journals. Prefer a retained
complete covering result over exporting each duplicate predecessor. Reuse an
existing valid export; the maintained exporter currently accepts one regular file
per invocation, and every export opens a bounded retention session. Serial exports
cannot promise to retain an arbitrary set of JUnits, provenance and cleanup files.
If required evidence will not fit the maintained routes, record the exact set and
add a bounded retention/bundle prerequisite through the execution-plan workflow
before the consumer rotates it. Do not invent an archive command, bypass allocation
or increase retention limits in a task brief. Recheck every required raw path after
the last export/check; missing proof requires repeating its complete history.

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

### Historical qualification routes

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

