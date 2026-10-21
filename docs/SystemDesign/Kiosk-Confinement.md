# Kiosk confinement

The dedicated request station lets a child ask an administrator for more time
without gaining a desktop, terminal, application launcher or policy-management
session. Confinement covers the package-created `oh-no-parent-control` account,
its graphical session, user manager, services and native helper processes.
The child's personal desktop is a separate account: its time and application
restrictions belong to [Screen time](Screen-Time.md) and
[Application policy](Applications.md).

The selected implementation uses the release-based session, account and PAM
baseline described in [C02 activation](#c02-activated-session-baseline).
The [execution plan](../Kiosk-Session-Confinement-Plan.md) owns its remaining
source cleanup, route defenses and installed acceptance. The v1.4 private-runtime
descriptions below are historical source/disposition context, not live fallbacks
or qualification of the rebuilt baseline.

The current plan rebuilds **session confinement only** from the pinned v1.3
release, retaining main's non-confinement kiosk features. Prospective R01–R12
mechanism instructions have been retired; current source descriptions and
historical proof limits remain separately identified.
Use the [current rebuild direction](#current-session-confinement-rebuild) and
master mandates; do not treat those older mechanisms as prerequisites.

## Security boundary and assumptions

The attacker is a smart technical, non-administrator child using ordinary
session/desktop/terminal/SSH/remote-desktop routes and exposed kiosk actions.
Very low-level professional/world-class exploitation is excluded under the
[master threat scope](../Kiosk-Session-Confinement-Plan.md#mandatory-threat-scope-reasonable-child-effort).
The child can operate the request station
and prepare files in their own account. Engineering tests additionally plant
kiosk-owned files, submit service requests and vary trusted configuration as
root to challenge boundaries that the public UI does not expose. Those fixtures
do not imply that a child can write root-owned policy or invoke privileged test
helpers. A fixture that pregrants arbitrary kiosk code execution does not, by
itself, establish a reachable customer escape or justify an admission predicate.

The trusted base comprises the kernel, root-owned package and distribution code,
PAM, systemd, GDM, AccountsService and Polkit, with the distribution's normal
security policy. The packaging boundary is Ubuntu 26.04/GNOME 50 and Fedora
Workstation 44/GNOME 50. Host composition of the rebuilt baseline supplies no
installed confinement qualification and does not change the product's overall
[release qualification](../System-Design.md).

The required customer result is a usable passwordless request form with genuine
administrator approval and no unrestricted station desktop. A legitimate unusual
host configuration or unrelated installed application must not create an
avoidable admission prerequisite. A normal supported fixture rejected at entry
is a product blocker; an intentional-refusal label cannot waive it. Deliberately
unsafe security fixtures separately prove that inability to establish isolation
never becomes unrestricted success. Explicit administrator access denials remain
effective and ordinary accounts retain their authentication and access policies.

Kernel or trusted-service exploits, stolen administrator credentials,
administrator policy changes and booting another operating system are outside
this boundary. The historical scenario table records bounded former proof
obligations, not exhaustive resistance or current rebuilt-baseline acceptance.

## Admission and account integrity

[Provisioning](../../tools/provision.py) creates a non-administrative account with
`/usr/sbin/nologin`, the dedicated Wayland session and durable visible/saved
AccountsService classification. Its recorded UID and reserved home determine
ownership. The product's Polkit rule denies the station changes to its own
AccountsService metadata. Provisioning uses public account properties; optional
artwork cannot veto required routing. [Lifecycle](Lifecycle.md#prepared-owned-lifecycle-migration)
owns retirement of the former private visibility state.

Fresh creation explicitly leaves expiry unset and the initial password locked.
After publishing its numeric UID authority, configuration records the original
expiry and quarantines the account before deleting the password. A retry between
UID publication and expiry journaling therefore records the correct unset origin;
an administrator's explicit expiry is still preserved. Reconfiguration uses the
same private UID-bound expiry transaction. Successful rebuilt PAM integration
restores that expiry.
Interruption and reboot retain the barrier, including for an already
passwordless account. Foreign identities and changed transaction records are
preserved rather than adopted.

The [native PAM module](../../tools/pam_oh_no_parent_control.c) checks the actual
service and account. Terminal and SSH account admission are denied. GDM account
and session checks require the dedicated preference and Wayland transport; a
repaired preference still denies the current attempt. Root-owned no-follow
locks serialize routing, admission, preparation and lifecycle writers. Current
missing state, unsafe lock files and contention deny admission.

The [distro PAM integration](../../packaging/distro_pam.py) uses Ubuntu's
`pam-auth-update` and Fedora's owned authselect transaction. Readiness verifies
the finite product authentication/account blocks, their skip destinations and
the following runtime-cap hook. It accepts equivalent logical lines and leaves
unrelated vendor content opaque. Ordinary accounts retain their authentication,
account denials and time policy. No v1.4 callback inventory or private material
measurement participates in the selected native module.

Saved preferences and a nologin shell do not attest to GDM's next executable.
The legacy PreSession hook is unselected. C06a retains the actual desktop/session
choice, TTY, SSH and remote-desktop route review, with ordinary-account controls;
host composition does not close those defenses or prove passwordless entry.

## Native execution and executable identity

The selected session uses the distribution's `gnome-session` and GNOME Kiosk
target directly. Current isolated Python entrypoints run the shared form and
notification provider; the vendor authentication agent retains its public
systemd service identity. No native role dispatcher, private mount image,
preparation service or required-material inventory is on this production path.
The selected native PAM module retains only account/session routing, ordinary
time/runtime-cap behavior and the lifetime lease needed by owned migration and
removal. See [C02 activation](#c02-activated-session-baseline).

**Historical v1.4 source account:** the following native graph and private-view
descriptions explain the disconnected source removed by C02d. They describe
neither the selected runtime nor extra requirements for its replacement.

The native gate (`tools/kiosk_confinement.h`) selects the production
fresh manager transaction (`tools/kiosk_fresh_startup.h`) for `systemd-user`
and retained gate transaction (`tools/kiosk_retained_startup.h`) for
`gdm-password`. Both run under identity-checked admission/preparation locks and
a bounded transaction deadline. The PAM-owned transaction retains unresolved
cleanup ownership; repeated callbacks cannot adopt another manager or allocate
another generation in the same handle.

Ubuntu changes and verifies the caller's enforcing AppArmor profile. The
generated policy selects the AppArmor 4.0 feature ABI; non-bootstrap roles deny
user namespaces. Fedora GDM receives a verified pending SELinux exec context
whose private entrypoint type constrains the actual next executable. Its
single-threaded systemd executor instead enters the current
`onpc_kiosk_manager_pam_t` domain before returning from PAM. The surviving
`sd-pam` child remains confined through credential deletion and teardown, with
no unconfined waiting-helper exception or reverse dynamic transition. Native
capability clearing removes and verifies inheritable/ambient capabilities while
preserving the trusted executor's effective/permitted sets; it does not change
the bounding set. No subprocess runs after the final MAC operation.

The bounded preparation service (`tools/kiosk_preparation_service.py`)
measures the owned account, enforcing policy, successful-load attestation and
current required material. The helper and native caller independently bind the
measurement, selected plan and actual mounted realization. Current required
material includes native executables/libraries, the vendor privilege helper,
Python/JS code, unit/activation inputs and an exact runtime inventory. That
inventory also includes cosmetic assets, fonts, translations and historical
What's New catalogues. Their present participation in admission is a limitation
to remove under the target, not evidence that their exact bytes are security
predicates.

Copies use independent root-owned inodes; global distribution executables are
neither hardlinked nor relabelled. Trust checks include lexical aliases,
original ancestors and complete symlink target chains. Explicit initialization
of proven new private objects checks root effective/filesystem UID and applies
root:root ownership before final modes without changing caller credentials or
umask. Existing/retained objects are validation-only. Failure cleanup removes
only recorded new identities; replaced, mounted, foreign or unknown state stays
intact and the original failure is retained.

<a id="planned-post-layout-ambient-binding"></a>
<a id="planned-retained-material-and-immutable-pins"></a>
<a id="planned-retained-view-admission-proof"></a>

### Current private views and retained admission

These compatibility anchors replace the superseded task-numbered design
exposition. Current production behavior follows the source entry points above;
the [implementation baseline](../Kiosk-Session-Confinement-Plan.md#implementation-baseline)
records the transition and its qualification limits.

The native caller creates a private mount namespace and a validated,
invocation-local tmpfs staging root. Preparation builds a directory skeleton
with private parents from `/usr` to protected inputs. Checked sibling entries
are represented by read-only binds; untrusted sibling directories are masked
and untrusted files, links, special or unrepresentable entries are omitted.
Required inputs remain strict. This still enumerates ambient siblings and
applies finite inventory/storage limits, so masking alone does not remove host
layout as a dependency.

Fresh startup independently copies selected code/runtime inputs, realizes the
private tree, attaches it recursively over `/usr`, makes it read-only, removes
owned staging mounts and publishes material, view and pin receipts before the
final MAC transition. Private directory dentries preserve mounted executable
and library views across package unlink/replacement and manager reexec.

Retained entry measures current required material, acquires the actual live
manager through public systemd service properties and pinned process objects,
and verifies its unit invocation, credentials, threads, labels, namespace,
executable and completed source receipts. It clones the manager's actual mounted
source, constructs an invocation-private projection and rechecks the original
manager and sources before MAC. Ambient omissions do not rewrite the manager's
receipt or allocate another completed generation. A source pin surviving manager
exit supplies storage lifetime only, never authority to admit a missing manager.
Disk receipts and saved numeric PIDs do not replace live identity proof.

Current required-material drift can produce `stale-manager-reboot-required`;
configuration does not stop or replace that manager. Completed generations
survive until reboot. Current limits are four generations per boot, 32,768
directory entries and 512 MiB of copied input per generation. Only owned
incomplete preparations are reclaimed under the exclusive lock. The current
fresh/retained code is implemented, but host composition checks and older
bootstrap evidence do not establish final installed entry qualification for
that composition on either target.

### Prospective compatibility-first target

The [target design](../Kiosk-Session-Confinement-Plan.md#target-design) is blacklist-led and
default-tolerant toward host configuration, with practical confinement of the
UI-driven request station. A child normally starts with the kiosk app, not an
arbitrary-code execution capability. Each restriction must identify a concrete
reachable route to a desktop, shell, SSH session, account switch, unauthorized
management operation or required-helper escape. Relevant routes include GDM
selection, exposed UI launch/handler actions and child-writable startup,
autostart, configuration, module, plugin or activation searches. Unknown benign
host services and trusted system helpers are not presumed attacks and do not
automatically activate inside the kiosk or veto entry.

Use a small fixed kiosk startup, account isolation and narrowly justified OS/role
fences. A universal executable whitelist or a complete closed `/usr` image is not
a mandatory design prerequisite. Unrelated host software contributes no ambient
scan, exact identity comparison or admission veto. Missing cosmetic resources
use safe defaults; unavailable optional services/renderers disable their feature
while preserving the usable core request form and parent approval. Python,
scripts, JavaScript, units and plugin configuration remain executable authority;
their concrete reachable injection risks cannot be reclassified as cosmetic.
Assess write authority on consumed paths using the relevant identities, group
membership and ACLs. A group-write bit, including on a root-group directory,
does not by itself establish child control. Unrelated writable data needs no
empty private view. Exclude a child-writable consumed input or its launch route;
reject entry only if the essential boundary cannot be recovered.

Healthy retained reuse becomes an optimization. A single lifecycle owner may
renew a proven owned stale/failed instance with bounded recovery, serialization,
live-session checks and identity-safe cleanup. Foreign or replaced state is
preserved. The target must demonstrate actual first exec, manager and teardown
safety, genuine Polkit approval, ordinary-account preservation and explicit
administrator-policy enforcement on both platforms before removing relevant
current guards. It does not claim to contain arbitrary-code compromise through
a blacklist of executable names alone. A read-only bind alone does not prove
immutable backing bytes; neither blind validator deletion nor a guessed kernel
transition is a complete design.
The plan's [acceptance](../Kiosk-Session-Confinement-Plan.md#acceptance) separates normal
compatibility fixtures from injected unsafe security negatives.

### Architecture decisions required before the entry proof

**Historical R-series anchor; the prospective programme is retired.** The
[current session-confinement plan](../Kiosk-Session-Confinement-Plan.md#target-design)
replaces the former R01–R12 decisions, proof sequence and estimates. The exclusive
unit graph/private bus, custom loading, PAM callback projection, native admission
records, visit/agent generations, effect-admission protocol and single recovery
transaction proposed here are not selected architecture or prerequisites for the
C-series rebuild. Their review history remains in Git; it supplies no product or
installed acceptance. Use the [current rebuild boundary](#current-session-confinement-rebuild)
and cumulative C01 source maps below for current dispositions and receiving owners.

#### Current source and public mechanism

These are descriptions of the existing implementation pending its assigned
cutover, rather than requirements to retain the old confinement mechanism.

| Current source/caller | Current behavior and boundary |
| --- | --- |
| [Shared kiosk profile](../../data/pam-configs/oh-no-parent-control-kiosk-only), [time profile](../../data/pam-configs/oh-no-parent-control-session-limits), [Ubuntu packaging](../../packaging/ubuntu.inc) | `pam-auth-update --package` adds account/session routing and child-time enforcement. Kiosk/admin skips cover product time modules, not the remaining authentication/account policy. Neither profile grants empty-token authentication. |
| [Fedora profile owner](../../packaging/fedora_pam.py), [stager](../../packaging/stage_distribution.py), [Fedora packaging](../../packaging/fedora.inc) | The custom authselect profile copies the selected base, retains features and substitutes `wheel` for `sudo` in shared product rules. Preinstall and first profile creation currently reject `without-nullok`. This is current behavior, not a new compatibility requirement. |
| Historical PAM packaging (`packaging/kiosk_confinement.py`, removed by C02e) | Rendering preserved vendor auth/account rules, appended a final session gate, skipped two callback names and rejected unfamiliar session modules, manager auth additions and exact-byte drift. Original/generated records also supported owned rollback. C02c/C02c2 own selective replacement and installed-state migration. |
| [Native PAM](../../tools/pam_oh_no_parent_control.c), [login check](../../tools/oh-no-parent-control-login-check) | The login helper checks integration, service and saved/actual session routing; it does not evaluate passwords, shadow expiry or arbitrary PAM access rules. Normal native authentication enforces child time rather than granting a kiosk password exemption. Account/session modes bind the GDM handle and route; manager credential mode rejects authentication and permits kiosk setcred. Close returns success, with admission ownership released by PAM-data cleanup. |
| [Polkit authorizer](../../broker/oh_no_parent_control/authorization.py), [selected-parent rule](../../data/polkit-1/rules.d/00-oh-no-parent-control-session.rules), role policy (`tools/kiosk_confinement_policy.py`) | `PolkitAuthorizer.check` passes the validated approver and requesting system-bus identity. The rule restricts the challenge to that parent; kiosk entry confers no approval authority. Product forms never receive the parent's password. Fedora policy retains the live setuid `polkit-agent-helper-1`, `policykit_auth_t` and `unix_chkpwd`/`chkpwd_t` path; Ubuntu retains its vendor root-helper/password path. |

Linux-PAM's [management-group and include/substack semantics](https://github.com/linux-pam/linux-pam/blob/v1.7.1/doc/man/pam.conf-syntax.xml)
separate authentication, account policy and session setup. The
[pam_unix contract](https://www.man7.org/linux/man-pages/man8/pam_unix.8.html)
separates empty-password authentication from account/password expiry, while the
[authselect base template](https://github.com/authselect/authselect/blob/1.5.0/profiles/sssd/system-auth)
uses `without-nullok` to remove the Unix empty-token option. These references
explain public mechanisms; they do not qualify an installed platform or prescribe
the discarded kiosk-only PAM projection. Genuine parent authentication,
cancellation, grant arithmetic and ordinary child enforcement retain their
[broker contract](Broker.md#authorization-and-grant-transactions) and
[C01b disposition](#c01b-feature-and-approval-source-lineage).

### R01a execution and activation decision

**Historical incoming-link anchor.** The exclusive graph/private-bus proposal
has been retired under the plan above. The following existing-path observations
remain relevant to the source boundary; they do not select a replacement.

The current local path runs through [native PAM](../../tools/pam_oh_no_parent_control.c),
[routing](../../tools/oh-no-parent-control-login-check),
native admission (`tools/kiosk_confinement.h`),
fresh startup (`tools/kiosk_fresh_startup.h`) and
retained startup (`tools/kiosk_retained_startup.h`).
Preparation (`tools/kiosk_preparation_service.py`) consumes account, policy
and material machinery in confinement preparation (`tools/kiosk_confinement.py`).
Its runtime/cosmetic material inventory and generated private units/known-name
D-Bus masks belong to the existing framework classified in
[C01a](#c01a-session-source-lineage), not the release reconstruction baseline.

The existing ordering has these limits:

- GDM sets the kiosk primary GID and NSS supplementary groups before session
  open, while UIDs remain root at the native gate. The separate systemd-user PAM
  executor runs before its final group/user drop, after the unit umask is applied.
  Neither native startup coordinator resets inherited IDs, groups or umask.
- Fresh startup confines the manager's separate ancestry. Retained startup
  requires a measured live manager and clones its source. Ubuntu changes the
  caller profile immediately; Fedora sets a pending exec context, which cannot
  retroactively confine earlier children or the waiting GDM worker.
- GDM's first executable is its absolute Wayland wrapper, before the product
  launcher. GDM applies its environment files after PAM open; `GDMSESSION` is
  supplied after that open. The wrapper connects to a bus and can fall back to
  PATH-resolved `dbus-daemon --session`. Only later does the
  [fixed launcher](../../tools/kiosk_session.c) clear environment and start the
  fixed GNOME session. The current fresh unit path ends with `:`, retaining
  default unit searches. The agent unit currently imports kiosk-owned
  `polkit-agent.env`; these facts do not imply the discarded controller exists.
- The form requests GNOME shutdown. GDM's wrapper waits for its direct
  subprocesses, rather than all separately managed services; GDM later performs
  vendor-context close-session/delete-cred/PAM-end cleanup. PAM-data destruction releases the
  admission lease; unresolved transaction recovery may retain separate locks.
  The manager's surviving `sd-pam` has its own credential/session teardown.
- Native private creation and Python `private_initialize` require effective/
  filesystem root and set root:root/final modes only on proven newly created
  non-lock objects. New lock files retain inherited GID and require protected UID,
  exact `0600` mode and named identity; existing objects are validated.

The upstream [GDM worker](https://github.com/GNOME/gdm/blob/50.1/daemon/gdm-session-worker.c),
[Wayland wrapper](https://gitlab.gnome.org/GNOME/gdm/-/blob/50.1/daemon/gdm-wayland-session.c)
and [systemd executor](https://github.com/systemd/systemd/blob/v259/src/core/exec-invoke.c)
explain this ordering. GDM's authentication/account calls retain their native
password-required flags; token-change policy and partial-open cleanup are
distinct from route checks. Source ordering is not installed acceptance. The
[C01a handoff](#c01a-cross-component-handoff-and-open-questions) records the
current-GDM first-exec gap and the receiving C02/C06 owners.

#### Current session-confinement rebuild

The current [master](../Kiosk-Session-Confinement-Plan.md#target-design) requires starting
from **only kiosk session confinement** at `releases/v1.3` commit
`188be907c46b1cd0dabae06ac898c43e75beb05e`, then adding justified protections.
All main non-confinement kiosk features and other product code stay current.
The [C01 boundary](#c01-selective-replacement-boundary) maps the exact
function/configuration boundary; [C02 activation](#c02-activated-session-baseline)
selects that slice.
This is additive work from the release, not subtraction from v1.4 confinement.

The earlier custom Python/native-loader proposal is discarded. Trusted installed
Python/GTK/GI code and normal lazy loading remain part of the trusted base.
[C06](../Kiosk-Prompt-Tasks/C06-protection-review.md) reviews actual deliberate
smart-child routes before C07/C08 add protection. Every protection-caused failed
use must meet the master's justification and usability mandates; unfamiliar
machine configuration alone cannot justify a veto.

C03/C04 realign host and installed/E2E automation with the rebuilt source,
preserving main feature tests and customer behavior while retiring obsolete
mechanism assertions. Historical R01–R12 architecture and partial source/test
receipts below are not active requirements, selected mechanisms or acceptance
for this rebuilt candidate. Public baseline use precedes new protections, and
final acceptance remains both-platform installed evidence.

##### C02 activated session baseline

C02 selects the prepared C02a/C02b/C02c account, runtime and PAM composition.
The unchanged `oh-no-parent-control` Wayland session starts distribution
`gnome-session --session oh-no-parent-control` and the GNOME Kiosk target. The
app, notification provider and vendor Polkit agent retain their service names;
the form keeps main's language, Preferences, duration controls, artwork,
What's New, diagnostics and direct broker approval interfaces. App exit or
failure requests session shutdown; reading, choosing and authenticating have no
new idle deadline. Shared child-overlay behavior remains under the same form
and broker contracts.

The selected account provisioner uses the package's fixed UID marker, reserved
home and public AccountsService routing/classification properties. Native PAM
keeps kiosk service/Wayland checks, the ordinary-user time and runtime-cap hooks,
and a shared admission lease through `pam_end`. The distro owner verifies only
the finite product blocks, preserving vendor authentication/account authority
and ordinary accounts. Actual GDM next-executable and remote-route defenses
remain C06a/C07 acceptance work.

The [lifecycle owner](Lifecycle.md#prepared-owned-lifecycle-migration) now owns
the selected migration and post-erase finalizer. Package activation disconnects
the old session/app/notification dispatchers, private policy/preparation graph, compositor
and audio confinement overrides, and historical PreSession route. These are
neither enabled alternatives nor hidden fallback paths. Exact source deletion
and remaining host/installed automation audits remain C02d/C02e and C03/C04;
this host cutover grants no installed passwordless-entry, approval or update
qualification.

The fixed `wellbeing` and `packages` wrappers remain selected feature consumers
of `tools/kiosk_session.c`: ordinary users retain their own environment for the
Wellbeing helper, and the diagnostic package query keeps its finite vendor
command. C02d must remove only the dead roles/default from this mixed source,
preserving or moving these two consumers. The wrappers import no old admission
or private-runtime framework.

C02d receives the following disconnected source inventory, including its direct
test consumers. The initial C02 working tree was clean; there was no separate
staged, unstaged or untracked old-plan delta to exempt from this inventory.

| Owner | Remaining source and disposition |
| --- | --- |
| C02d | Remove `tools/kiosk_bwrap.c` and the native headers `kiosk_confinement.h`, `kiosk_private_creation.h`, `kiosk_host_proof.h`, `kiosk_manager_admission.h`, `kiosk_material_authority.h`, `kiosk_view_receipt.h`, `kiosk_preparation_channel.h`, `kiosk_preparation_child.h`, `kiosk_preparation_plan.h`, `kiosk_native_realization.h`, `kiosk_policy_authority.h`, `kiosk_view_publication.h`, `kiosk_fresh_startup.h`, `kiosk_retained_record.h`, `kiosk_retained_startup.h` under `tools/`, after closing their include/test callers. |
| C02d | Remove `tools/kiosk_confinement.py`, `tools/kiosk_confinement_policy.py`, `tools/kiosk_preparation_input.py`, `tools/kiosk_preparation_service.py`, `tools/kiosk_view_receipt.py` and their generated graph/material/policy definitions and direct fixtures. They have no selected package/runtime caller. |
| C02d | Remove `data/systemd/oh-no-parent-control-kiosk-confinement.service`, `data/systemd/user/org.gnome.Kiosk@wayland.service.d/confinement.conf` and `data/systemd/user/wireplumber.service.d/oh-no-parent-control.conf`; none is installed or enabled by the new payload. Selectively remove unused roles from `tools/kiosk_session.c` while preserving the two feature consumers above. |
| C02e | Remove unconsumed `packaging/kiosk_confinement.py`, `data/gdm3/PreSession/Default` and residual old integration fragments/definitions after C02d closes runtime callers. Keep the selected migration's finite installed-state ownership/recovery handling; it is not a fallback admission protocol. |
| C02e | Recheck the C01 frontend/broker map: direct public request APIs, scoped approval, cancellation, locale preparation and all main form features stay selected. Do not invent visit/controller modules absent from this source or delete useful shared code to satisfy a historical name. |

The selected-path provision/login/PAM tests now target the rebuilt owners;
discarded cache-admission, integrity/private-manager assertions lose their
implementation. Replacement checks retain UID/home/admin ownership, public
routing, optional-artwork fallback, ordinary time policy, service/transport
denials and lease lifetime. Still-runnable old native/header fixtures remain
with C02d/C03; C04 owns installed/E2E consumer alignment. No historical customer
case or required public result is removed by this source cutover.

The parallelism review retains the existing compatible unit classifications.
The affected fixtures use launcher-owned pytest scratch, private staged package
trees, process-local account/service doubles and the existing bounded native
compiler/mapping children with forwarded scratch leases and joined cleanup.
No shared host account, PAM file, service, bus, display, cache, network or VM
resource is acquired, and no cleanup/UI inventory gains an owner.

C02 host acceptance passed **974 checks** in the finite package
configuration/removal/input/payload/activation/RPM, Fedora PAM, native PAM,
provision/login, runtime-cap, systemd-unit and host-classification selection,
with a 600-second worker deadline; see the
[host report](../../output/test-runs/host/plans/9e6d398945018fab1240008bd0d1c27837ea1d8065b0d73abfbe70631ec42477/accepted-evidence.json).
This includes native ordinary-user success and kiosk denial through both
post-unpack failure callbacks, successful retry, interrupted fresh-account
creation with genuine administrator-expiry controls, capture/retirement
interruption and ownership refusals, and repeated removal/purge after state is
gone. The selected source has no changes to main's broker, kiosk/shared-form,
child or parent feature code, or the mixed feature-wrapper source.

Independent Astra xHigh review passed **Usability priority**, **Threat scope**
and **Ownership/lifecycle**, with no actionable backend finding remaining. Its
four initial findings were resolved: failed post-unpack configuration uses
vendor PAM with kiosk-only denials rather than incompatible legacy native
options; fresh creation keeps a locked credential until original expiry is
journaled and quarantined; exact captured-file ownership survives old-state
erasure and interrupted retirement; and mismatched saved UIDs refuse before
capture writes. The final host run covers these revisions. The review's two
stale-document findings were corrected in the removal and screen-time owners;
their selected-hook and activation descriptions now match the source.

Final `make build` passed for both DEB and RPM after the final packaged-source
edits. Retained outputs are
`output/deb/oh-no-parent-control_1.4+local1~ubuntu26.04.1_amd64.deb`,
`output/rpm/oh-no-parent-control-1.4-0.1.dev.fc44.x86_64.rpm` and
`output/rpm/build.log`. Implementation/review agents are closed, test/build
children and owned scratch cleanup completed, and no task-owned process, VM,
installed state or temporary preparation source remains. Normal reports and
package outputs are retained. No installation, staging, commit or push was
performed. Installed entry, approval, update/removal and route qualification
remain with their declared later tasks.

C02 verified the predecessor's retained accepted result, command record and
completed cleanup through the maintained bundle reader. The three C02c report
destinations now use the stable accepted-proof locator; their original members
retain the exact 187, 676 and 639 passing checks in
`onpc-evidence-bundle-iglk69um` (SHA-256
`2601490f36342e6652f801aebaa7065946197d9ee2f8f93c4435964bca6b41ac`).
Only destinations changed; predecessor completion and acceptance claims remain
historical and unchanged.

Close-out passed **639 metadata checks** in the maintained consistency selection
and `test_execution_plan_launcher.py`, with a 600-second worker deadline and
completed cleanup; see the
[close-out report](../../output/test-runs/host/plans/9e6d398945018fab1240008bd0d1c27837ea1d8065b0d73abfbe70631ec42477/accepted-evidence.json).
The read-only plan check selects C02d with 53 tasks remaining. Only C02 is newly
checked and its temporary brief is removed; every other row's status, relative
order, scope and dependencies remain unchanged.

The preparation records below describe each predecessor's accepted unselected
state at its own completion. C02 selection supersedes those exclusion claims;
their commands, counts and review findings remain historical evidence.

##### C02d native and runtime source cleanup

C02d started from clean HEAD
`4d0107dca338061da3dcae1d32d505e72f8949a4`: no staged, unstaged or untracked
old-plan delta existed. The committed superseded code was therefore the entire
removal input. C02's disconnected-source inventory above has these dispositions:

| Source family | C02d disposition and remaining consumers |
| --- | --- |
| `tools/kiosk_bwrap.c` and the fifteen native headers listed in the C02 handoff | Removed with their direct native, graph, view, receipt, material, preparation and fresh/retained startup fixtures. No remaining production/test include consumes a removed header. |
| The five runtime Python modules in the C02 handoff | Removed, including the graph/MAC/material generator and serializers. No checked-in generated graph copies or selected Makefile/package inputs remain; no remaining Python import consumes these modules. |
| The confinement system service and compositor/WirePlumber drop-ins | Removed; selected systemd, session and D-Bus consumers already use C02's public commands. |
| `tools/kiosk_session.c` | Retains only the fixed `wellbeing` and `packages` feature commands. The unselected session default and app, notification, cleanup, audio and D-Bus roles are removed. Ordinary-user Wellbeing environment and the fixed RPM diagnostic query remain. |
| Direct host consumers | Removed twenty-one dedicated mechanism test modules and five shared fixture modules, plus their unit classifications and obsolete isolation rationales. Mixed login/confinement tests retain selected session/feature coverage, remaining package-helper checks and installed-helper checks. No cleanup/UI inventory changes. |
| Remaining package and installed consumers | `packaging/kiosk_confinement.py`, the historical PreSession source and their residual direct tests remain with C02e. Installed engineering helpers and their host tests remain for C04's audit; they do not import the deleted runtime modules. Selected migration ownership and original installed records are unchanged. |

Historical source links to removed implementations/fixtures are now plain source
names; accepted evidence and historical claims keep their original scope.
The broader package/feature, host and installed/proof audits remain with
C02e, C03 and C04 respectively. No installed qualification is claimed here.

C02d host acceptance passed **1,108 unit checks plus source/traceability** in
the ten-module kiosk login/confinement, unit inventory, package
input/payload/activation/RPM, guest-input, system-info and systemd selection,
with a 600-second worker deadline. The
[initial run](../../output/test-runs/host/plans/9e6d398945018fab1240008bd0d1c27837ea1d8065b0d73abfbe70631ec42477/accepted-evidence.json)
passed 1,106 checks and exposed two stale embedded-finalizer fixtures: they still
relocated the retired helper's constants after C02 selected lifecycle migration.
The fixture now uses the maintained migration machine and shared path relocation,
preserving payload-erasure, original-PAM restoration and state/barrier cleanup
assertions. The exact selection's
[resumed acceptance](../../output/test-runs/host/plans/9e6d398945018fab1240008bd0d1c27837ea1d8065b0d73abfbe70631ec42477/accepted-evidence.json)
passed both repaired cases and the previously unrun source check, retaining the
unaffected results. The fixture forwards scratch leases and uses only private
files, absent-account doubles and a bounded waited interpreter; existing unit
compatibility remains valid, without cleanup/UI inventory changes.

Independent Astra xHigh review found no actionable backend issues:
**Usability priority, Threat scope, feature preservation, consumer closure and
ownership/lifecycle: passed**. The subsequent fixture-only repair changes no
reviewed product code. Final `make build` passed for DEB and RPM after the final
packaged edit, retaining
`output/deb/oh-no-parent-control_1.4+local1~ubuntu26.04.1_amd64.deb`,
`output/rpm/oh-no-parent-control-1.4-0.1.dev.fc44.x86_64.rpm` and
`output/rpm/build.log`. Generated coverage reflects the current inventories.
All agents are closed, test/build children and owned scratch cleanup finished,
and no task-owned VM, installed state, temporary source or live process remains.
Normal reports/package outputs are retained. No installation, staging, commit
or push was performed.

The C02 report destinations use the stable accepted-proof locator after
verification of the original 974-check and 639-check results, exact command and
completed cleanup in `onpc-evidence-bundle-3jqvd3kg` (SHA-256
`cac9b2b2ad43b16294091bfd4e1ac0ce7fe49613301f6316950ba08a0d177625`).
Only destinations changed; predecessor completion and claims are unchanged.

Close-out passed **639 metadata checks** with a 600-second worker deadline and
completed cleanup in the
[final report](../../output/test-runs/host/plans/9e6d398945018fab1240008bd0d1c27837ea1d8065b0d73abfbe70631ec42477/accepted-evidence.json).
Markdown links and the read-only plan check passed; the pointer selects C02e
with 52 tasks remaining. Only C02d is newly checked and its temporary brief is
removed. Every other row, order, Scope and Requires field is unchanged.

##### C02e feature protocols and package source cleanup

C02e started from clean HEAD
`a2b98d1414e638fdc023f788e5f83efd4d81e5cc`: no staged, unstaged or untracked
old-plan delta existed. The cumulative C01/C02d source inventory now closes as
follows; installed records and retained evidence are not source-deletion inputs.

| Source family | Final source disposition and retained owner |
| --- | --- |
| Native/runtime graph, material, preparation, receipt and private-view code | Removed by C02d with its direct includes, imports, generated definitions and fixtures. Only the useful Wellbeing and fixed RPM diagnostic roles remain in `tools/kiosk_session.c`. |
| `packaging/kiosk_confinement.py` | Removed with its exact-module parser, old installation/loading protocol, unused test adapter and shell doubles. Selected `distro_pam.py` and `lifecycle_migration.py` retain PAM policy, original-state ownership, quarantine, rollback and post-erase finalization. The renderer embeds only the selected migration owner. |
| `data/gdm3/PreSession/Default` | Removed; no package input installs this obsolete hook. Fresh-package fixtures no longer generate its payload. Explicit historical-hook tests and the templates' exact owned-hook retirement remain, including the distro path scalar. |
| Remaining package definitions | Removed overridden distro PAM fragment bodies, the stale Fedora hook-labeling operand and new-payload activation classifications for discarded roles/private trees/drop-ins. Current Wellbeing/packages classifications and recorded old-manifest removal impacts remain intact. No selected Makefile, source map, RPM/DEB payload or generated definition consumes the removed source. |
| Frontend/broker feature interfaces | No controller, startup, visit-token or receipt API exists to delete. Direct request/XML methods, scoped genuine approval, cancellation, policy transactions, locale preparation, logout, shared overlay and all main form features remain with their current owners. No feature production source was restored from the release or removed by historical naming. |
| Direct and remaining test consumers | Removed 54 functions (132 parametrized checks) of the retired helper, including the later optional-cgfs composition that imported its parser. Preserved the selected post-erase finalizer and 67 installed-helper functions. Migration tests now consume finite exact historical PAM/state snapshots rather than execute the retired installer; their ownership, foreign-state, restoration and retry assertions remain. C03 owns the remaining host audit; C04 owns explicit historical installed-helper consumers, which import no removed checkout module. |

This accounts for the committed cleanup inputs and the empty active-delta
inventory: each current source has a selected feature/lifecycle owner or verified
removal. Historical links to deleted source are plain names. No discarded
implementation remains as an executable fixture, fallback or package dependency.
Fixed historical migration data does not recreate a selectable runtime protocol.

Host acceptance passed **2,380 unit checks plus source/traceability** in the
13-module packaging, migration/removal, kiosk feature, request/service contract,
systemd and inventory selection, with a 600-second worker deadline and completed
cleanup in the [focused report](../../output/test-runs/host/plans/9e6d398945018fab1240008bd0d1c27837ea1d8065b0d73abfbe70631ec42477/accepted-evidence.json).
Independent Astra xHigh review passed **Usability priority** and **Threat scope**,
with no backend correctness, security, concurrency or ownership finding. Its one
P3 finding identified the unused fresh-package hook fixture; that input was
removed while explicit historical-hook removal tests stayed intact.
The affected configuration, removal and RPM selection then passed **566 checks**
with the same deadline and completed cleanup in the
[post-review report](../../output/test-runs/host/plans/9e6d398945018fab1240008bd0d1c27837ea1d8065b0d73abfbe70631ec42477/accepted-evidence.json).
This fixture-only correction changes no reviewed product code.

Final `make build` passed for DEB and RPM after the final packaged edit, retaining
`output/deb/oh-no-parent-control_1.4+local1~ubuntu26.04.1_amd64.deb`,
`output/rpm/oh-no-parent-control-1.4-0.1.dev.fc44.x86_64.rpm` and
`output/rpm/build.log`. Coverage regeneration passed when run serially after the
tests; its initial overlapping attempt correctly refused the runner lock.
Fixture resource review retains private pytest files/locks, bounded waited
children and existing compatible unit scheduling; no allocation, cleanup or UI
owner was added. All agents and owned test/build children finished. Normal
reports/package outputs remain; no task-owned VM, installed state, temporary
source or live process remains. This host task declares no targets and grants
no installed qualification. No staging, commit or push was performed.

Close-out passed **639 metadata checks** with a 600-second worker deadline and
completed cleanup in the
[close-out report](../../output/test-runs/host/plans/9e6d398945018fab1240008bd0d1c27837ea1d8065b0d73abfbe70631ec42477/accepted-evidence.json).
C02d's three report destinations now use the stable accepted-proof locator after
verifying its original reports, accepted result, exact initial/resume/metadata
commands and cleanup record in `onpc-evidence-bundle-xc5eukic` (SHA-256
`abef8d30eec12991f308dec37e4ed956baeea573eb16d2a8b0cb4b97d6ba5eec`).
Only those destinations changed; earlier completion and claims are unchanged.
The pointer selects C03a1 with 51 tasks remaining. Only C02e is newly checked
and its temporary brief is removed; every other row, order, Scope and Requires
field remains unchanged.

##### C03a1 native runtime host-test reconciliation

C03a1 started from clean HEAD
`488bf09161c378f9642380428266c25502090af9`: no staged, unstaged or untracked
old-plan fixture/module delta existed. The C01 native-runtime test inventory and
C02d/C02e removals were checked against current tests, shared helpers and
`tools/regression_unit.py`. The following dispositions close this runtime audit;
paths without a directory prefix are under `tests/unit/`.

| Items | Current disposition and surviving behavior |
| --- | --- |
| `test_kiosk_pin_storage.py`, `test_kiosk_required_material.py`, `test_kiosk_material_selection.py`, `test_kiosk_retained_projection.py`, `test_kiosk_initial_realization.py` | Removed by C02d; no fixture, import or registration remains. Exact material membership, copied runtime trees, cosmetic admission and generation/inode assertions have no selected runtime owner. Current feature assets remain covered by rendering and package tests. |
| `test_kiosk_host_proof.py`, `test_kiosk_manager_admission.py`, `test_kiosk_material_authority.py`, `test_kiosk_native_realization.py`, `test_kiosk_pin_native.py`, `test_kiosk_policy_authority.py` | Removed by C02d with their private native compilers/probes and graph authority. No removed-header include or registration remains. Selected fixed feature commands retain argument and environment checks in `test_kiosk_confinement.py`. |
| `test_kiosk_preparation_channel.py`, `test_kiosk_preparation_child.py`, `test_kiosk_preparation_entry.py`, `test_kiosk_preparation_plan.py`, `test_kiosk_preparation_service.py`, `test_kiosk_view_publication.py`, `test_kiosk_view_receipt.py` | Removed by C02d with the discarded preparation/channel/receipt/publication protocols. No caller or serializer remains; these mechanisms add no customer outcome to the rebuilt session. |
| `test_kiosk_fresh_startup.py`, `test_kiosk_retained_record.py`, `test_kiosk_retained_startup.py` | Removed by C02d together; no generated fresh/retained fixture copies or malformed-record matrices remain. Entry composition and exit/shutdown ownership use the selected session tests below. |
| `tests/support/kiosk_material.py`, `tests/support/kiosk_material_selection.py`, `tests/support/kiosk_material_authority.py`, `tests/support/kiosk_preparation_plan.py`, `tests/support/kiosk_fresh_startup.py` | Removed by C02d; caller searches found no remaining code consumer. No unused helper, private compiler or skipped legacy module is retained. |
| `test_kiosk_login.py` | Retained selected session identity/composition, app shutdown ownership, vendor agent/locale interface, notification command, source closure, ordinary-user Wellbeing settings and kiosk environment restriction. The Wellbeing compiler/observer now forwards scratch leases. Native PAM fixtures remain C03a's audit. |
| `test_kiosk_confinement.py` | Retained fixed Wellbeing/packages commands, argument refusal, environment sanitization and the finite RPM diagnostic query. Compiler/native/observer children now forward scratch leases. The selected embedded migration finalizer and `tests/support/package_scripts.py` remain with C03a; historical installed engineering-helper assertions remain with C04. Neither is a replacement runtime framework. |
| `test_request_time_estimate.py`, `test_systemd_unit.py` | Retained logout registration/acknowledgement, single exit, bounded fallback, late-reply refusal and diagnostic privacy; selected Wellbeing activation/recovery, notification startup, crash-notifier ordering and scoped agent environment. These cover normal entry/exit integration without reinstating material admission. |
| `test_kiosk_rendering.py` | Retained current artwork/cache, shared kiosk/overlay form, startup readiness and authorized timing observations. No removed runtime dependency remains; C03 retains the broader shared-form audit. |
| `tools/regression_unit.py` | All 21 removed module names and their obsolete isolation rationales remain absent. The surviving modules stay explicitly compatible; resource comments now record descendant scratch-lease forwarding. No cleanup or UI inventory entry changes. |

The launcher already forwards scratch leases into pytest, but the retained
fixtures' `subprocess.run` calls closed them before starting their compiler,
native launcher and observer descendants. The fixture-only repair passes
`scratch_descriptors()` through those calls, preserving every assertion and
existing deadline. Resource review covers private pytest trees, three tiny
compiled feature binaries across the two fixtures, bounded waited children and
process-local exec/NSS doubles. It adds no allocation, shared host path/cache,
account, PAM file, service, socket/bus/display, VM or cleanup owner. Existing
compatible scheduling remains appropriate. No product/build input changed;
backend review and package builds are not required for this test-only repair.

C03a receives the concrete inline PAM fixtures, package-machine/finalizer helper
and account/package registrations already identified in the C01 consumer map.
No `tests/support/kiosk_pam.py` exists. C04 retains the installed-helper audit;
this host task declares no targets and grants no installed qualification.

Host acceptance passed **1,656 checks** with a 600-second worker deadline in
the exact seven-module kiosk confinement/login/rendering, request-time estimate,
systemd, unit inventory and support-architecture selection. The
[focused report](../../output/test-runs/host/plans/9e6d398945018fab1240008bd0d1c27837ea1d8065b0d73abfbe70631ec42477/accepted-evidence.json)
records passing retained assertions and compatible overlap across four branches.
The worker is closed, all test children finished and launcher-owned scratch
cleanup completed. No task-owned installed state, VM or live process remains.
Normal reports are retained; no installation, staging, commit or push occurred.

C02e's three report destinations now use the stable accepted-proof locator after
verification of its exact reports, accepted result, commands and cleanup record
in `onpc-evidence-bundle-cuhc9gcp` (SHA-256
`2a03b1e1be0e5db2fe9af71d51723f27ead2869e0fa95ff70d94f370cb66d568`).
Only destinations changed; predecessor completion and evidence claims remain
unchanged.

Close-out passed **639 metadata checks** with a 600-second worker deadline and
completed cleanup in the
[close-out report](../../output/test-runs/host/plans/9e6d398945018fab1240008bd0d1c27837ea1d8065b0d73abfbe70631ec42477/accepted-evidence.json).
Markdown links and the read-only plan check passed. Only C03a1 is newly checked,
its temporary brief is removed and the pointer selects C03a with 50 tasks
remaining. Every other row's completion, order, Scope and Requires is unchanged.

##### C03a native and package host-test reconciliation

C03a started from clean HEAD
`4b1c9cda5c1290eb7bf75eaf8947034253dad23f`: no staged, unstaged or
untracked old-plan test/fixture delta existed. The C01 package/PAM consumer map
and C03a1 runtime dispositions were checked against current source, inline
fixtures, shared package machines and unit registrations. Paths without a
directory prefix below are under `tests/unit/`.

| Items | Disposition and surviving behavior |
| --- | --- |
| `test_fedora_pam.py` | Retain vendor policy and authselect profile/features restoration, genuine passwordless denial, collision/ownership refusal and interrupted retry. |
| `test_prepared_kiosk_pam.py` | Retain the selected native/distro owners' service/Wayland routing, ordinary authentication and vendor denial, role independence, account/session binding, admission lease identity/lifetime, runtime caps, readiness and rollback. Its historical filename is not an alternate product path. |
| `test_pam_runtime_cap.py`, `tests/support/pam_runtime_fixture.c` | Retain real libpam transactions with private stacks: graphical runtime-cap removal, non-GDM preservation, account denial and packaged skip rules. The C fixture has two live consumers, here and in `test_prepared_kiosk_pam.py`; both compilers remain necessary. Runtime-cap compiler children now forward scratch leases. |
| `test_kiosk_login.py` | Retain selected session composition, app shutdown ownership, vendor agent/locale, notifications, source closure, ordinary Wellbeing settings and kiosk environment restriction. The isolated login-check startup child now forwards its scratch lease. |
| `test_session_limit_check.py`, `test_system_pam_variants.py` | Retain ordinary time enforcement and the narrowly scoped administrative bridge; private PAM-variation ownership/restoration, mandatory rules, pending-update retry and independent policy checks. Installed-helper qualification remains C04's scope. |
| `test_package_configuration.py`, `tests/support/package_scripts.py` | Retain selected lifecycle/PAM composition, first-account expiry quarantine, genuine administrator expiry, post-unpack ordinary authentication and kiosk refusal, complete retry/rollback, live-worker preservation, captured-policy ownership and post-erasure finalization. Historical v1.4 PAM/config/policy records are finite migration inputs, not a live confinement implementation. Package-machine shells and nested broker/trust children now forward scratch leases. |
| `test_package_removal.py`, `test_provision.py` | Retain distro erase/abort-remove parity, PAM and account ownership, complete restoration and repeated removal/purge; selected provisioning preserves UID/home/admin-group checks, public AccountsService routing, unrelated metadata and optional-artwork behavior. |
| `test_package_inputs.py`, `test_package_payload.py`, `test_rpm_packaging.py` | Retain immutable source closure, current feature payload, absence of retired runtime assets, native helper/environment checks, Debian/RPM composition and rendered scriptlet/rollback parity. Stage/archive/native/import children now forward scratch leases, including the isolated notification-import grandchild. |
| `test_package_activation.py` | Retain current activation, backend/trust and manifest behavior. Three old preparation-support names occur only in synthetic previous-version manifests to verify removal keeps the recorded activation impact; they do not demand those files in the current payload. LMDB and manifest-generation children now forward scratch leases. |
| `test_kiosk_confinement.py` | Retain the selected standalone embedded migration finalizer and fixed Wellbeing/packages native feature commands. Shared package fixtures remain consumed here and by configuration/removal/RPM tests. Installed engineering helpers retain their separate C04 audit. |
| `tools/regression_unit.py` | Retain explicit compatible registrations for every surviving module; no removed native module or absent PAM helper is registered. Isolation comments now describe selected owners and descendant lease forwarding. No cleanup or UI registration changes. |

`tests/support/kiosk_pam.py` does not exist. Its brief reference resolves to the
inline native fixtures above and `tests/support/package_scripts.py`, as already
mapped by C01c/C03a1; no compatibility helper is introduced. No customer assertion
is weakened, skipped or removed. This host task declares no targets and supplies
no installed entry, approval or lifecycle qualification. Shared installed helpers
and public journeys remain with C04 and its following tasks.

The repairs only forward `scratch_descriptors()` through existing subprocess
layers, including numeric descriptor arguments across isolated imports that
must not load checkout support code. All assertions, inputs and existing
deadlines remain unchanged. No dead compiler, import, fixture or registration
was found after mapping its consumers. Historical hook/PAM/policy inputs remain
necessary to test migration and removal; absent-payload and previous-manifest
assertions do not require a discarded runtime in the current package.

Parallelism/storage review covers private pytest trees, small native builds,
staged source/payload archives, real libpam against private configurations,
private LMDB writer/readers and waited shell/interpreter descendants. Existing
launcher worker deadlines also bound calls without their own timeout. No new
allocation, process lifetime, host account/PAM/service, bus/display, network,
shared cache or cleanup owner is introduced. Every surviving module retains its
compatible unit classification; cleanup/UI inventories gain no owner. Product
and build inputs are unchanged, so no package build or independent backend
review is required for these fixture-only changes.

Host acceptance passed **2,473 checks** in the exact sixteen-module Fedora/native
PAM, login, runtime-cap, session-limit, PAM-variation, configuration/removal,
provisioning, package input/payload/activation/RPM, confinement, unit-inventory
and support-architecture selection, with a 600-second worker deadline. The
[focused report](../../output/test-runs/host/plans/9e6d398945018fab1240008bd0d1c27837ea1d8065b0d73abfbe70631ec42477/accepted-evidence.json)
and its inventories/progress record all selected cases passing, with compatible
overlap across four branches. Ordinary-role authentication, genuine denial,
ownership, rollback and selected entry/exit assertions remain intact. Usability
priority and threat scope pass this test reconciliation: it introduces no
product refusal or new protection requirement.

Both implementation workers are closed. Test children finished, the maintained
runner returned success after owned scratch cleanup, and no task-owned installed
state, VM or live process remains. Normal reports are retained. No installation,
staging, commit or push occurred.

The link check found that C03a1's focused report had rotated. The maintained
bundle reader verified both exact original reports, the accepted result,
command record and completed cleanup in `onpc-evidence-bundle-goeda64r`
(SHA-256 `4bc7f3561ba9e0df363b43ee879265256c38a1fc8c57e9da6119fb1a48177913`).
Its two report destinations now use the stable accepted-proof locator, retaining
the original labels and claims; predecessor status and acceptance are unchanged.

Close-out passed **639 metadata checks** in the maintained consistency selection
and `test_execution_plan_launcher.py`, with a 600-second worker deadline and
completed cleanup; see the
[close-out report](../../output/test-runs/host/plans/9e6d398945018fab1240008bd0d1c27837ea1d8065b0d73abfbe70631ec42477/accepted-evidence.json).
Only C03a is newly checked, its temporary brief is removed and the pointer selects
C03b with 49 tasks remaining. Every other row's completion, relative order,
Scope and Requires is unchanged.

##### C03b approval and broker host-test reconciliation

C03b started from clean HEAD
`95ca30710300616920eee1e9511005143c2cd151`: no staged, unstaged or
untracked old-plan test/fixture delta existed. The C01 approval consumer map and
C02b1/C02b caller chain were audited against the current authorizer, broker,
service dispatch and shared request orchestration. Paths without a directory
prefix below are under `tests/unit/`.

| Items | Disposition and surviving behavior |
| --- | --- |
| `test_core.py` | Retain wrong-role/target and selected-approver checks, genuine approval, denied/cancelled attempts without cooldown, account/preference revalidation, grant arithmetic, policy transactions and rollback. Both request surfaces cover departure during usage, preflight and every reversible snapshot, fresh authentication, no pre-admission writes/termination, and once-only admitted completion. |
| `test_broker_properties.py`, `test_broker_state_machine.py` | Retain independent grant arithmetic, policy normalization and two-child grant/policy isolation. The state machine uses the shared scoped approval double; it requires no discarded receipt. |
| `test_service_contract.py`, `tests/component/test_private_dbus_service.py` | Retain authenticated bus identity, caller-derived child target, direct public signatures, safe worker error translation, transport cancellation and disconnect liveness. Transport cancellation and broker no-grant assertions remain distinct layers. |
| `tests/component/test_authorization_lifecycle.py` | Retain real Gio/GLib lifecycle handling with private logind/Polkit doubles, selected identity/action, lock/session/disconnect cancellation, late-result refusal, bounded kiosk agent startup, final effect admission and post-admission completion/rollback. Extend final-session and sessionless positive/disconnect checks to both kiosk and child callers. Authentication outcome checks now assert unchanged policy after refusal, fresh genuine approval without cooldown, distinct checks and exactly one grant. |
| `test_request_time_estimate.py`, `test_request_selections.py`, `test_kiosk_model.py` | Retain frozen submission inputs, single-flight requests, single-use async stages, silent cancellation, late/stale result rejection and destruction guards for kiosk and overlay. Agent locale/readiness remains a real feature dependency; C-only fallback work stays with its declared receiving task. |
| `tests/component/test_broker_startup.py`, `test_systemd_unit.py`, the two authorization/startup-log cases in `test_parent_main.py` | Retain broker publication/readiness, optional failure diagnostics, role-checked startup and agent/service composition. No private-view receipt or discarded confinement readiness is required. |
| `tests/support/broker.py`, `tests/support/dbus.py` | Retain the single shared scoped `Authorizer`/`Approval` double and recording D-Bus adapters unchanged. Current mocks already implement direct calls, single-use admission and disposal; no duplicate compatibility mock or obsolete protocol fixture remains to port/delete. |

No required behavior assertion, fixture or registration was removed. Existing
controller/request tests bind the current feature lifecycle rather than an old
view protocol; unrelated test-controller credential proofs are preserved.
The bounded unit-audit worker found no additional repair and is closed.
**Usability priority: passed; Threat scope: passed** for this reconciliation:
positive approval/sessionless controls remain, genuine denial is authoritative,
and no new product refusal or protection requirement is introduced.

Resource review covers the existing private buses, in-memory account/policy
doubles and fixture-owned bounded worker threads. Added parameters run under
the same fixture and release/join route; they introduce no mutable shared path,
cache, external service, process, socket, display, storage or cleanup owner.
The existing component admission and compatible unit classifications remain
applicable; unit-inventory and support-architecture checks passed. Cleanup/UI
inventories gain no owner. Only tests and documentation changed, outside
`PACKAGE_SOURCE_FILES` and build-tool dependencies; neither package builds nor
independent backend review is required.

Host acceptance passed with no declared targets: **1,239 unit and 128 component
checks passed**, all with explicit 600-second worker deadlines. After the audit
worker closed, the combined final
[acceptance/close-out report](../../output/test-runs/host/reports/20261021T033251Z-141cf0f0/report.md)
passed **2,006 checks**, including those same acceptance inputs and all **639
metadata checks**. It records the exact ten-module core, broker property/state-machine,
service, request estimate/selection/model, systemd, support-architecture and
unit-inventory selection (1,237 checks), with compatible overlap across four
branches; the two `ParentWindowTests` authorization/startup-log cases; the
authorization-lifecycle, private-D-Bus-service and broker-startup component
modules; and the four maintained consistency modules plus
`test_execution_plan_launcher.py`. All original and expanded assertions passed.
These host results
grant no installed qualification; C04 retains installed-helper/public-journey work.

All test commands returned success after owned scratch cleanup. The audit
worker is closed; no task-owned VM, installed state, temporary source artifact
or live process remains. Normal runner reports are retained. No installation,
staging, commit or push occurred. Only C03b is newly checked, its temporary brief
is removed and the pointer selects C03. Every other row's completion, relative
order, Scope and Requires is unchanged.

C03a's two report destinations above now use the stable accepted-proof locator
after the maintained bundle reader verified both exact original reports, the
2,473/2,473 and 639/639 results, matching command record, accepted result and
completed cleanup in `onpc-evidence-bundle-d8w6g8r6` (SHA-256
`35fd01cf050fdce9284e18eec3db5c1b400d9db5f57ebf4a2f99aefa21a1ce9b`).
Only destinations changed; predecessor status and acceptance claims are preserved.

##### C02a prepared session runtime

The six session assets in `data/kiosk-runtime-unselected/` prepare the release-based
session arrangement without selecting it. Their relative destinations match
`data/wayland-sessions`, `data/gnome-session/sessions` and `data/systemd/user`.
They are excluded from `PACKAGE_SOURCE_FILES`, package installation and activation;
the existing native session entry and private runtime remain selected until C02.
There is no second session name, enabled target or live admission route.

The desktop directly selects
`gnome-session --session oh-no-parent-control`, as at pin
`188be907c46b1cd0dabae06ac898c43e75beb05e`.
The unchanged session identity is `oh-no-parent-control`, with `Kiosk=true` and
`DesktopNames=GNOME-Kiosk;GNOME;`. Its target requires `org.gnome.Kiosk.target`
and `oh-no-parent-control-app.service`; it wants the current notification and
authentication-agent services. The current kiosk-only Apport conflicts remain:
those systemd-started crash windows bypass XDG autostart suppression. Ordinary
desktop crash reporting is unaffected. This is the existing bounded route
barrier, not an inventory of unfamiliar services.

The app service runs main's `/usr/bin/oh-no-parent-control` isolated Python
entrypoint, retaining the shared form and its features. It remains bound to
`gnome-session.target`, ordered after the compositor and notification service,
with no automatic restart. Both successful exit and failure request
`gnome-session-shutdown.target`; failure retains `replace-irreversibly` job mode.
Main's `KioskLogout` still owns the cooperative GNOME client/logout exchange and
its exit-action-only fallback deadline. No idle or authentication deadline is
introduced by these assets.

The agent keeps `oh-no-parent-control-polkit-agent.service`, its optional
`%t/oh-no-parent-control/polkit-agent.env`, foreground vendor executable
`/usr/libexec/polkit-mate-authentication-agent-1` and failure restart behavior.
C02b must preserve `KioskAgentLocale`'s service/job association and pending
authentication cancellation. The notification service keeps
`org.freedesktop.Notifications`, the GNOME Kiosk notification client tag and
compositor/session stop ownership, invoking the current provider through the
vendor `gnome-service-client` with isolated Python commands. Neither prepared
service depends on an obsolete native role wrapper.

C02b/C02c consume these same public session/service identities; C02c's account
and PAM preparation must route only the dedicated Wayland session while leaving
ordinary-user policy intact. Only C02 may move these assets into the selected
locations and update package source/install/activation wiring together with the
prepared account, PAM, broker and lifecycle slices. That cutover must disconnect
the old graph and preserve live/foreign session ownership; C02d/e then remove its
unconsumed sources. C02a changes no installed state and grants no live usability
or installed-acceptance credit.

C02a host acceptance passed on 2026-10-20: **318 checks passed** in the affected
`test_kiosk_login.py`, `test_package_payload.py`, `test_rpm_packaging.py`,
`test_request_time_estimate.py` and `test_regression_unit.py` modules, using
`tools/run-tests unit` with an explicit 600-second worker deadline. The retained
[host report](../../output/test-runs/host/plans/9e6d398945018fab1240008bd0d1c27837ea1d8065b0d73abfbe70631ec42477/accepted-evidence.json)
records the exact selection and successful four-branch join. It verifies prepared
commands, session identity, service/exit ownership, current agent/logout behavior,
source exclusion and unchanged selected Ubuntu/Fedora payloads. C02 must update
the temporary unselected/current-payload assertions when it activates this slice.
The resource review retains the existing compatible unit classifications: the
new checks read small source assets, wait for one bounded Make source-list child
and reuse existing pytest-private staged payloads. No new shared cache, bus,
display, service, network or cleanup owner is acquired.

Independent Astra xHigh backend review found no actionable issues:
**Usability priority: passed; Threat scope: passed; ownership/lifecycle and
unselected boundary: passed**. It confirmed pin provenance, current feature
preservation, the notification client's vendor argument/descriptor contract and
the existing Apport route justification. Review grants no runtime acceptance.
`make build` then passed for both DEB and RPM; retained outputs include
`output/deb/oh-no-parent-control_1.4+local1~ubuntu26.04.1_amd64.deb`,
`output/rpm/oh-no-parent-control-1.4-0.1.dev.fc44.x86_64.rpm` and
`output/rpm/build.log`. These build the unchanged selected runtime, not an
installed or live qualification of the prepared assets. Both agents finished;
the test runner and build completed owned cleanup. No task-owned VM, installed
state, temporary file or live process remains; normal reports/build outputs
are retained. No staging, commit or push was performed.

Close-out passed all **639 metadata checks** in the four maintained consistency
modules and `test_execution_plan_launcher.py`, with the same 600-second worker
deadline and completed cleanup; see the retained
[close-out report](../../output/test-runs/host/plans/9e6d398945018fab1240008bd0d1c27837ea1d8065b0d73abfbe70631ec42477/accepted-evidence.json).
The plan check selects C02b1 with 59 remaining tasks. The C01 report had rotated;
its link destination alone now uses the accepted-evidence locator after the
maintained bundle reader verified the exact original report (639/639), accepted
result, command record and completed cleanup in bundle
`onpc-evidence-bundle-vhi564vh` (SHA-256
`8effa470abe2dc49daa80738a20e3cf11e3ab271d1065355eca28c9ef266644a`).
This repairs no completion claim and changes no other queue row.

##### C02b1 prepared broker approval boundary

The public methods remain `RequestAccess(uuub)→(ss)` for the configured kiosk
and `RequestOwnAccess(uub)→(ssu)` for the enabled child caller. Both XML copies,
service dispatch and frontend calls remain unchanged. No `kiosk_visits.py`,
startup receipt or view-registration interface exists in this source to port or
retain. The selected runtime consumes the compatible internal change directly;
no alternate live route or unselected broker copy is introduced.

`PolkitAuthorizer.check()` now owns a scoped approval through `_request_access`.
It retains the original caller/session subscriptions after authentication,
including the original user-manager display when used for session resolution.
`_apply` requires an admission callback after preflight and every reversible
snapshot read. Final account/preference revalidation and lifecycle queue drains
precede its single admission latch; departure and return cannot revive a queued
cancellation. A cancelled request makes no transaction or rollback writes,
terminates no apps and consumes no success cooldown. An admitted request finishes
only its original immutable transaction, with existing hard/soft app policy,
grant arithmetic and rollback limits. See [Broker](Broker.md#authorization-and-grant-transactions)
for the observed-order boundary and synchronous observer limits.

This compatible producer change activates on broker process restart; C02 still
owns runtime/account/PAM/package cutover. C02b owns shared form/agent lifetime and
result handling, preserving locale preparation, single-flight and fresh-request
behavior. C02e may remove only proven obsolete protocols and consumers; the
current public methods and vendor authentication are retained. Host evidence
does not qualify installed prompt association or complete customer histories;
those remain with C04 and the later installed tasks.

Independent Astra xHigh review passed for the owned backend/tests:
**Usability priority: passed; Threat scope: passed**. It confirmed terminal
cancellation, original-request values, one admission before rollback becomes
possible, transaction ownership and scoped cleanup before lock release. Its sole
P3 documentation finding is resolved: only a still-pending authentication needs
remote Polkit cancellation; after authentication the approval is invalidated
locally. No actionable backend finding remains. Review gives no test credit.

The resource review retains the existing compatible unit/component
classifications. Added cases use in-memory adapters, the existing private buses
and fixture-owned joined workers, with bounded Event waits and unconditional
release. They add no shared path/cache, process owner, socket, display, real
session/service or storage allocation. No cleanup/UI inventory module changes
are needed.

Host acceptance passed on 2026-10-20: **1,040 checks passed** (937 unit and
103 private-bus component cases) on the final packaged source. The exact
`tools/run-tests` selection was `test_core.py`, `test_broker_state_machine.py`,
`test_broker_properties.py`, `test_service_contract.py`,
`test_diagnostic_privacy.py` and `test_localization.py` under `tests/unit/`, then
`test_authorization_lifecycle.py` and `test_private_dbus_service.py` under
`tests/component/`, with an explicit 600-second worker deadline for each category.
The retained [host report](../../output/test-runs/host/plans/9e6d398945018fab1240008bd0d1c27837ea1d8065b0d73abfbe70631ec42477/accepted-evidence.json)
records the exact inputs and completed cleanup. Coverage includes all pre-write
read gaps, rest-of-day, departure/return, display replacement and failed final
reads, no effect/cooldown on cancellation, fresh authentication and admitted
completion/rollback on both request surfaces. An initial model check expected
`denied` after caller disconnect; it now expects the required `cancelled` result
while preserving its unchanged-state assertion. Final verification passed that
check and the three disconnect diagnostic calls, which use the existing
cancelled-outcome event without changing retained catalogue meanings.

After the final packaged edit, `make build` passed for both DEB and RPM. Retained
outputs are `output/deb/oh-no-parent-control_1.4+local1~ubuntu26.04.1_amd64.deb`,
`output/rpm/oh-no-parent-control-1.4-0.1.dev.fc44.x86_64.rpm` and
`output/rpm/build.log`. This is host acceptance, with no declared targets or
installed claim. Both agents are finished/closed; tests and build completed
their owned cleanup. No VM, installed state, temporary source file or live
task-owned process remains. Normal reports/build outputs are retained; no
staging, commit or push was performed.

Close-out passed all **639 metadata checks** in the four maintained consistency
modules and `test_execution_plan_launcher.py`, with the 600-second worker
deadline and completed cleanup; see the retained
[close-out report](../../output/test-runs/host/plans/9e6d398945018fab1240008bd0d1c27837ea1d8065b0d73abfbe70631ec42477/accepted-evidence.json).
The plan check selects C02b with 58 remaining tasks. Only C02b1 is newly checked;
its temporary brief is removed and every other queue row is preserved.

The retained C02a host/close-out report destinations above use the accepted-proof
locator after the maintained bundle reader verified their exact 318/318 and
639/639 results, original selections, accepted result and completed cleanup in
`onpc-evidence-bundle-m0ie1_mm` (SHA-256
`a1dc449a7ac35492be2ad5ba3a120e24a2a2bd837d60f84fa8dd546332fbb686`).
Only destinations changed; predecessor completion and claims remain unchanged.

##### C02b shared form and agent boundary

The shared form retains main's direct `RequestAccess(uuub)→(ss)` and
`RequestOwnAccess(uub)→(ssu)` calls. There is no startup/controller/visit module,
receipt or view-registration protocol in the selected source to delete or port.
No alternate admission path, release-wide frontend restoration or confinement
activation change is introduced. C02 still owns the runtime/account/PAM/package
cutover; C02e may delete only proven unconsumed feature protocols and wiring.

Each submission fixes its child, approver, duration and soft-app choice. Local
request revisions and stages bind preference-save, agent-preparation and result
callbacks to that one submission. Terminal failure, completion or destruction
cannot revive it, dispatch another approval or finish a fresh request. The
broker continues to own genuine parent authentication, session/disconnect
cancellation, effect admission and the original transaction after admission;
discarding a window's callback does not revoke an admitted grant.

`KioskAgentLocale.close()` is terminal. Queued work and late restart/job/deadline
callbacks cannot reopen the helper; a superseded deadline cannot fail the next
locale preparation. The existing public service/job association, finite restart
deadline, unbounded human authentication time and shared-overlay behavior remain.
Main's language/Preferences, presets, reminders, What's New, artwork, feedback,
diagnostics, request choices and public logout integration are retained. Current
C-only locale and stylesheet fallback gaps remain with C09a, and installed
native-agent association/customer histories remain with C04 and later tasks.

Independent Astra xHigh review initially found a P2 language regression: taking
a locale snapshot at submission could retain the previous child's language when
the new language reply arrived during preference saving. That extra snapshot
was removed; guarded preparation retains the original current-language lookup.
A focused delayed-language ordering regression passes. Fresh independent review
then found no actionable issues: **Usability priority: passed; Threat scope:
passed; ownership and lifecycle: passed**. Review supplies no acceptance credit.

The resource review retains the existing compatible unit and request-UI
classifications. Added checks use in-memory callback/transport doubles,
pytest-private files and the existing private preview/display/bus with its
finally-released authentication gate. They add no process, shared path/cache,
external service, display, bus or cleanup owner; no cleanup inventory changes
are required.

Host acceptance passed with no declared targets: **350 unit and 169 UI checks
passed** across the maintained selections and focused repair. The
[main report](../../output/test-runs/host/plans/9e6d398945018fab1240008bd0d1c27837ea1d8065b0d73abfbe70631ec42477/accepted-evidence.json)
records the six unit modules (`test_request_time_estimate.py`,
`test_request_selections.py`, `test_kiosk_model.py`, `test_systemd_unit.py`,
`test_kiosk_login.py`, `test_service_contract.py`) with a 600-second worker
deadline, and `test_request_form_component.py` plus `test_language_settings.py`
with an 1,800-second deadline. Its 350 unit and 165 unchanged UI cases passed.
The two new UI loop failures expected a second refused mutation after the
automation guard had already marked input uncertain. Cancel and duplicate-submit
refusals now use separate fresh attempts, preserving disabled controls, exactly
one broker request and successful completion. All four kiosk/overlay variants
passed in the [focused repair report](../../output/test-runs/host/plans/9e6d398945018fab1240008bd0d1c27837ea1d8065b0d73abfbe70631ec42477/accepted-evidence.json),
using the same 1,800-second deadline. Product source was unchanged by that
test-only repair. No assertion or input-safety guard was weakened.

After the final packaged edit, `make build` passed for both DEB and RPM. Outputs
are `output/deb/oh-no-parent-control_1.4+local1~ubuntu26.04.1_amd64.deb`,
`output/rpm/oh-no-parent-control-1.4-0.1.dev.fc44.x86_64.rpm` and
`output/rpm/build.log`. The implementation worker and both review agents are
finished/closed. The interrupted initial UI candidate, corrected full selection,
focused repair and build completed their owned cleanup. No task-owned VM,
installed state, temporary source file or live process remains; normal reports
and package outputs are retained. No installation, staging, commit or push was
performed. This host result grants no installed qualification.

Close-out passed all **639 metadata checks** in the four maintained consistency
modules and `test_execution_plan_launcher.py`, with the 600-second worker
deadline and completed cleanup; see the retained
[close-out report](../../output/test-runs/host/plans/9e6d398945018fab1240008bd0d1c27837ea1d8065b0d73abfbe70631ec42477/accepted-evidence.json).
The plan check selects C02c1 with 57 remaining tasks. Only C02b is newly checked;
its temporary brief is removed and every other queue row is preserved.

The C02b1 report destinations above now use the accepted-proof locator after
the maintained bundle reader verified the original 1,040/1,040 and 639/639
reports, exact command selections, accepted result and completed cleanup in
`onpc-evidence-bundle-kh4nne3g` (SHA-256
`ce79885d4398d61d6d069ba01237e77716760b30bc7e0b25cac7895763f904c9`).
Only destinations changed; predecessor completion and claims are preserved.

##### C02c1 prepared account provisioning

`data/kiosk-runtime-unselected/provision.py` reconstructs the account/configuration
slice from pin `188be907c46b1cd0dabae06ac898c43e75beb05e`, retaining main's
account ownership and public AccountsService improvements. It is excluded from
`PACKAGE_SOURCE_FILES`, installation and activation. The selected
`tools/provision.py`, package lifecycle, native PAM and login helper remain
unchanged; only C02 may select the prepared entry. It supplies no second live
admission path or new login-route defense.

The prepared CLI retains `--kiosk-user oh-no-parent-control`, `--prefix` and
`--check-account`. It validates the reserved NSS identity, non-root/non-admin
UID, reserved home and its owner, and the lifecycle's private numeric UID marker
before any provisioning write. `--check-account` performs only that validation.
The package lifecycle owns creation, `nologin`, password deletion and marker
publication; the marker must exist before either prepared CLI mode is called.
Ordinary accounts and their credentials, time policy and metadata are untouched.

Configuration retains main's broker schema validation, numeric `kiosk_uid`,
root-owned mode-0600 config and mode-0644 account-specific system-bus policy.
Live provisioning resolves the fixed UID with `FindUserById`, uses `CacheUser`
only for an unsaved account, disables its kiosk `LimitType`, and sets/verifies
`Session=oh-no-parent-control`, `SessionType=wayland`, `SystemAccount=false`
and `Saved=true`. Correct retained settings need no setter calls. Custom retained
artwork is preserved; optional artwork failures emit a fixed diagnostic and
cannot prevent required routing. Required account-service failures remain
operational failures, rather than claimed confinement successes.

The prepared module has no old admission imports, cache-version/package checks,
daemon restarts, shadow changes or private cache/transaction writes. The current
public API exposes `SystemAccount` read-only; `UncacheUser` would discard saved
metadata and is not a migration shortcut. A retained hidden account therefore
requires C02c2's owned migration before this entry is selected. Public visible
state alone does not prove that old private visibility work has been recovered.

The handoff is finite:

- **C02c2:** preserve `/var/lib/oh-no-parent-control/package-created-kiosk-uid`
  as the root-owned mode-0600 numeric UID authority. Recover the UID-bound
  `kiosk-configuration-account.json` (`version`, `uid`, original `expires`,
  `phase=quarantined|releasing`) and preserve unrelated native expiry policy.
  Recover AccountsService's `.onpc-kiosk-visibility-v1` slot and
  `user.oh-no-parent-control.visibility-v1` xattr using their recorded
  UID/inode/digest/metadata ownership; durably migrate retained hidden state
  without losing comments, unknown fields, groups or custom icons. Source
  cleanup does not authorize deleting these installed records or foreign state.
- **C02c/C02:** use the same fixed UID, public session identity and Wayland
  transport as the prepared session assets. Preserve passwordless entry and
  effective administrator/ordinary-account policy. The old GDM PreSession hook
  is historical and is not current-GDM routing proof. C02 must complete the
  lifecycle migration, replace the selected provisioner and coordinate native
  PAM/account admission before retiring quarantine/release and visibility-repair
  callers, the AccountsService start-pre drop-in and old integration verification.
  C02d/e may then delete their unconsumed sources and package wiring. No legacy
  fallback may remain selected.

Independent Astra xHigh backend review found no actionable issues:
**Usability priority: passed; Threat scope: passed; ownership, lifecycle and
unselected boundary: passed**. It confirmed that the retained-hidden-account
precondition is acceptable only after C02c2 completes its declared migration.
Review supplies no host or installed acceptance credit.

Host acceptance passed with no declared targets: **694 checks passed** in the
[focused report](../../output/test-runs/host/plans/9e6d398945018fab1240008bd0d1c27837ea1d8065b0d73abfbe70631ec42477/accepted-evidence.json),
using `tools/run-tests unit` with a 600-second worker deadline. The selection
includes `test_provision.py`, `test_package_configuration.py`,
`test_package_removal.py`, `test_system_first_configure.py`,
`test_system_kiosk_accounts.py`, `test_kiosk_login.py` and
`test_regression_unit.py`, plus the prepared-runtime payload-exclusion case in
each of `test_package_payload.py` and `test_rpm_packaging.py`. Sixteen new
provisioning methods cover fresh/retained public API composition, required
readbacks, optional artwork failure, reserved ownership and atomic-write
rollback. Existing selected-path configuration, ownership, interruption/retry
and removal tests remain intact. Public readbacks and service doubles do not
qualify installed persistence, migration or passwordless GDM/PAM behavior.

The parallelism review retains the compatible `provision` and `kiosk_login`
unit classifications. New cases load the inert prepared source without bytecode
output and use existing private temporary trees and process-local NSS/bus/owner
doubles. Atomic faults preserve the prior private file and remove only their
owned temporary file. The existing bounded Make source-list child and staged
Ubuntu/Fedora payload fixtures are reused. No shared cache, host account,
service, bus, display, socket or cleanup inventory changes; the rationale is
recorded in `tools/regression_unit.py` and its inventory checks passed.

Final `make build` passed for both DEB and RPM. Retained outputs are
`output/deb/oh-no-parent-control_1.4+local1~ubuntu26.04.1_amd64.deb`,
`output/rpm/oh-no-parent-control-1.4-0.1.dev.fc44.x86_64.rpm` and
`output/rpm/build.log`. These build the unchanged selected account/runtime path;
the prepared entry remains outside package selection. The implementation worker
and independent reviewer are finished/closed. The host runner and build finished
owned cleanup; no task-owned VM, installed state, temporary source artifact or
live process remains. Normal reports and package outputs are retained. No
installation, staging, commit or push was performed.

Close-out passed all **639 metadata checks** in the four maintained consistency
modules and `test_execution_plan_launcher.py`, with a 600-second worker deadline
and completed cleanup; see the
[close-out report](../../output/test-runs/host/plans/9e6d398945018fab1240008bd0d1c27837ea1d8065b0d73abfbe70631ec42477/accepted-evidence.json).
The plan check selects C02c2 with 56 remaining tasks. Only C02c1 is newly checked;
its temporary brief is removed and every other queue row is preserved.

The rotated C02b main and focused-repair report destinations alone now use the
accepted-proof locator. The maintained bundle reader verified their exact original reports,
original test commands, accepted result and completed cleanup in
`onpc-evidence-bundle-5rgw5klr` (SHA-256
`fc1c8364c724d1aaa115390f27fd6dc30b65c83c76c6269b9127f6b5f8acbf4e`).
The original 350 unit/165 unchanged UI passes and four passing repaired UI cases remain
unchanged historical claims; this repair grants no new acceptance.
Final Markdown validation checked 262 links with none missing; the plan check
and `git diff --check` also passed. No product input changed after review or build.

##### C02c2 prepared owned lifecycle migration

The unselected
[migration module](../../packaging/lifecycle_migration.py)
prepares finite legacy-state retirement without importing the old integration or
provisioner. The [lifecycle owner](Lifecycle.md#prepared-owned-lifecycle-migration)
records its exact prepare/original-PAM/readiness/commit/release, rollback,
visibility and post-erase composition, C02 activation/removal obligations and
C02d/C02e residual source deletions. The explicit prepared renderer entry is
unselected; package inputs, production lifecycle selection and activation
classification remain unchanged. The existing manifest comparison retains
removed members' activation impacts.

Known UID, expiry, confinement/PAM and visibility slot/xattr records retain
their original ownership and retry identities. Live kiosk admissions/executors,
foreign state, ordinary accounts, preferences and unrelated removal behavior
are preserved. No runtime-lock/private-generation sweep or new persistent
transaction format is introduced. Actual C02c readiness and atomic C02 selection
remain required; installed update/reentry acceptance remains C11c1/C12c1.

Independent Astra xHigh review resolved two P1 findings and one P2 finding:
rollback now restores SELinux policy and admission/PAM labels under quarantine
before reopening; post-erase finalization preserves unrelated ordinary PAM
workers retaining erased mappings while keeping kiosk/lease checks; and the
shared barrier restores the pinned admission inode's current SELinux label
before preflight refusal, including failed-relabel retries. Fresh review of the
final revisions found no actionable issues: **Usability priority: passed;
Threat scope: passed; ownership/lifecycle and unselected boundary: passed**.
Review supplies no host or installed acceptance credit.

Parallelism review retains the compatible `package_configuration` classification.
Fixtures use private pytest trees, process-local NSS/policy doubles, real private
locks/xattrs and bounded, explicitly owned child processes. Scratch leases reach
the embedded finalizer and mapping child; cleanup signals only the owned child
and waits. No shared account, service, bus, display, host PAM/cache or additional
cleanup/UI inventory is changed. The rationale lives in `regression_unit.py`.

Host acceptance passed with no declared targets: **1,559 checks passed** in the
[final host report](../../output/test-runs/host/plans/9e6d398945018fab1240008bd0d1c27837ea1d8065b0d73abfbe70631ec42477/accepted-evidence.json),
using the maintained unit selection and a 600-second worker deadline. The
selection covers package configuration/removal, provisioning, activation,
package inputs, both prepared-payload exclusions, RPM composition, support
architecture and unit inventory. Its 71 new migration cases include fresh,
configured, previous-publication, removing, pre-lease/reboot, interrupted/retry,
rollback, failed readiness, owned/foreign visibility, live kiosk negatives and
executed post-erase histories. Real bounded mapping children verify preservation
of ordinary workers across payload erasure. Native/service doubles supply no
installed SELinux, PAM, entry or update acceptance.

Final `make build` passed for both DEB and RPM after the last packaged edit.
Retained outputs are
`output/deb/oh-no-parent-control_1.4+local1~ubuntu26.04.1_amd64.deb`,
`output/rpm/oh-no-parent-control-1.4-0.1.dev.fc44.x86_64.rpm` and
`output/rpm/build.log`. Implementation and review agents are finished/closed;
host-runner, mapping-child and build cleanup completed. No task-owned VM,
installed state, temporary source artifact or live process remains. Normal
reports and package outputs are retained. No installation, staging, commit or
push was performed.

Three rotated C02b/C02c1 report destinations alone now use the accepted-proof
locator. The maintained bundle reader verified the original 639, 694 and 639
passing reports, exact command selections, accepted results and cleanup in
`onpc-evidence-bundle-ojo_nad1` (SHA-256
`7d49c9ea057908b70c9e56751297779a12c53f1204d830dd0e529bb4f5fa807b`).
Labels and historical claims are unchanged; this grants no new acceptance.

Close-out passed all **639 metadata checks**, including the four maintained
consistency modules and `test_execution_plan_launcher.py`, with the 600-second
worker deadline and completed cleanup; see the
[close-out report](../../output/test-runs/host/plans/9e6d398945018fab1240008bd0d1c27837ea1d8065b0d73abfbe70631ec42477/accepted-evidence.json).
Only C02c2 is newly checked, its temporary brief is removed, and the plan selects
C02c with 55 tasks remaining. All other queue status, order, scope and
prerequisites are preserved.

##### C02c prepared native and distro PAM integration

The prepared native module, `login_check.py`, `distro_pam.py` and two
`pam-configs` profiles live under `data/kiosk-runtime-unselected/`. They have
no production caller and remain outside package source, payload and activation
selection. C02 alone replaces the selected native module, helper and package
PAM transaction. The current selected path remains intact.

The native module reconstructs the pinned release's ordinary-user time-check
and graphical runtime-cap behavior, retaining main's separate session-limit
helper and administrative user-bus exception. Kiosk account/session dispatch
uses the release service boundary (`gdm-password` and `systemd-user`) with main's
public saved-session/Wayland checks. Other users bypass kiosk routing without
querying another account. Vendor authentication, account denials and credential
callbacks retain their ordering and authority; no password exemption or
manager-credential projection is added.

A small shared flock on the existing admission inode lasts until `pam_end`,
including root executor teardown and a bounded routing helper's lifetime. It
preserves C02c2's removal/migration exclusion without importing old confinement
headers, MAC policy, private generations, callback inventories or admission
protocols. The helper uses a fixed environment and public AccountsService
properties. A repaired default still refuses that attempt; required-service
failure remains an operational failure. Optional assets and unrelated native
modules have no admission vote.

The distro transaction retains Ubuntu's public `pam-auth-update` route, original
Malcontent selection and local-edit handling, and the maintained Fedora
authselect owner's original profile/features, owned-file checks and restoration.
It never forces local PAM replacement. Configuration readiness checks the finite
product-owned authentication/account blocks, including their skip targets,
administrative bridge, Malcontent and following runtime-cap hook. Their numeric
skip rules require the relevant same-type entries to stay together and ordered;
one bounded logical-line reader handles PAM continuations and comments for
every check. Unrelated vendor content outside those blocks remains opaque. Shared
time/account skip rules remain unchanged; Fedora composition substitutes `wheel`
for `sudo`. Removal verifies
that effective shared stacks no longer reference product PAM payload before
allowing payload deletion.

C02 must install the prepared native/helper/account/session payload, restore
the old owned `gdm-password`/`systemd-user` originals under quarantine, and
activate the shared distro profiles before passing
`lambda: distro_pam.runtime_ready(distribution)` to
`commit_migration`. The callback reads effective shared PAM output and required
installed native/helper availability, returns `None` on success, and mutates
neither PAM nor account state. The lifecycle independently rechecks its original
PAM and quarantine before retiring old records and releasing the account.
Rollback keeps that quarantine while restoring the former integration through
the retained lifecycle owner. C02d/C02e then remove unconsumed legacy native,
helper, hook and package wiring; this preparation deletes no installed state.

**C06a route handoff:** saved AccountsService defaults and PAM's actual Wayland
transport do not prove GDM's selected next executable. The historical PreSession
hook is unused here and is not current-GDM proof. Actual desktop/session-choice,
TTY, SSH and supported remote-desktop histories, with ordinary-account controls,
remain unclosed under their existing queue scope. Shared profile composition and
host PAM fixtures provide no installed passwordless-entry, authentication or
route-confinement acceptance.

Independent Astra xHigh review resolved a P1 readiness gap by requiring complete
ordinary-user time-policy blocks before migration can retire recovery records,
and a P2 usability gap by using the same PAM logical-line normalization for
direct rules, owned blocks and removal references. Fresh review found no
actionable issues: **Usability priority: passed; Threat scope: passed;
ownership/lifecycle and unselected boundary: passed**. The review grants no host
or installed acceptance credit.

Host acceptance has no declared targets. The final prepared PAM, Fedora
transaction and real migration-readiness selection passed **187 checks** with
a 180-second worker deadline; see the
[focused report](../../output/test-runs/host/plans/9e6d398945018fab1240008bd0d1c27837ea1d8065b0d73abfbe70631ec42477/accepted-evidence.json).
It includes 139 native/routing/distro cases, 32 migration composition cases and
16 Fedora owner/facade cases. Missing or reordered required rules retain
quarantine/recovery records; restored rules permit retry, and legacy rollback
still works. Both distros accept equivalent continued/commented rules without
accepting wrong module prefixes or commented-out policy.

The final affected regression selection passed **676 checks** with a 600-second
worker deadline; see the
[regression report](../../output/test-runs/host/plans/9e6d398945018fab1240008bd0d1c27837ea1d8065b0d73abfbe70631ec42477/accepted-evidence.json).
It covers selected native/login behavior, graphical runtime caps, shared time
checks, package configuration/removal, unit scheduling and both prepared-payload
exclusions. Tests compile the prepared native code and exercise private PAM
configurations; production selection remains unchanged. Host doubles do not
qualify installed entry, parent authentication, real distro policy or updates.

The parallelism review classifies `prepared_kiosk_pam` as compatible unit work.
It owns private PAM configurations, native modules, admission files and bounded,
waited compiler/helper children; account, bus and command doubles are process
local. The existing Fedora and package-configuration fixtures supply private
authselect and migration/rollback composition, with scratch leases forwarded to
native compilation. No shared account, PAM, service, bus, display, cache or VM is
changed. Cleanup and UI inventories gain no resource owner. The classification
and rationale are recorded in `tools/regression_unit.py`.

Final `make build` passed for both DEB and RPM after the final source edits.
Retained outputs are
`output/deb/oh-no-parent-control_1.4+local1~ubuntu26.04.1_amd64.deb`,
`output/rpm/oh-no-parent-control-1.4-0.1.dev.fc44.x86_64.rpm` and
`output/rpm/build.log`. These packages retain the selected production path;
the prepared PAM assets remain excluded. Implementation and review agents are
finished/closed, and test/build cleanup completed. No task-owned process, VM,
installed state or temporary source artifact remains. Normal reports and package
outputs are retained. No installation, staging, commit or push was performed.

Two C02c2 report destinations alone now use the accepted-proof locator. The
maintained bundle reader verified their exact original members, accepted result,
command record and completed cleanup in `onpc-evidence-bundle-q3vjgtzo` (SHA-256
`0c8fe82a5ac00a610267a3ca2b5fb973a0a3f9c1bdaa858282d0646a34d99d53`).
Their 1,559 and 639 passing checks remain historical claims, with no new
acceptance or predecessor completion change.

Close-out passed **639 metadata checks** in the maintained consistency modules
and `test_execution_plan_launcher.py`, with a 600-second worker deadline and
completed cleanup; see the
[close-out report](../../output/test-runs/host/plans/9e6d398945018fab1240008bd0d1c27837ea1d8065b0d73abfbe70631ec42477/accepted-evidence.json).
Only C02c is newly checked, its temporary brief is removed, and the master
selects C02 with 54 tasks remaining. Every other row's status, relative order,
scope and dependencies are preserved.

##### C01 selective replacement boundary

C01 combines the C01a/C01b/C01c inventories below into the implementation
boundary. The release source is exactly
`188be907c46b1cd0dabae06ac898c43e75beb05e`; the reviewed main input is
`5968a3d10d073d6f4a9a0d13a209f340a3d7b209`. At C01 entry,
`git status --short` was empty. The predecessor inventories and current source
agree: there is no separate staged, unstaged or untracked old-plan product delta.
Committed post-release confinement code is still a removal input. Documentation
edits in this task neither accept that code nor create a second product baseline.
Repeat the active-delta inventory at each implementation cutover.

The three dispositions are **reconstruct** the release session/account slice,
**retain** main's feature/policy behavior, and **remove** superseded confinement
mechanisms after their callers move. They apply at function/configuration level,
not whole-file level. The cumulative tables below supply the exact source,
caller, generated/package and test-consumer inventory for each decision here.

| Interface and provenance | Selected boundary and retained result | Receiving implementation/removal and direct test owners |
| --- | --- | --- |
| Release desktop/session/target/app/agent units; main native role launchers | **Reconstruct** dedicated GNOME Kiosk entry and session shutdown from the pin, invoking current main commands. **Retain** the current vendor agent, notification provider and shared logout behavior. **Remove** private wrapper/graph selection after coherent callers exist. The legacy PreSession hook cannot enforce current GDM routing. | C02a prepares; C02 activates; C02d/e remove obsolete launchers, hook and wiring. C01a unit rows and C01c package table own login/confinement/payload/RPM assertions; C03a finishes the audit. |
| Release account provisioner/login helper and shared PAM; main routing, quarantine, parser and MAC integration | **Reconstruct** only kiosk account/session integration, preserving effective administrator authentication/account denial and ordinary-user callbacks. **Retain** main UID/home ownership, public visible/saved Wayland routing, metadata/icon preservation, broker UID/bus configuration and shared child-time/runtime-cap/admin-bridge behavior. **Remove** exact vendor-module inventory/private admission assumptions, with owned state migrated before deletion. | C02c1 provisioning; C02c native/distro PAM; C02c2 migration; C02 cutover; C02d/e obsolete source/wiring. C01a/c enumerate provision, Fedora PAM, session-limit/runtime-cap, package configuration/removal and installed cases 4/5/6–25/283–286. |
| Main-only fresh/retained native graph, preparation/material/view/pin/receipt code, policy generator and helper substitution | **Remove**, including selectable synthetic/positional legacy branches, generated inventories/overrides/masks, includes and probe consumers. Do not make this graph or a custom loader the new baseline. **Retain** bounded work, original useful causes, identity-safe owned cleanup and genuine required isolation as outcomes. Trust supported installed Python/GTK/GI and vendor helpers. | C02a/c/c2 prepare replacement responsibilities; C02 disconnects all live selectors without a legacy fallback; C02d removes runtime/native source; C02e remaining protocols/wiring. C01a header/Python rows and C01c fixture/registration closure bind immediate repairs; C03a1/a audit residuals; C04a ports installed engineering consumers. |
| Shared main launcher/form/agent locale, preferences, selections, durations/presets, notifications/Wellbeing, What's New, artwork and feedback | **Retain** main features, current exposed-action restrictions, request drafts and separate kiosk/overlay identities. Locale restart/job ownership and `KioskLogout` are real service/lifecycle behavior, not private receipts. **Remove** only proven unconsumed confinement launch plumbing; keep ordinary-user Wellbeing/audio and RPM diagnostics callers. | C02a preserves commands; C02b adapts form/agent consumers coherently; C02d/e remove wrappers after every shared caller moves. C01b feature rows and C01c UI/preview/worker closure own focused repairs; C03 audits both surfaces, C04b/u/f map and qualify changed public operations. |
| Main broker `RequestAccess(uuub)→(ss)`, `RequestOwnAccess(uub)→(ssu)`, role/target checks, Polkit and account transaction | **Retain** current public signatures, caller validation, selected-parent authentication, pending cancellation, no late revival/duplicate dispatch, time arithmetic, hard/soft app behavior, cooldown and rollback limits. There is no visit-token API, controller or final visit validation in this input. Preserve required lifetime outcomes without importing the superseded visit/receipt design. | C02b1 owns producer/lifetime adaptation and C02b its form/agent callers; C02e may delete only demonstrated obsolete consumers. C01b exact interface/cancellation handoff and C01c broker tests bind unit/component/system repairs; C03b audits, C04 qualifies changed installed operations. |
| Main Makefile source lists/install rules, activation manifests, DEB/RPM payload, lifecycle templates and embedded finalizer | **Retain** main packaging improvements and feature assets. **Remove** obsolete source/generated members and install/removal dependencies together. **Migrate** original/generated PAM, quarantine/visibility and removal records before retiring old integration; source deletion never authorizes installed-state deletion. | C02c2 prepares configure/upgrade/abort/remove/post-erase/retry ownership; C02 activates; C02d/e close source and generated/embedded wiring. C01c package/state tables are the exact checklist; each product slice repairs direct tests before C03/C04 audit. |
| Main host fixtures, registered cases, copied workers, frozen guest inputs and proof consumers | **Retain** customer behavior, stable case IDs, ordinary-use positives, genuine enforcement failures, original diagnostics and restoration. **Remove/port** discarded graph/receipt/material assertions and registrations, including generated fixture text and transitive imports. Current registration or an unchanged callable name grants no changed-candidate qualification. | C03a1/a/b/C03 host audits; C04a engineering closure; C04b baseline composition; C04u/f changed entry/approval qualification; C04c proof/design consumers; C04 readiness. C01c names exact modules, helpers, IDs, copied worker routes and qualification-input identity. |

No whole-file release restoration is permitted for `Makefile`, `provision.py`,
the native PAM module, distro integration, shared frontend or broker. Preparation
tasks keep the selected production route coherent and buildable; only C02
switches entry/PAM/package activation. It also removes temporary live adapters;
C02d/e finish unconsumed source deletion before C03. This sequencing does not
permit broken direct test consumers to wait for an audit task.

###### Behavior and prospective-design resolution

The request station and child overlay continue to share main's form and policy
semantics under the [specification](../Specification.md#requesting-and-approving-access).
Human language selection, dialogs and parent authentication are not startup
deadlines. Cosmetic assets, translations, unrelated packages, ambient siblings,
unknown benign services and valid local PAM variation have no admission vote.
An actual essential-service/enforcement failure remains an operational fault
with safe retry/exit; genuine parent or administrator denial remains authoritative.

The historical frontend report is inapplicable to this input: `_load_stylesheet`
has no fallback, `agent_environment` refuses C-only locale inventories, and no
final visit validation exists. Frame presentation only records timings. Retain
real account/preference/language readiness, stale callback guards, request
snapshots and single-flight serialization. C09a owns optional stylesheet/native
language fallback; C02b preserves features during decoupling without claiming
those gaps fixed. No missing historical edit is a new C01 prerequisite.

The [broker's audited gap](Broker.md#audited-implementation-gap) was an input to
C02b1: authentication completion dropped lifecycle cancellation before
usage/preflight and the first write, while sender survival did not prove session
activity. C02b1 prepares the compatible scoped approval boundary; C02b preserves
the form/agent result and fresh-request ownership through its caller adaptation.
The customer lifetime requirements in the
[specification](../Specification.md#prospective-kiosk-visit-lifetime) survive;
the old controller, receipt, effect-admission protocol and exact private graph
do not become mandatory architecture. C01 grants no implementation acceptance.

###### Remaining route review and proof consumers

C06a must inspect actual current GDM selection/final execution, desktop/TTY,
SSH and the named supported remote-desktop provider. Saved session properties,
`nologin`, the historical PreSession hook, a PAM refusal probe or an absent
remote service alone cannot qualify all those routes. Pair each proposed denial
with a working ordinary-account/permitted-station control on each target.
For the personal child, `session_limit_check.authentication_outcome` adds an
authentication-time check only for `gdm-password`; other services depend on
their account stacks, and runtime-cap clearing is restricted to `gdm-*`.
Inspect those actual stacks and retained sessions; this source observation
establishes neither a bypass nor successful enforcement on alternate routes.
C06 must inspect Overview/terminal shortcuts, About/Preferences/feedback links,
choosers, handlers and automatic activation, then actual child-writable consumed
startup/settings/module/plugin inputs. Distinguish personal-child and kiosk
identities and effective group/ACL/ancestor write authority. An injected arbitrary
kiosk executable or writable root fixture does not establish child reachability.
No new blacklist, private image or general loader architecture is selected here.

C04c owns remaining external prospective copies in
[Lifecycle](Lifecycle.md#prospective-configuration-and-activation-recovery),
[Broker](Broker.md#prospective-kiosk-approval-lifetime), the
[native-language fallback decision](Localization.md#r01e-native-authentication-fallback-decision), the
[standalone proof catalogue](../Kiosk-Confinement-Proof.md#evidence-scope) and
the [reliability plan](../Reliability-Plan.md#task-boundaries-after-audit).
The C01c installed-consumer table is its finite handoff: reliability 006a/006b
and cases 290/291 retain useful compatibility/consumed-input outcomes; 008a/008c
retain actual locale/job/cancellation outcomes; cases 292–294 and proof scenarios
13–32 lose mandatory private-view/material/generation mechanisms. C04c also
checks catalogue, recipes and coverage claims against the changed operations.
It preserves original historical candidate claims and known proof loss, and
closes no other plan's row. Compatibility anchors in this owner carry no retired
architecture obligation. Current implementation descriptions stay accurate until
their product cutover; retained runner evidence/checkpoints/VM baselines remain
under their existing owners.

###### Sizing and acceptance boundary

The broad native removal closure, mutually generated fresh/retained fixtures,
mixed 7,300-line confinement test, shared non-kiosk wrapper callers, copied guest
workers and embedded package finalizer are sizing risks. Lifecycle migration
must cover configured, partial publication, removing, account-absent/post-erase,
legacy-prelease, expiry and visibility recovery states without adopting live or
foreign state. C02b1's post-authentication gap requires precise concurrency and
result ownership review. These risks do not resize later rows; a selected
consumer inserts a bounded prerequisite only if it proves independent work is
needed. No prerequisite is needed for this source/design review.

C01 acceptance is review only, with no targets. It changes documentation only;
no product, tests, generated inputs, installed state or qualification is changed.
Independent Astra xHigh review passed with no actionable findings: **Usability
priority: passed; Threat scope: passed; provenance and feature preservation:
passed**. It confirmed coherent native/runtime, shared-helper, generated-package,
embedded-finalizer and test-consumer closure. The post-authentication lifetime,
optional fallbacks, actual route proof and external prospective copies remain
with the named receiving tasks above, without inherited acceptance.

Markdown links, plan structure and the four maintained host consistency modules
plus `test_execution_plan_launcher.py` passed. The same 639 checks passed again
after advancing the pointer, with owned cleanup complete in the retained
[final runner report](../../output/test-runs/host/plans/9e6d398945018fab1240008bd0d1c27837ea1d8065b0d73abfbe70631ec42477/accepted-evidence.json).
The plan check selects C02a with 60 remaining tasks. Concurrent commit
`484e38ea` changes only launcher instructions/tooling and its tests, leaving
the reviewed product inputs unchanged. These docs are outside package/build inputs;
no build or installed result is required or
claimed. All source/edit/review agents finished; the maintained runner ended its
owned cleanup. No task-owned VM, installed state, temporary file or live process
remains. Concurrent unrelated launcher/test edits are preserved and excluded
from this task's owned paths.

##### C01a session source lineage

Source review on 2026-10-20 compared the exact release commit
`188be907c46b1cd0dabae06ac898c43e75beb05e` with checked-in HEAD
`8755a6709bb06807d4e7267737c0b963f73da2d7`. Both objects resolve locally;
the release pin, rather than the branch tip, supplies the release column below.
At entry, `git status --porcelain=v1 --untracked-files=all --ignored=no`,
`git diff --name-only --cached`, `git diff --name-only` and
`git ls-files --others --exclude-standard` were empty. Thus there is **no active
staged, unstaged or untracked old-plan source delta in this checkout**. The
post-release confinement mechanisms below are committed cleanup inputs, not
accepted replacement work. This inventory does not recreate absent old-plan work.

In particular, there is no tracked or working startup replacement, native agent
or session controller corresponding to `kiosk_startup_open`. The leftover
`data/kiosk-runtime/session-services` and `data/kiosk-runtime/user-units`
directories contain no files; they supply no graph or package input. Current
generated user-unit overrides and D-Bus masks come from
`tools/kiosk_confinement_policy.py`, not that tree. The historical R02a report in
[verification limits](#verification-scope-and-evidence-limits) must not be used
as a current source map. Production still selects fresh/retained private views.
Likewise, “unwired” comments on `required_material` and `InitialPreparation` in
the Python helper are stale: the production preparation service calls them.

All rows below have an empty active delta. “Added” means absent at the release
pin and present in committed HEAD. Actions name receiving tasks already in the
[queue](../Kiosk-Prompt-Queue.md), not changes made by this review or a final
protection design. C01b owns full feature/approval classification; C01c owns the
complete package and automation consumer audit; C01 decides the combined boundary.
Test owners identify source consumers, not tests run or acceptance transferred.

| Release source / functions | Checked-in equivalent and confinement responsibility | Required behavior / main feature to preserve | Disposition and receiving task; direct test owner |
| --- | --- | --- | --- |
| `data/wayland-sessions/oh-no-parent-control.desktop`: direct `gnome-session --session oh-no-parent-control`; `data/gnome-session/sessions/oh-no-parent-control.session`: `Kiosk=true` | Same desktop now selects `/usr/libexec/oh-no-parent-control-kiosk-session`; `.session` still selects the dedicated GNOME Kiosk session without XDG autostart. `tools/kiosk_session.c:main` clears the startup environment and executes `gnome-session --no-reexec --session=oh-no-parent-control`. | Passwordless dedicated request station, compositor and shared form; no ordinary desktop launch. | Reconstruct release session entry in C02a; C02 activates it; C02d removes superseded wrappers after consumers move. `tests/unit/test_kiosk_login.py`, `tests/unit/test_kiosk_confinement.py`. |
| `data/systemd/user/gnome-session@oh-no-parent-control.target.d/session.conf`, `oh-no-parent-control-app.service`: compositor/app required, agent wanted; direct `/usr/bin/oh-no-parent-control` | Target adds notification service and Apport conflicts. App invokes native `app` role, which runs `/usr/bin/python3 -I /usr/bin/oh-no-parent-control`; shutdown/exit integration remains in the app service. | Current request UI, language, preferences, diagnostics, notification presentation and successful/cancelled exit; preserve main's app implementation. | C02a prepares session wiring; C01b classifies feature commands; C02 switches and C02d/e remove obsolete launch/wiring. `tests/unit/test_kiosk_login.py`, `tests/unit/test_kiosk_confinement.py`, `tests/unit/test_package_configuration.py`. |
| `data/systemd/user/oh-no-parent-control-polkit-agent.service`: forking `/usr/bin/mate-polkit`; release Fedora staging already substitutes the native vendor agent | Shared HEAD unit is `Type=simple`, directly running `/usr/libexec/polkit-mate-authentication-agent-1`; retains environment-file, ordering and restart integration. No new product-native agent exists. | Genuine vendor authentication and selected-parent presentation; a running unit alone proves neither registration nor approval. | C02a/C02b preserve the authentication path; C01b follows `KioskAgentLocale` and approval callers; C02e retires obsolete coupling. `tests/unit/test_kiosk_login.py`, `tests/unit/test_rpm_packaging.py`. |
| No release notification/Wellbeing units or native role launcher | Added `oh-no-parent-control-notifications.service`, `oh-no-parent-control-wellbeing.service`, `data/dbus-1/services/com.puffyslippers.OhNoParentControl.Wellbeing.service`; `kiosk_session.c:main` also implements `notifications`, `notification-client`, `wellbeing`, `cleanup`, `audio`, `packages`, `dbus`. Compositor/WirePlumber drop-ins select fixed cleanup/audio paths. | Main notification/reminder and Wellbeing behavior, package diagnostics, ordinary-user audio/Wellbeing environment. The audio/Wellbeing roles explicitly bypass kiosk environment filtering for other UIDs. | C01b maps feature calls; C02a adapts required entry commands; C02d/e delete confinement-only wrappers/drop-ins after replacement, without deleting shared features. `tests/unit/test_kiosk_confinement.py`, `tests/unit/test_kiosk_rendering.py`; C01c completes registration coverage. |
| `tools/oh-no-parent-control-login-check`: shell allow for `gdm-password` / `systemd-user` | Isolated Python `main`, `read_session`, `verify_session`, `verify_confinement`, `busctl`: checks native integration and saved/actual Wayland routing, repairs an incorrect saved preference and denies that attempt. Called by native `run_kiosk_check` for account, session and integrity modes. | Dedicated account routing, ordinary-account independence, bounded diagnostics and retry after repair; this helper does not authenticate passwords or evaluate arbitrary PAM policy. | C02c1 prepares account/routing, C02c prepares PAM callers, C02 activates; C02d/e remove obsolete integration checks. `tests/unit/test_kiosk_login.py`, `tests/unit/test_fedora_pam.py`. |
| `data/gdm3/PreSession/Default`: checks `USER`/`LOGNAME` and `GDMSESSION` | Identical file at both commits; still packaged as the historical GDM hook. It is not the current native entry boundary; GDM 50 does not invoke it and `GDMSESSION` is too late for PAM selection. | Dedicated session routing, rather than entitlement to preserve a nonfunctional hook. | C01c accounts for install/removal wiring; C02 selects actual entry and C02e removes unconsumed legacy wiring. `tests/unit/test_kiosk_login.py`, `tests/unit/test_package_configuration.py`, `tests/unit/test_package_removal.py`; [lifecycle owner](Lifecycle.md#startup-login-and-update-lifecycle). |
| `tools/provision.py`: `account`, `atomic_write`, `accounts_service_user_path`, `accounts_service_set_icon_file`, `main` | Same shared file adds `accounts_service_set_kiosk_session`, `accounts_service_provision_kiosk`, `accounts_service_cache_kiosk`, `repair_kiosk_visibility`, visibility transaction/recovery/version checks, and `configure_account_access` / `kiosk_account_expiry` / `_configuration_account_record`. Owns saved visible Wayland account, UID/home/admin-group validation and expiry quarantine. | Passwordless package-owned account, retained metadata/custom icon, public AccountsService routing, disabled kiosk time limits, broker `kiosk_uid` configuration and ordinary accounts. Do not restore this whole file from release. | C02c1 prepares selective provisioning; C02c2 handles quarantine/visibility state migration and owned rollback; C02 activates. `tests/unit/test_provision.py`, `tests/unit/test_package_configuration.py`, `tests/unit/test_system_first_configure.py`, `tests/unit/test_system_kiosk_accounts.py`. |
| `data/pam-configs/oh-no-parent-control-kiosk-only`: account `pam_exec` login check; shared session-limits profile and native child-time module already exist | Kiosk-only profile now requires native `kiosk` in account and session groups. `packaging/fedora_pam.py:configure`, `selection`, saved authselect ownership remain; HEAD `verify_pam` requires both native stages and excludes the old helper. `stage_distribution.py:pam_profile`, `pam_stack` generate the distro stack. | Shared Malcontent/time checks, administrator/kiosk skips limited to product modules, original authselect profile/features and ordinary authentication policy. | C02c selectively reconstructs kiosk integration; C02 activates; C02e cleans obsolete wiring. `tests/unit/test_fedora_pam.py`, `tests/unit/test_pam_runtime_cap.py`, `tests/unit/test_session_limit_check.py`, `tests/unit/test_rpm_packaging.py`. |
| `tools/pam_oh_no_parent_control.c`: `run_session_limit_check`, account `systemd.runtime_max_sec=infinity` for graphical services; no kiosk-specific native branches | Adds `kiosk_identity`, `kiosk_account_check`, `run_kiosk_check`; `pam_sm_acct_mgmt`, `pam_sm_open_session`, `pam_sm_authenticate`, `pam_sm_setcred`, `pam_sm_close_session` dispatch kiosk account/session/integrity/admission/confinement/manager-credentials modes. Routing and admission leases live in PAM data and their destructors. | Ordinary child login/unlock time enforcement and graphical runtime-cap clearing, non-graphical limits, normal credential no-ops; keep separate from kiosk replacement. | C02c prepares selective native branches; C02 cutover; C02d deletes obsolete includes/branches after all consumers move. `tests/unit/test_kiosk_login.py`, `tests/unit/test_pam_runtime_cap.py`, `tests/unit/test_session_limit_check.py`. |
| `tools/session_limit_check.py`: `main`, `is_confirmed_unrestricted`, `authentication_outcome` already implement the shared account skip / graphical authentication-time check | HEAD adds `is_systemd_user_bus_bridge`: only real/effective root, exact `login` service, verified non-kiosk account and public systemd transient-service properties can exempt the administrative user-bus bridge from the two product time modules. Native `run_session_limit_check` retains the authentication route; the PAM account profile calls the helper separately. | Ordinary child login/unlock checks and authenticated administrative bus access after time exhaustion; the bridge exception explicitly excludes kiosk and skips no other PAM policy. | C02c preserves this shared post-release behavior selectively; C01c follows both helper callers and distro-generated profile wiring. `tests/unit/test_session_limit_check.py`, `tests/unit/test_pam_runtime_cap.py`. |
| No release `packaging/kiosk_confinement.py` | Added `admission_barrier`, `pam_lines`, `validate_stack`, `guarded_sessions`, `audit_manager_credentials`, `rendered`, `verify_pam`, `install_locked`, `load`, `check_remove`, `remove`, `finish_remove`: exact vendor/generated PAM snapshots, module inventory/callback guards, locks, MAC policy attestation and durable removal denial/finalization. | Ordinary PAM callbacks/policy, safe owned installation/rollback/removal and useful causes. Exact module inventory/private admission protocol are mechanisms, not baseline behavior. | C02c prepares PAM replacement; C02c2 migrates owned records; C02 activates; C02d/e remove old source/wiring. `tests/unit/test_kiosk_confinement.py`, `tests/unit/test_package_configuration.py`, `tests/unit/test_package_removal.py`. |
| No release `tools/kiosk_confinement.h` | Added `kiosk_confinement` dispatcher, `kiosk_admission_transaction`, `release_kiosk_transaction`, locks/removal marker and native primitives. Production manager calls `kiosk_fresh_startup_until`; gate calls `kiosk_retained_startup_until`. Current transaction budget is 60 seconds, failed-cleanup budget five seconds. | Identity-safe admission/lifecycle ownership and useful diagnostics; do not preserve private-view proof or its timeouts as new requirements. | C02c/C02c2 prepare replacement entry/cleanup, C02 disconnects, C02d removes old machinery. `tests/unit/test_kiosk_confinement.py`, `tests/unit/test_kiosk_login.py`. |
| No release fresh/retained native transactions | Added `kiosk_fresh_startup.h:kiosk_fresh_startup_until`, `kiosk_retained_startup.h:kiosk_retained_startup_until`; `kiosk_manager_admission.h:kiosk_manager_acquire_until` / selection/recheck and `kiosk_retained_record.h:kiosk_retained_record_open_until` / recheck bind live manager and retained source. These are production dependencies, not merely regression probes. | Preserve legitimate repeated entry, foreign/live-session safety and owned cleanup, without inheriting manager-clone/source-generation requirements. | C02a/C02c/C02c2 prepare replacement responsibilities; C02 cutover; C02d removes these files and direct consumers. `tests/unit/test_kiosk_fresh_startup.py`, `test_kiosk_retained_startup.py`, `test_kiosk_manager_admission.py`, `test_kiosk_retained_record.py` in `tests/unit/`. |
| No release host/material/policy/view native graph | Added `kiosk_host_proof.h`, `kiosk_material_authority.h`, `kiosk_policy_authority.h`, `kiosk_preparation_plan.h`, `kiosk_native_realization.h`, `kiosk_view_receipt.h`, `kiosk_view_publication.h`: capture/recheck paths, decode and verify material/policy/plan, realize mounts and publish receipts. All are reached by fresh/retained startup. | Main feature code/assets remain available as ordinary installed inputs; exact cosmetic bytes, ambient inventory and private receipts are not required customer behavior. | C02d deletion inventory after C02; C03a1 reconciles mechanism assertions. Direct `tests/unit/test_kiosk_host_proof.py`, `test_kiosk_material_authority.py`, `test_kiosk_policy_authority.py`, `test_kiosk_preparation_plan.py`, `test_kiosk_native_realization.py`, `test_kiosk_view_receipt.py`, `test_kiosk_view_publication.py`. |
| No release preparation channel/private creation graph | Added `kiosk_preparation_channel.h`, `kiosk_preparation_child.h`, `kiosk_private_creation.h`: bounded descriptor/channel exchange, child lifetime and proven-new-object initialization, used by active preparation, pinning, publication and realization. | Ownership/identity-safe cleanup and no takeover of foreign objects; the channel/pin format itself is disposable. | C02c2 preserves necessary cleanup outcomes; C02d removes old graph/consumers. `tests/unit/test_kiosk_preparation_channel.py`, `test_kiosk_preparation_child.py`, `test_kiosk_pin_native.py`, `test_kiosk_pin_storage.py`, plus `test_kiosk_confinement.py` / `test_kiosk_login.py`. |
| No release Python preparation/material graph | Added `tools/kiosk_confinement.py:main` → `prepare_native_channel` → `native_preparation_service` → `kiosk_preparation_service.py:serve` → `measure` / `required_material`; manager uses `InitialPreparation`, gate uses `retained_plan`, `RetainedSourceProjection`, `select_retained_material`. `kiosk_preparation_input.py:PreparationExchange` and `kiosk_view_receipt.py` supply exchange/receipt formats. `runtime_input_specs` includes exact code, units, cosmetic assets and catalogues. | Preserve feature payload, normal system loading, optional presentation fallback, bounded errors and cleanup. Do not carry global runtime inventory or cosmetic admission votes into release reconstruction. | C02d removes old preparation/material/copy/receipt code after C02; C03a1 audits tests. `tests/unit/test_kiosk_preparation_entry.py`, `test_kiosk_preparation_service.py`, `test_kiosk_preparation_child.py`, `test_kiosk_preparation_channel.py`, `test_kiosk_required_material.py`, `test_kiosk_initial_realization.py`, `test_kiosk_retained_projection.py`, `test_kiosk_material_selection.py`, `test_kiosk_rendering.py`. |
| No release legacy private binding or bubblewrap replacement | `kiosk_confinement.h:prepare_kiosk_confinement`, `bind_kiosk_executables`, `apply_kiosk_mac` and old protocol parser remain for direct/synthetic probe consumers, outside the current dispatcher. Python `prepare(role)` remains a selectable positional CLI branch. Added `tools/kiosk_bwrap.c:main` substitutes a private executable view for the vendor sandbox helper. | Main in-app report editor/media capability and genuine authentication must survive; neither old probe protocol nor private bubblewrap substitution is a feature. | C02d removes implementations and synthetic consumers after activation; C01b maps UI helper use and C01c inventories package/test inputs. `tests/unit/test_kiosk_confinement.py`, `tests/unit/test_kiosk_login.py`, `tests/unit/test_kiosk_rendering.py`; installed `tests/integration/system_kiosk_confinement.py`. |
| No release confinement policy generator or loader service | Added `tools/kiosk_confinement_policy.py:executables`, `routes`, `apparmor`, `selinux`, `generate`; `data/systemd/oh-no-parent-control-kiosk-confinement.service` calls the integration loader. Generates roles, policy, config, private user-unit overrides and session-data D-Bus masks consumed by both preparation and lifecycle. | Actual required isolation and supported vendor privilege path, ordinary-account services and feature availability; generated graph is not a release baseline. | C02c/C02c2 prepare required integration/migration, C02 activates, C02d/e delete obsolete policy definitions and wiring. `tests/unit/test_kiosk_confinement.py`, `test_kiosk_rendering.py`, `test_package_activation.py`, `test_package_payload.py`; C01c completes build/install/removal inventory. |

The complete current native route is PAM kiosk identity/options → admission and
routing leases → `kiosk_confinement` → manager fresh / gate retained transaction
→ native channel child and Python `serve` → measured material and selected plan
→ native realization/publication and final MAC operation. The PAM-owned
transaction retains unresolved cleanup ownership; ordinary PAM paths do not
enter that graph. Whole-file rollback of the PAM module, provisioner, frontend,
Makefile or distro integration would cross the required feature boundary.

##### C01a cross-component handoff and open questions

- **C01b:** follow native roles into `kiosk/oh-no-parent-control`,
  `oh_no_parent_control_kiosk.main`, `notifications.py`, `agent_locale.py`
  (`KioskAgentLocale`, `polkit-agent.env`, `RestartUnit`/`JobRemoved`),
  `session_logout.py` and `child/wellbeingService.js`. Trace the current broker
  `RequestAccess` / `RequestOwnAccess`, account/language and diagnostic methods
  independently of historical visit/controller proposals. Determine which current
  launcher/agent checks are feature requirements and which are obsolete
  confinement coupling. C01a supplies no approval-protocol decision.
- **C01c:** start at `Makefile:PACKAGE_SOURCE_FILES`, `PRODUCT_USER_SERVICES` and
  `_install-product-files`: the native role builds, PAM shared object, installed
  `oh-no-parent-control-kiosk-{confinement,support,confinement-integration}` and
  generated `share/oh-no-parent-control/confinement` are actual inputs. Follow
  `packaging/render_lifecycle.py` (including `embedded_confinement_finish_remove`),
  `stage_distribution.py:pam_profile` / `pam_stack`, distro fragment tokens
  `pam_restore`, `pam_enable`, `pam_remove`, `create_account`, and
  `package_activation.py` rather than treating empty `data/kiosk-runtime` as a
  payload. Map copied/generated definitions as well as direct source imports.
  Installed consumer entry points include `tests/integration/system_kiosk_confinement.py`,
  `system_kiosk_admission.py`, `system_kiosk_platform.py`, `system_kiosk_scope.py`,
  `system_kiosk_required_history.py`, `system_kiosk_ambient_history.py` and
  `system_pam_variants.py` in that directory; preserve their customer outcomes
  separately from private-implementation assertions.
- **C02c1/C02c2:** account state includes the UID marker
  `/var/lib/oh-no-parent-control/package-created-kiosk-uid`, the UID-bound
  `kiosk-configuration-account.json` expiry transaction, AccountsService's fixed
  `.onpc-kiosk-visibility-v1` slot/xattr and the ignored-failure start-pre repair
  drop-in. Decide selective state migration with the existing
  [lifecycle](Lifecycle.md#startup-login-and-update-lifecycle) and
  [removal](Package-Removal.md#pam-and-kiosk-ownership) owners; do not delete
  installed records as source cleanup.
- **C02c/C02c2:** integration state `kiosk-confinement.json` records original and
  generated PAM bytes, backend, kiosk UID, admission protocol and optional
  previous/removing/prelease-boot fields; `kiosk-confinement-removing` and
  `fedora-authselect.json` protect removal/profile restoration. C01c must map
  postinst install/release ordering, prerm check/remove and postrm embedded
  finalization. Preserve foreign edits and ordinary-user policy during cutover.
- **C01:** settle reconstruction versus retention at the shared PAM, launcher,
  provisioner and policy-generation functions only after C01b/C01c. Source
  absence is established, not a missing runtime prerequisite: no startup graph,
  native controller/agent or `kiosk_startup_open` implementation can be retained
  from this checkout. The current private graph's breadth is a sizing/removal
  risk, not permission to import it into the new baseline. Later protection
  review must justify actual child-accessible routes separately.

C01a acceptance is source review only, with no declared targets. It changes no
product code, protection design, generated inputs or installed state. Usability
priority: **passed**; Threat scope: **passed**, for the lineage/disposition scope.
Independent GPT-6.1 Sol High review passed after correcting the PreSession test
owners and adding the shared session-limit helper's lineage and administrative
bridge behavior. No actionable review findings remain. No product or installed
acceptance is claimed. All read-only source/review agents finished; no task-owned
processes, VMs or temporary source artifacts require cleanup.

##### C01b feature and approval source lineage

Source review on 2026-10-20 compared release
`188be907c46b1cd0dabae06ac898c43e75beb05e` with checked-in HEAD
`235f76839b7b4442c5a26d5ea89c43c87b9f51ea`. The same four Git inventory
commands recorded in C01a were empty at entry: **no staged, unstaged or
untracked old-plan source additions exist in this checkout**. All post-release
changes below are committed main source, not accepted replacement work. There
is no separate active implementation to retain or remove. Later consumers must
repeat that inventory if their inputs change.

This extends C01a's table, with feature behavior owned by
[Front ends](Frontends.md#main-flows), [Localization](Localization.md#responsibilities-and-language-ownership),
[Broker transactions](Broker.md#authorization-and-grant-transactions) and the
[specification](../Specification.md#request-station). It maps source and future
disposition, not a new protection design or installed qualification. Test paths
identify consumers for C01c, not checks executed or reusable live evidence.

| Release source / interface | Checked-in main responsibility and callers | Retained behavior / disposition and receiving task | Direct test consumers for C01c |
| --- | --- | --- | --- |
| `kiosk/oh-no-parent-control` imports `main`; child alias inserts `--child-overlay` | Same dispatch, now isolated Python shebang; native `app` role calls it with `python3 -I`. `main.py:main`, `Application.do_activate` / `do_command_line` and `RequestWindow` own startup and request lifecycle directly. HEAD adds `--preferences` and the Preferences action; `child/extension.js:_showRequest` opens the overlay, and `ChildErrorHandler.report` uses `--error-report-stdin`. | Retain one shared form, error-report entry and separate kiosk/overlay application identities. C02a/C02b adapt entry commands selectively; C02 switches them; C02d/e remove superseded wrappers only after their callers move. | `tests/unit/test_kiosk_login.py`, `test_package_payload.py`, `test_kiosk_rendering.py` in `tests/unit/`; `tests/ui/test_request_form_component.py`. |
| No `controller.py`, `startup.py` or `kiosk_visits.py` at either pin | None tracked or present in the working source. Neither broker XML nor form implements visit registration, startup receipts, `AdmitKioskSession` or a final visit-validation call. Startup frame timestamps are diagnostics, not admission votes. | No fictitious protocol deletion or historical implementation acceptance. C01/C02b1/C02b must start from the actual direct request/agent interfaces below, and preserve required cancellation/identity outcomes without importing the old proposed protocol. | `tests/unit/test_request_time_estimate.py`, `test_service_contract.py`; C01c reconciles historical-only claims separately. |
| `main.py` request callbacks and `model.py:RequestState` already serve both surfaces | `_request_access`, `_preferences_saved`, `_agent_prepared`, `_request_done` validate, snapshot and serialize one request; the saved tuple fixes child, approver, duration and soft-app choice. `RequestContent.selected` rejects invalid custom values before save/authentication. | Retain single-flight, disabled pending edits/Cancel, silent authentication cancellation, denied retry, error reporting and three-second success exit. C02b preserves this pipeline while adapting C02b1's coherent broker boundary; no UI/backend interface may dangle until C03. | `tests/unit/test_request_time_estimate.py`; `tests/ui/test_request_form_component.py`; `tests/component/test_authorization_lifecycle.py`; public `tests/e2e/restricted_station.py`. |
| `agent_locale.py:installed_locales`, `agent_environment`, `KioskAgentLocale.prepare` already exist | `main.py` warms the selected child's locale after language loads/changes and requires `prepare` before kiosk `RequestAccess`. HEAD queues required preparation behind warm work; revision checks suppress stale callbacks. Writes `%t/oh-no-parent-control/polkit-agent.env`, then systemd `RestartUnit(ss)->o` and matching `JobRemoved(uoss)` completion. Overlay skips this kiosk agent. | Retain selected-child language, genuine vendor authentication, finite restart/error handling and owned subscription/timer disposal. This is ordinary locale/service integration, not an obsolete visit protocol. Unit completion alone does not prove agent registration. C02a/C02b preserve it or provide equivalent coherent wiring; C02e removes only unconsumed coupling. | `tests/unit/test_request_time_estimate.py`, `test_systemd_unit.py`, `test_kiosk_login.py`, `test_rpm_packaging.py`; `tests/ui/test_language_settings.py`. |
| Language chooser, request choices, selection store and shared duration validation exist | HEAD replaces kiosk `language_dialog.py` with `preference_dialog.py` (compatibility `LanguageDialog`), adds `duration_controls.py` / `preset_dialog.py`, custom minutes/hours, editable presets and reminders. Main follows selected-child language context; overlay uses own account/language. `selection_store.py` keeps OS-user child/approver defaults separate from shared per-child choices. | Retain language/setup/Preferences, input drafts, custom units and exact durations, sorted presets, empty preset lists, selected-preset conversion to Custom and stale-selection guards. C02b changes only confinement coupling; no whole-file release restoration. State and localization APIs remain main's feature source. | `tests/unit/test_preferences.py`, `test_request_selections.py`, `test_request_time_estimate.py`; `tests/ui/test_language_settings.py`, `test_request_form_component.py`. |
| No release kiosk notification provider or reminder editor | `preference_dialog.py:ReminderDialog._preview` calls session-bus `org.freedesktop.Notifications.Notify(susssasa{sv}i)->u`, and `CloseNotification(u)` on disposal. `notifications.py:NotificationApplication` bounds content and owns one sender-bound banner, timer and `NotificationClosed(uu)`; its Preferences action calls the form's `org.gtk.Actions.Activate(sava{sv})`. Overlay preview uses `child/reminderPreview.js:PreviewLocalized`, not this provider. | Preserve actual reminder preview, localization, fullscreen urgency, dismissal and unsaved draft. Native `notification-client` → `gnome-service-client --tag=gnome-kiosk-notification` → `notifications` is launch plumbing, not the feature. C02a/C02b retain working commands; C02d/e remove obsolete wrappers/wiring after replacement; C03/C04 port only mechanism assertions. | `tests/ui/kiosk_notification_preview.py`, `test_language_settings.py`; `tests/unit/test_e2e_kiosk_notification_wellbeing.py`, `test_accessible_e2e_ui.py`, `test_kiosk_login.py`; C01c follows `tests/support/preview.py` and E2E registrations. |
| No release Wellbeing service/suppression modules | `child/extension.js` → `wellbeingSuppression.js` → `wellbeingService.js:SetWindow(sd)` on the user bus; sender/token-bound leases and persisted setting backup restore the original banner setting. The shared user unit and D-Bus activation run native `wellbeing`; ordinary users explicitly bypass kiosk environment filtering in `kiosk_session.c`. | Retain independent child reminder/Wellbeing behavior and recovery, without classifying leases for a personal notification setting as kiosk admission receipts. C02a/C02d/e must preserve shared activation and ordinary-user settings while replacing confinement-only launch plumbing. | `tests/component/test_wellbeing_service.py`, `tests/unit/test_package_payload.py`, `test_package_activation.py`, `test_e2e_kiosk_notification_wellbeing.py`; `tests/child/` notification/Wellbeing tests. |
| No release kiosk What's New coordinator/dialog | `main.py` uses `whats_new.py` / `whats_new_dialog.py`, shared release renderer/catalogues and role-specific broker query/acknowledgement. Both request surfaces share the child's acknowledgement and wait for language resolution. | Retain current-version visibility, language and acknowledgement behavior. C02b keeps feature code/assets; C02e removes only obsolete confinement inventory entries, never notes/translations as feature cleanup. No translation sync is authorized here. | `tests/unit/test_whats_new.py`; `tests/ui/test_language_settings.py`; `tests/unit/test_service_contract.py`. |
| Shared scene/artwork, About and error reporting already exist | HEAD adds lava cache/artwork generation and current layout/features. `REQUEST_MEDIA_ENABLED=False` keeps sound/lightning off and mute hidden. `GatewayBackground._load_texture` tolerates missing texture; font registration tolerates missing font; lava cache failure recomputes. `_load_stylesheet` directly loads `style.css`, with no fallback. | Retain main artwork/layout and current media state. Optional presentation cannot become an admission clock. C02b preserves features; C01 records actual fallback gaps for C09a rather than accepting the historical stylesheet-fallback claim. | `tests/unit/test_kiosk_rendering.py`, `test_automation_ids.py`; `tests/ui/test_request_form_component.py`, `test_request_layout.py`, `test_preview_smoke.py`, `test_language_settings.py`. |
| Kiosk hides external Help/About/file actions; shared feedback already exists | Main still supplies in-app About/error/report flows; shared `feedback.py` / `rich_text_editor.py` use the standard WebKit widget with blocked external navigation. `system_info.py:_rpm_dependency_info` calls the fixed native `packages` role for a bounded RPM query. `tools/kiosk_confinement_policy.py` / `kiosk_bwrap.c` substitute the private helper view; the editor itself has no private receipt API. | Retain drafts, diagnostics and normal vendor WebKit/Glycin/authentication support. C02b keeps exposed feature restrictions; C02d/e remove obsolete private-wrapper machinery only after functional consumers move, including shared RPM diagnostics outside kiosk. Keep useful sanitized original causes when retiring confinement-specific diagnostic parsing. | `tests/unit/test_system_info.py`, `test_e2e_kiosk_feedback_confinement.py`; `tests/ui/test_error_feedback.py`, `test_parent_feedback.py`; `tests/integration/check_e2e_kiosk_feedback_confinement.py`, `check_e2e_kiosk_preferences_confinement.py`; public `tests/e2e/kiosk_about.py`. |
| Main used direct session logout before post-release `session_logout.py` | `main.py` creates `KioskLogout.prepare` while idle, calls `begin` on exit, and closes it on destruction. `session_logout.py` uses GNOME SessionManager registration, logout signals and responses, with a 750 ms exit-action deadline; app-unit `OnSuccess`/`OnFailure` supplies shutdown fallback. | Retain Cancel/Escape and success returning to sign-in, overlay close without session logout, and cancelled external logout leaving the idle form usable. This is a public lifecycle helper, not a disposable private controller. C02a/C02b preserve coherent exit wiring. | `tests/unit/test_request_time_estimate.py`, `test_systemd_unit.py`; public `tests/e2e/kiosk_cancel.py`, `kiosk_escape.py`, `restricted_station.py`. |
| `authorization.py:PolkitAuthorizer`, `_PendingAuthorization` | Byte-identical release→HEAD. Selected-parent Polkit action, sender/session resolution, lifecycle subscriptions, remote/local cancellation, five-second kiosk challenge grace and bounded remote cleanup. `core.py:_request_access` is its production caller through `service.py` dependencies. | Preserve genuine selected-parent authentication and pending cancellation, original subject/cancellation ID, no late revival and no human authentication timeout. Do not delete role/session checks as confinement plumbing. C02b1 owns any compatible boundary adaptation and C02b its callers. | `tests/component/test_authorization_lifecycle.py`, `test_private_dbus_service.py`; `tests/unit/test_core.py`, `test_service_contract.py`; `tests/system/test_authorization.py`. |
| `core.py:request_access`, `request_own_access`, `_request_access`, `_apply` already exist | Main retains kiosk-only selected-target versus enabled-child own-target authority, eligibility/preference revalidation around authentication and usage, nonblocking shared transaction lock, UID cooldown only after success, fixed/rest-of-day calculation and verified app/time transaction/rollback. Post-release changes add feature settings, running-soft-app queries and shared policy improvements. | Retain main policy/grant/enforcement code, target-only termination, hard/soft behavior and rollback limits. C02b1 must separate actual session integration selectively, not restore core/service from release or remove validation because it precedes a grant. C02e deletes only proven unconsumed protocol code; no visit module currently exists. | `tests/unit/test_core.py`, `test_broker_properties.py`, `test_broker_state_machine.py`; `tests/component/test_private_dbus_service.py`, `test_authorization_lifecycle.py`; `tests/system/test_authorization.py`; public request/time/app cases traced by C01c. |
| `service.py` and installed `com.puffyslippers.OhNoParentControl1.xml` publish the same direct approval signatures | Service workers dispatch `RequestAccess` / `RequestOwnAccess` without visit tokens. HEAD adds custom-unit/presets/notifications/What's New and running-soft-app methods in both XML copies, diagnostic collection and policy adapter improvements. Role derivation, bounded inputs, diagnostics-only mode and role recheck before export remain separate from form availability. | Retain public API parity and all current feature/management callers. C02b1 owns producer changes, C02b consumers; C02e cannot remove a public method or copied/generated definition merely because historical prose called it a confinement protocol. C01c follows private-bus and packaging copies. | `tests/unit/test_service_contract.py`; `tests/component/test_private_dbus_service.py`; `tests/unit/test_package_payload.py`, `test_package_activation.py`. |

##### C01b concrete interface and cancellation handoff

The authority is the pair of executable `service.py:INTROSPECTION_XML` and
[installed XML](../../data/dbus-1/com.puffyslippers.OhNoParentControl1.xml), with
permissions in [Broker](Broker.md#broker-interface-and-roles). Relevant form
calls use these signatures (input → output; parentheses denote tuple encoding):

| Interface family | Exact methods and signatures | Caller / preservation boundary |
| --- | --- | --- |
| Accounts and request | `ListManagedUsers`, `ListKioskUsers`, `ListApprovers`: `()→(a(uss))`; `GetOwnAccount`: `()→(uss)`; `RequestAccess`: `(uuub)→(ss)`; `RequestOwnAccess`: `(uub)→(ssu)` | Parent uses Managed; kiosk uses Kiosk; shared form loads approvers; broker derives overlay child from caller credentials. No visit argument. |
| Request state / estimate | `GetPreferences(u)→(s)`; `UpdateRequestPreferences(usdbu)→(s)`; `UpdateRequestPreferencesWithUnit(usdbus)→(s)`; `SetRequestMuted(usb)→(s)`; `GetTimeStatus(uu)→(uuuu)` | Main saves unit-aware choices before approval; old update method still has a public contract. Estimate failure does not block valid submission. |
| Language | `GetOwnLanguage()→(s)`, `SetOwnLanguage(s)→(s)`; `GetChildLanguage(u)→(s)`, `GetChildLanguageContext(u)→(ss)`, `SetChildLanguage(us)→(s)` | Own surface versus kiosk selected child; locale preparation is user-service integration, not a new system-bus authority. |
| Presets and reminders | `GetOwnTimeGrantPresets`, `GetOwnNotifications`: `()→(s)`; `GetChildTimeGrantPresets`, `GetChildNotifications`: `(u)→(s)`; `SetOwnTimeGrantPresets`, `SetOwnNotifications`: `(s)→(s)`; `SetChildTimeGrantPresets`, `SetChildNotifications`: `(us)→(s)`; `GetOwnSessionAllowsSoftApps()→(b)` | Preferences and child notification code; personal settings never authorize policy/grant changes. |
| What's New | `GetOwnWhatsNew()→(s)`, `GetChildWhatsNew(u)→(s)`, `AcknowledgeOwnWhatsNew(s)→(s)`, `AcknowledgeChildWhatsNew(us)→(s)` | Parent own record versus both forms' shared child record; keep broker role checks. |
| Shared policy / calculations | `GetPolicyWarnings(u)→(as)`, `ListApplications(u)→(a(ssssasas))`, `ListRunningSoftBlockedApps(u)→(as)`, `HasRunningSoftBlockedApps(u)→(b)`, `SetPreferences(us)→(s)`, `SetParentControl(ubu)→(s)`, `RevokeOneTimeGrant(u)→()`; `CalculateRemainingTime(uuuu)→(u)`, `CalculateOwnRemainingTime(u)→(u)`, `PrepareOwnSession()→(b)` | Parent management, child countdown and expired-grant session reconciliation retain their distinct role/transaction contracts. Arithmetic calls authorize no grant; ordinary child policy is outside the session-confinement rollback. |
| Shared diagnostics | `LogEvent(sss)→()`, `ExportDiagnosticLogs()→(ay)`, `GetStartupTimings()→(a{st})` | Frontend event handler/report collection and technical timing readers; preserve bounded role-scoped diagnostics, not obsolete mechanism-specific admission authority. The separate frontend session-bus `KioskTiming1.GetStartupTimings()→(ttt)` reports Python-start/paint/presentation only. |

The actual order is local validation → saved request choices → kiosk locale
preparation (overlay skips it) → broker role/target/snapshot/lock/cooldown
checks → Polkit → caller/target/preferences/usage rechecks → account transaction
→ result. During authentication, `_PendingAuthorization` cancels on caller loss,
lock, inactivity, closing/removal or logind loss; it retains subscriptions and
the original cancellation identity through the kiosk challenge retry. Denial and
cancellation make no grant and consume no successful-request cooldown.

**C01 input boundary, not an implemented visit protocol:** authentication completion
sets `auth_done`, disables cancellation and drops lifecycle subscriptions.
Post-authentication usage/preflight/account reads precede the first policy write;
`NameHasOwner` proves connection survival, not continued session activity. Session
resolution may fall back to the user manager's primary `Display`, or permit a
sessionless caller. See the existing [audited implementation gap](Broker.md#audited-implementation-gap).
C01 must distinguish required pending-authentication cancellation and the
prospective outcome from the superseded mechanism. C02b1/C02b must preserve
required no-stale/no-duplicate-grant and fresh-request outcomes; this map neither
accepts the gap nor chooses new visit/admission machinery. C02b1's scoped
approval now covers the broker's pre-write lifetime; the current implementation
and its qualification limits are recorded in [Broker](Broker.md#authorization-and-grant-transactions).

The master's historical frontend note describes final visit validation and a
stylesheet fallback that are **absent from this source baseline**. There is no
active delta containing them. Actual account/preference/language readiness and
single-flight guards serve form correctness; frame presentation measurements
do not gate approval and human pauses have no frontend admission deadline.
C01 owns reconciliation of that obsolete prospective narrative, without
inventing a prerequisite or transferring historical review credit.
`agent_environment` also currently requires an installed non-C UTF-8 locale;
an inventory containing only C locales refuses preparation. C01/C09a must keep
that current limitation distinct from the required native-language fallback.

For C01c, `test_private_dbus_service.py` exercises a finite public-method matrix;
its name does not mean every newer feature API is covered there. Feature JSON,
role and XML dispatch checks also live in `test_service_contract.py`. Keep host
pending-authentication tests distinct from the post-authentication gap and from
real installed authentication. Follow the shared `tests/e2e/accessible_ui.py`,
entry/approval/rejection/cancel and overlay/choice/language/reminder callers into
`tests/e2e/scenarios.json`; no existing selector or qualification is declared
reusable by this source review.

##### C01b packaging, removal and review boundary

`Makefile:KIOSK_SOURCES`, `BROKER_SOURCES`, `COMMON_SOURCES`,
`EXTENSION_SOURCES`, `PRODUCT_USER_SERVICES` and `PACKAGE_SOURCE_FILES` name
the real payload. `_install-product-files` installs the shared launcher/child
alias, Python modules, agent environment consumer, notification/Wellbeing units,
D-Bus activation and XML; compiles the native role wrappers; and generates the
private confinement inputs described in C01a. `ACTIVATION_MANIFEST_PATHS`
tracks the native commands and unit/drop-in paths. C01c must follow those lists,
generated copies and lifecycle removal wiring before C02d/e delete wrappers,
policy entries or diagnostic parsers. Preserve the feature implementations,
ordinary-user Wellbeing/audio environment, agent vendor helper, shared RPM
diagnostics and WebKit/Glycin consumers. Removing their confinement inventory
does not authorize deleting their ordinary packaged assets.

There are no active old-plan files to delete now. Committed private launch,
material/view/proof and helper-substitution coupling remains a later removal
input; release-origin locale preparation and post-release public logout are
feature/lifecycle interfaces to preserve. This review edits documentation only;
no product, test registration, generated input or installed state changes.
C01b acceptance: **review passed**, with no declared targets. Independent
GPT-6.1 Sol High review checked provenance, exact APIs, feature preservation,
cancellation limits and caller/package/test handoffs; no actionable findings
remain. Usability priority: **passed**; Threat scope: **passed**, for this
source-review scope. Markdown links, plan structure, the four maintained host
consistency modules and `test_execution_plan_launcher.py` passed (639 tests).
These documentation-only paths are excluded from package inputs; no build or
installed acceptance is required or claimed. All three read-only source/review
agents finished and were closed. The maintained test runner finished its owned
cleanup; no task-owned VMs, processes or temporary source artifacts remain.

##### C01c automation and package consumer lineage

Source review on 2026-10-20 used release pin
`188be907c46b1cd0dabae06ac898c43e75beb05e` and checked-in HEAD
`c7c32f1757a47a26d8165eb743ab4425cdfe83fb`. The four Git inventory commands
recorded in C01a were empty at entry: **no staged, unstaged or untracked old-plan
additions exist in this checkout**. C01a/C01b's release/main interface tables
remain the source lineage; this extension follows their committed consumers.
Post-release source is a cleanup input, not accepted replacement work. Historical
controller/visit/startup reports do not supply missing source or qualification.

The tables name receiving tasks in the [queue](../Kiosk-Prompt-Queue.md).
C02 slices own their immediately affected tests, imports and registrations;
C03/C04 audit the remainder. No row authorizes broken intermediate consumers,
whole-file rollback of shared code, deletion of historical evidence or changes
to another plan's completion. The [test documentation map](../TestAutomation/README.md)
owns test-layer/status meanings; the [master](../Kiosk-Session-Confinement-Plan.md)
owns the replacement behavior and threat scope.

###### Package inputs, generated definitions and lifecycle callers

| Source owner / concrete caller | Retained behavior and removal/port boundary | Receiving task / test consumers |
| --- | --- | --- |
| [Makefile](../../Makefile): `PACKAGE_SOURCE_FILES`, `KIOSK_SOURCES`, `BROKER_SOURCES`, `COMMON_SOURCES`, `EXTENSION_SOURCES`, `PRODUCT_USER_SERVICES`; [package_inputs.py](../../tools/package_inputs.py) `paths/copy/digest` → `build_package.py`, `build_rpm.py`, `packaging/check_package.py` | Keep the explicit common DEB/RPM input map, frozen source and missing-input checks. The added native/private-preparation block is absent from the release pin. Remove its obsolete C/header/Python/policy members with their consumers; keep main's feature modules/assets, catalogues and packaging improvements. The empty `data/kiosk-runtime` directories add no payload. | C02a/C02c2 prepare; C02 activates; C02d/e remove. C03a audits `test_package_inputs.py`, `test_package_payload.py`, `test_rpm_packaging.py` in `tests/unit/`. |
| Makefile `_install-product-files` → `kiosk_session.c`, `kiosk_bwrap.c`, preparation and integration helpers; desktop/session/unit/drop-in callers in C01a | Builds `kiosk-session`, eight role variants (`app`, `notifications`, `notification-client`, `wellbeing`, `cleanup`, `audio`, `packages`, `dbus`) and `kiosk-bwrap`; installs three preparation-support modules and the integration helper. Reconstruct release session selection, then move every live caller before deleting wrappers. Keep shared request/logout, vendor authentication, notifications, ordinary-user audio/Wellbeing, RPM diagnostics and WebKit/Glycin feature consumers. | C02a prepares commands; C02 activates; C02d removes native/runtime source; C02e removes remaining wiring. `test_kiosk_login.py`, `test_kiosk_confinement.py`, `test_kiosk_rendering.py`, payload/RPM tests. |
| `tools/kiosk_confinement_policy.py` `generate` → Makefile → runtime preparation and lifecycle loader | Generates `config.json` runtime/executable/domain inventories, `generation`, distro MAC policy, `user-units/*/90-kiosk-confinement.conf`, Ubuntu Snap masks and two private session-data D-Bus definitions. Retire discarded private graph/material/inventory definitions and generated copies; preserve required isolation and functional service activation through the rebuilt owners. Feature assets cease being admission predicates without ceasing to be package assets. | C02c/C02c2 prepare required integration/migration; C02 switches; C02d/e remove. C03a1 audits mechanism fixtures; package activation/payload and rendering tests retain feature obligations. |
| Makefile `ACTIVATION_MANIFEST_PATHS`, `_generate-package-activation-manifest`; [package_activation.py](../../packaging/package_activation.py) `activation_for`; DEB rules and [RPM `%files`](../../rpm/oh-no-parent-control.spec.in) | Current classifier selects reboot for kiosk wrappers/support/confinement tree, compositor/WirePlumber drop-ins, login helper and PAM inputs. Port to justified replacement activation, including removed manifest members. Keep final packaged-byte manifests, shared builders and unrelated broker/child-trust/fapolicyd/Wellbeing activation. A former support-module reboot assertion is not a new lifecycle requirement. | C02c2 prepares classification/migration; C02 activates; C02e closes residual paths. C03a: `test_package_activation.py` (three preparation-support assertions), package payload/RPM tests; C04a maps affected installed histories. |
| [stage_distribution.py](../../packaging/stage_distribution.py) `pam_profile/pam_stack`, [fedora_pam.py](../../packaging/fedora_pam.py), distro `pam_restore/pam_enable/pam_remove` fragments → native PAM and session-limit helper | Port kiosk-only integration selectively. Preserve ordinary-account vendor policy/authselect profile/features, child time checks and the non-kiosk administrative user-bus bridge. The packaged historical GDM PreSession hook is also copied/removed by lifecycle code; its presence is not a working GDM 50 boundary. | C02c prepares native/distro integration; C02 activates; C02e removes unconsumed hook/profile wiring. C03a: Fedora PAM, kiosk login, runtime-cap, session-limit and package composition/removal tests. |
| [provision.py](../../tools/provision.py) account, `configure_account_access`, AccountsService session/cache/visibility methods → `postinst.in` `create_account`, AccountsService start-pre drop-in | Pin already supplies account UID/home/admin-group checks, broker UID, bus policy, icon and basic session/time setup. Main adds saved visible Wayland routing, metadata preservation, cache migration and UID-bound native expiry quarantine. Retain ownership, passwordless availability and ordinary-user independence; assess strict version gating separately from those results. Do not restore the shared provisioner wholesale. | C02c1 prepares routing/account behavior; C02c2 owns expiry/cache recovery and rollback; C02 cutover. C03a: `test_provision.py`, package configuration/removal, first-configure/account host fixtures; C04a installation/reboot histories. |
| Historical `packaging/kiosk_confinement.py` `install/install_locked/load` → [postinst](../../packaging/lifecycle/postinst.in), loader service | The former path audited exact PAM text/control flow/module inventories, published guards/MAC attestation, then released quarantine. Preserve effective policy, ordinary callbacks, retry/rollback and original useful causes. Exact unknown-module refusal and private loaded-material attestation are implementation assertions to replace, not customer requirements. | C02c prepares PAM; C02c2 prepares owned state; C02 switches; C02d/e remove old implementation. C03a package/PAM composition; C04a first-configuration, PAM variants and admission histories. |
| [prerm](../../packaging/lifecycle/prerm.in) `check-remove/remove`; postinst abort-remove; [postrm](../../packaging/lifecycle/postrm.in) `finish_remove`; [render_lifecycle.py](../../packaging/render_lifecycle.py) `embedded_confinement_finish_remove` | Current removal refuses live/foreign state, publishes durable vendor-only PAM denials before policy unload, and restores originals after account absence. Preserve safe removal, rollback and retry outcomes. The renderer embeds the **entire integration helper source** into postrm; installed-helper deletion alone leaves this build dependency. Replace the finite migration/finalizer before removing source, template tokens or generated distro scripts. | C02c2 prepares complete configure/remove/abort/post-erase/retry handling; C02 activates; C02e removes old embedding/wiring. `tests/support/package_scripts.py:use_real_kiosk_confinement` and finalizer source rewriting, package configuration/removal/RPM tests; C04a installed removal/fault/update helpers. |

###### Host fixtures and registration closure

Paths in this table are under `tests/unit/` unless another directory is named.
The native source families and individual header test owners are enumerated in
C01a; these rows also account for their shared/generated fixtures.

| Consumer / source owner and callers | Preserve versus retire/port | Receiving task |
| --- | --- | --- |
| Material/storage/selection: `test_kiosk_pin_storage.py`, `test_kiosk_required_material.py`, `test_kiosk_material_selection.py`, `test_kiosk_retained_projection.py`, `test_kiosk_initial_realization.py`; `tests/support/kiosk_material.py`, `tests/support/kiosk_material_selection.py` | Preserve applicable ownership, bounded work, foreign-state preservation and actual consumed-input protection. Retire exact runtime membership, cosmetic/catalogue admission bytes, private copied `/usr`, generation limits, ambient masks and inode equality after harmless replacement. Package asset-presence coverage survives separately. The old assertion that `InitialPreparation` is unwired is a staging assertion, not a customer result. | Immediate C02a/d/e repairs; remaining C03a1 audit. |
| Authority/channel/plan/realization/receipt/publication tests in C01a; `tests/support/kiosk_material_authority.py`, `tests/support/kiosk_preparation_plan.py`; fresh/retained startup tests and `tests/support/kiosk_fresh_startup.py` | Remove unused native probes, serializers, copy tickets, sealed protocol/view/pin formats and malformed-record matrices with discarded source. Port surviving cleanup/diagnostic outcomes. Retained fixtures derive C/Python text by replacement from fresh fixtures; both must move together. Namespace composition with PAM/MAC doubles supplies no installed entry proof. | C02d/e immediate source/fixture closure; C03a1 remaining audit. |
| `test_kiosk_login.py:native_module/native` and boundary observer; mixed `test_kiosk_confinement.py`; `test_fedora_pam.py`, `test_provision.py`, package configuration/removal/RPM tests; [package_scripts.py](../../tests/support/package_scripts.py) | Preserve ordinary authentication/administrator denial, dedicated routing, account ownership and complete rollback/removal/retry. Port exact native stage/guard lines, strict module inventory and attestation/order assertions to rebuilt responsibilities. `test_kiosk_confinement.py` mixes retained and obsolete coverage; whole-file deletion loses required checks. | C02c1/c2/c and C02 repair their own changes; C03a residual audit. C03a's named `tests/support/kiosk_pam.py` does not exist: use the concrete inline native fixtures and package-machine owner here. |
| `test_core.py`, `test_broker_properties.py`, `test_broker_state_machine.py`, `test_service_contract.py`; component `test_authorization_lifecycle.py`, `test_private_dbus_service.py`; support broker/DBus doubles | Preserve role/target checks, genuine selected-parent authority, session/disconnect cancellation, no late/duplicate grant, transactions/rollback and shared overlay semantics. Current consumers use direct request signatures; no visit-token/private-view fixture protocol exists to delete. Transport cancellation and broker no-grant tests protect distinct layers; neither establishes the post-authentication gap's resolution. | C02b1/b immediate compatible changes; C03b full chain audit. |
| Request estimate/selection/model/preferences/rendering/What's New units; UI `test_request_form_component.py`, `test_request_layout.py`, `test_language_settings.py`, feedback/About/identity/preview tests; [request_component_preview.py](../../tests/ui/request_component_preview.py), [preview.py](../../tests/support/preview.py) | Preserve current features and both kiosk/overlay parameters, agent-locale job ownership and normal exit. UI `ScriptedAgentLocale` bypasses native authentication and `ComponentWindow._logout` records an event: these prove host controls only. Current C-only-locale rejection is a known compatibility assertion to change with its implementation owner, not authority to weaken fallback or essential authentication failure checks. | C02b immediate changes; C03 residual shared-form audit; C09a owns fallback gaps identified by C01b. |
| `test_package_inputs.py`, `test_package_payload.py`, `test_package_activation.py`, `test_rpm_packaging.py`, `test_guest_inputs.py` | Keep feature packaging and immutable input closure; port removed preparation-support reboot/path assertions. Guest-input regression currently requires standalone `system_kiosk_confinement.py` in installed setup's closure; change it with actual consumers, not by dropping the assertion while imports survive. | C02 immediate package/closure repairs; C03a package audit; C04a installed helper closure. |

[regression_unit.py](../../tools/regression_unit.py) explicitly classifies 21
separate native runtime mechanism modules above, in addition to mixed package,
login, broker and feature modules. Delete obsolete names **and isolation
rationales** when source/tests disappear. [regression_ui.py](../../tools/regression_ui.py)
owns request/layout/feedback/preview groups; [regression_cleanup.py](../../tools/regression_cleanup.py)
separately classifies kiosk language/reminder/Chinese lifecycle safety modules
also present in unit inventory. Preserve fixture grouping and review changed
processes, namespaces, mounts, descriptor lifetime and scratch inheritance under
the [parallelism owner](../../tests/README.md#host-test-parallelism-review).
`test_regression_unit.py` checks the complete partition; exclusive fallback is
not completed review. [test_commands.py](../../tools/test_commands.py)
`CATEGORIES/suite_inventory` discovers leaves; there is no kiosk/C-series
category. Coverage is generated by `tools/generate_test_coverage.py` from its
inventories, not edited as an independent register.

###### Installed engineering and public-journey consumers

Maintained `tools/run-tests --help`, `--list`, `system --help/--list` and
`e2e --help/--list` were inspected. Listing needs no VM. Registered IDs below
identify **existing** bindings, not acceptance commands for the replacement.
Changed or missing candidate qualification is **pending**; C04 must compare exact
source/package/input/provider/target scope before any reuse. No replacement
C-series selector is registered by this review.

| Owner / registered consumer | Required result versus old mechanism coupling | Receiving task / qualification boundary |
| --- | --- | --- |
| [system IDs](../../tests/integration/system_case_ids.py), `tests/system/test_install_smoke.py`, `test_removal.py`; integration first-configure/accounts/removal helpers and `system_pam_variants.py` | Cases 4/5 retain interruption/retry and visible account/real entry across reboot; 6–25 retain remove/reinstall, rollback, post-erase and identity-refusal histories (8 is RPM-only); 283–286 retain finite vendor/profile/administrator/pending-update PAM variants. Port private generation/PAM guard/attestation witnesses; preserve ordinary-user policy, exact owned restoration and foreign-state refusal. | C02 owns immediately changed tests; C04a audits registrations/composition and helper sources. Host porting grants no live result. |
| `tests/system/test_enforcement.py` → integration `system_kiosk_confinement.py`, `system_kiosk_admission.py`, `system_kiosk_platform.py`, `system_kiosk_scope.py`, `system_kiosk_ambient_history.py`, `system_kiosk_required_history.py` | IDs 267–271 cover execution/admission/platform/callback/shared scope; 290–294 cover sibling/required/bootstrap/retained ambient/retained required histories. Retain normal-use/ordinary-account positives, deliberate reachable-route protection, original causes and owned restoration. Retire exact all-role MAC census, private helper substitution, retained view/manager equality, global material hashes, ambient masks and stale-generation reboot as mandatory outcomes. Engineering injections remain separate from public use. | C02d/e direct consumers; C04a remaining installed audit; C04c proof alignment. C06 and later protection tasks decide actual route defenses; registration alone cannot make a refusal acceptable. |
| Integration `system_native_update.py`, `system_session_expiry.py`, `system_runner.py`; session-expiry tests | Preserve shared child runtime-cap/time, offline recovery and PAM scope (281/282), authenticated administrative bridge behavior, earlier-release/update policy and usable reentry. Native dependency case 289 has an isolated complete retained-session history; port generation-refusal/private-manager witnesses without deleting the update outcome. | C02c/C02c2 directly affected changes; C04a map, C04b baseline composition; later C09c1/lifecycle histories qualify actual changed activation. |
| [kiosk_entry.py](../../tests/e2e/kiosk_entry.py) `enter_station`, `observe_activation`, `native_update_station`, `KioskEntryJourney`; `parent_setup_qualification.py`, graphical smoke dispatch | Public GDM entry requires fresh account/focus/boot proof, one Enter, independent form/return. `confinement_census` separately calls the old system helper from entry, installation activation and native-update contexts; remove/port these transitive engineering calls with their producer. A working form or engineering census cannot replace the other when required. | C04a helper/engineering closure; C04b maps exact operations; C04u/f adapt and qualify changed entry/approval on both targets. |
| [scenarios.json](../../tests/e2e/scenarios.json): 47/48/49, 50/51/52, 192 → request exit, `restricted_station.py`, `kiosk_about.py`; shared `request_flow.py`, `kiosk_approved_flow.py`, `request_composition.py` | Retain Cancel/close/approved exit, usable restricted station, genuine approval/denial/Cancel with preserved choices, safe About and fresh reentry. `KioskRequestJourney` checks balances/choices through public results, without private receipt authority. 50–52 additionally attempt Overview/grid/terminal and observe the unchanged restricted form; those outcomes survive independently of native framework details. | C04b maps finite baseline selectors; C04u/f qualify changed shared operation; C04 verifies readiness before C05u/f customer histories. These existing ready inventory labels are not qualification of the rebuilt candidate. |
| Remaining request/overlay/choice/time/app/revocation/language/reminder/lifecycle consumers through [catalogue](../TestAutomation/E2E-Building-Blocks.md#kiosk-child-overlay-and-the-shared-request-form) and [recipes](../TestAutomation/E2E-Scenario-Recipes.md); `fresh_kiosk_restart.py` case 259 and Chinese lifecycle | Keep child identity, soft/hard app effects, expiry/revocation, both surfaces' shared choices, per-child language, genuine native prompt language and real install/reboot/reentry. Entry/approval fragments are transitive dependencies of these journeys. Host language/agent doubles or a 50–52 pass cannot establish this complete core downstream journey or every feature binding. | C04b traces exact finite baseline needs and pending gaps; C04u/f shared qualification; C04 readiness, C05 baseline and C10 final maps. Additional independent missing operations need the selected consumer's prerequisite route, not hidden work in one qualifier. |
| Engineering `check_e2e_kiosk_preferences_confinement`, `check_e2e_kiosk_feedback_confinement`, `check_e2e_kiosk_notification_wellbeing` → respective journeys/guest helpers | Preferences checks exposed actions, draft preservation and an old strict census. Feedback owns a broker fault/restoration plus usable unsent editor/privacy and census. Notification/Wellbeing checks a preview and ordinary-user settings restoration via `system_wellbeing_qualification.py`; it supplies no natural-reminder customer credit. Port mechanism witnesses; retain exposed-action, feature, fault ownership and restoration outcomes. | C04a maps engineering dependencies; C04b records applicable operations; C04c reconciles proof claims. Later exposed-action/fallback/recovery tasks qualify their exact scope. |

Source closure also includes `system_runner.stage_selected_inputs`,
`system_guest`, `system_removal` and `tests/integration/guest_inputs.py:Bundle`:
selected test-area imports and declared non-Python/native inputs are frozen,
including function-local imports. Obsolete imports cannot remain as inert
copies. `system_guest.installed/verify_pam/collect_native_checkpoints` and
`system_removal.verify_loaded_confinement` also consume the old graph.
Generated engineering inputs include temporary native-mode PAM services,
namespace callback stacks, copied interpreters, units and fault wrappers.
Port their source definitions and host doubles (`test_system_runner`,
`test_system_snapshots`, `test_native_update_runner` and affected
`test_system_*` modules) alongside producer removal. Retained ambient case 293
currently binds 11 mutations to one manager/view; required case 294 binds four
native/config/policy/privilege branches. Port or retire complete histories,
including runner phases/checkpoints, rather than leaving renamed assertions.
E2E's `InstalledJourney/JourneyPlan` → `UiObservations` → `AccessibleUI`
shares `tests/support/application_ui.py` with host automation. Perl
`onpc_gdm::enter_station`, `onpc_request_flow::prepare/approve`,
`onpc_password::enter_kiosk_mate_password`, graphical smoke dispatch and
`e2e_worker.distribution_inputs` are copied/validated worker consumers, not just
Python imports. Port shared mechanics once; retain public IDs, current owner,
single-use input, secret-recipient and uncertain-result guards under the
[UI mandate](../Mandates/UI-Automation-Mandate.MD). REQUEST01–06/08–13,
AUTH01/02 and FLOW request fragments retain their exact catalogue qualification
limits. Unsupported native-gesture exclusions remain exclusions.

Qualification wrappers use `named_input(package_source=True)` (and the declared
fixture/upgrade profile where applicable); `test_commands` prepares absent
inputs through the maintained builder. `KioskEntryQualification` also checks
frozen package, baseline and installation-recipe identity before restoring its
snapshot. A version name, unchanged function name, legacy bundle or historical
pass cannot qualify changed bytes. Current input definitions/imports may be
ported; already-created artifacts have separate ownership below.

###### Installed state, retained evidence and C01 sizing handoff

| State/evidence owner | Preservation or migration boundary |
| --- | --- |
| [Lifecycle](Lifecycle.md#startup-login-and-update-lifecycle), [removal](Package-Removal.md#pam-and-kiosk-ownership), integration helper | C02c2 owns migration of `kiosk-confinement.json` original/generated PAM, backend/UID/protocol/previous/prelease/removing/attestation records, durable removal marker/PAM denials, identity-bound runtime locks and old private generations. Account absence and owned restoration must precede retiring barriers; live/foreign/replaced objects stay protected. Source deletion is no permission to erase installed records. |
| Provisioner/account lifecycle | Preserve `package-created-kiosk-uid`, reserved home/mail ownership, UID-bound `kiosk-configuration-account.json` original expiry and `quarantined/releasing` recovery. AccountsService's `.onpc-kiosk-visibility-v1` slot/xattr carries inode/UID/digest ownership; do not sweep its cache. Preserve native administrator policy, original Fedora authselect ownership, ordinary preferences/logs, child trust/fapolicyd baseline and uninstall rollback snapshots under their existing owners. C02c1/c2 port selectively. |
| [Storage mandate](../Mandates/Test-Storage-Mandate.md), [retention](../../tests/README.md#aggregate-output-retention), [plan evidence](../Execution-Plans.md#accepted-evidence-lifetime-and-historical-recovery) | Preserve verified inputs, runner reports, accepted bundles/locators, controller checkpoints, recordings and VM baselines under their owners. Replacing a source fixture/selector does not authorize artifact purge, journal edits or baseline deletion. Ordinary bounded retention and exact owned recovery remain in force. This task allocated no VM or installed state. |
| [Proof](../Kiosk-Confinement-Proof.md), confinement/lifecycle/specification prospective prose, [Reliability plan](../Reliability-Plan.md#task-boundaries-after-audit), E2E catalogue/recipes/coverage owners | C01 settles combined source/design conflicts; C04c reconciles obsolete R-series/receipt/private-view obligations and current descriptions after cutover, retaining original historical claims and known proof loss. Reliability 006a/006b map cases 290/291 only after the new boundary/protection review; locale/readiness consumers 008a/008c retain actual job/cancellation behavior. This review closes no row in those plans. |

Finite risks for C01: lifecycle migration spans configured, partial PAM
publication, removing, post-erase/account-absent, legacy-prelease and expiry/cache
recovery states. Source allowlist, staged DEB/RPM payloads/manifests, RPM `%files`,
embedded finalizer and package-machine rewrites must move together.
`test_kiosk_confinement.py` exceeds 7,300 lines and mixes retained behavior with
discarded mechanisms; fresh/retained fixtures generate interdependent C/Python
sources. Frozen installed-area imports and copied worker definitions broaden
the removal closure beyond direct callers. These are sizing risks for the
receiving task when selected, not authority to resize/reorder future rows now.
No new independent prerequisite is needed to complete this finite source map.

C01c acceptance: **review passed**, with no declared targets. Independent
GPT-6.1 Sol High review corrected the concrete installed-helper caller list
(PAM variants under installation; both retained histories under enforcement)
and confirmed no remaining actionable findings. Usability priority: **passed**;
Threat scope: **passed**, for the source-map scope. Markdown links, plan
structure, the four maintained host consistency modules and
`test_execution_plan_launcher.py` passed (639 tests). This changes documentation
only; product, test registrations, generated input definitions, qualification
status and installed state remain untouched. These paths are outside package
inputs; no build or installed result is required or claimed. All three source
agents and the independent reviewer finished and were closed. The maintained
runner completed its owned cleanup; no task-owned VMs, processes or temporary
source artifacts remain.

#### Single decision/rejection ledger — execution contribution

**Historical incoming-link anchor; the R-series ledger is retired.** Its
proposed refusal categories, customer explanations, clocks, recovery protocol
and locale/visit/activation mechanisms are not registered product behavior or
requirements for this rebuild. The master's
[usability rule](../Kiosk-Session-Confinement-Plan.md#highest-priority-product-usability)
and [threat scope](../Kiosk-Session-Confinement-Plan.md#mandatory-threat-scope-reasonable-child-effort)
own current decisions. Existing implementation and feature dispositions are in
the cumulative C01a/C01b/C01c maps above. C04c must reconcile remaining references
from lifecycle, localization, reliability/proof and automation owners; this
retirement changes no test expectation or installed state.

### R01 integrated admission contract

**Historical incoming-link anchor; no active admission contract.** The former
integrated proposal and its review receipt did not implement or qualify a
replacement. Do not infer a required native gate/controller, private unit graph,
PAM projection, visit receipt or effect-admission transaction from consumers
still using this anchor. Follow the
[current target](../Kiosk-Session-Confinement-Plan.md#target-design),
[task boundaries](../Kiosk-Session-Confinement-Plan.md#task-boundaries) and
[acceptance](../Kiosk-Session-Confinement-Plan.md#acceptance).
The retained current-source descriptions above remain descriptive until cutover.

#### Accepted mapping of legacy assertions

**Historical incoming-link anchor; the R-series mapping is retired.** It grants
no authority to rewrite assertions or transfer historical passes. The
[C01c consumer map](#c01c-automation-and-package-consumer-lineage) allocates host
cleanup to C03 and installed/E2E, reliability/proof and documentation reconciliation
to C04. Those owners preserve stable customer case identities, required behavior,
ordinary-use controls, exact owned restoration and historical evidence while
removing tests of discarded mechanisms. Reliability 006a/006b and cases 290/291
remain reconciliation consumers, with no row closed here. The
[verification scope and evidence limits](#verification-scope-and-evidence-limits)
retain the original evidence and known proof loss; no installed acceptance is
claimed by this documentation edit.

## Roles, services and dialogs

The generated role policy (`tools/kiosk_confinement_policy.py`) separates
session, manager, request-app, notification, audio, Wellbeing, authentication,
WebKit, scanner and image-decoder routes. Generic interpreters are reachable
only through [native fixed launchers](../../tools/kiosk_session.c), which reject
caller arguments, clear startup injection and select installed scripts. The
manager cannot use user units, privileged command prefixes or ignored
profile-setting errors to escape its existing kernel boundary.

The manager alone receives the private root-owned unit search path. Ubuntu's
finite Snap masks and private D-Bus definitions block the reviewed vendor
activation routes. Shared Wellbeing/audio launchers preserve ordinary users'
environments. Kiosk WirePlumber uses system roots and empty Lua default search
paths; its trusted custom searcher remains available. Kernel mapping/transition
restrictions, rather than Lua alone, enforce native plugin boundaries. Reviewed
packages and shipped scripts define current qualified plugin scope. Some current
shared resource searches still use host `/etc/xdg`, `/usr/share` and
`/usr/local/share`; the target must distinguish trusted host resources from
concrete child-writable injection routes without making unknown resources an
entry prerequisite.

Fedora's compositor/service, app and notification-provider roles may map
`dri_device_t` GPU devices for rendering. That permission belongs only to those
three roles and grants no executable transition or general device mapping.

The bubblewrap launcher (`tools/kiosk_bwrap.c`) supplies a read-only
`/usr/bin` bind before invoking independently pinned distribution bubblewrap.
Only finite native WebKit/Glycin bootstrap roles receive their required private
namespace, mount and loopback setup permissions. Payload roles do not receive
that authority. AppArmor profiles stack with existing restrictions; Fedora
binds retain source inode types without generic `bin_t` execution. Glycin's
pinned decoders have no onward exec route. The optional GStreamer Python plugin
cannot acquire executable mappings in the confined view.

Polkit owns authentication; product forms never receive the password. The vendor
native helper retains its original inode and privilege metadata through an
independent read-only pin: mode 04755 on Fedora and 0755 on Ubuntu, without file
capabilities. Fedora requires the helper's enforcing domain, exact mixed UID
tuple, private namespace/material and live confined agent parent. Its vendor
`unix_chkpwd` route retains vendor transitions and shadow access. Ubuntu's
socket-activated root helper runs outside the kiosk account. These finite routes
must survive the target; global `nosuid` or `NoNewPrivileges` assumptions cannot
replace platform-specific proof. [Broker](Broker.md#broker-interface-and-roles)
owns authorization and approval transactions independently of confinement.

About, Preferences, editors, reports and privacy disclosure remain in-app.
Kiosk mode suppresses external handlers, file choosers, management controls and
arbitrary launch actions. [Front ends](Frontends.md) and
[Logging and feedback](Logging-and-Feedback.md) own those feature contracts.

## Installation, updates and removal

Current configuration takes shared admission then exclusive preparation while
publishing policy, PAM and attestation. If the preparation inode is absent it
takes exclusive admission without manufacturing a wrongly labelled lock. The
boot loader uses the exclusive admission/routing/preparation barrier and verifies
the saved digest pair before loading policy. Interrupted unpack cannot become a
trusted configuration merely by rebooting, and an active admission prevents a
racing loader from changing policy or attestation.

Current native confinement, PAM, fixed-launcher and routing updates use the
reboot activation boundary: graphical logout can retain an old manager and
private executable generation. Before required reboot, the station offers the
restart explanation with policy controls unavailable. The prospective lifecycle
reduces avoidable manager/material rejection through safe owned renewal; it has
not changed the shipped activation classifier. See
[Lifecycle](Lifecycle.md#retained-material-activation-and-recovery).

[Package removal](Package-Removal.md#pam-and-kiosk-ownership) owns cleanup and
recovery. Exclusive locks exclude admissions; live kiosk threads, pending MAC
state and stale mappings currently refuse removal without signalling them.
Durable PAM denials precede policy unload/payload erasure. Exact original PAM is
restored only after verified owned-account deletion. Abort restores enforcement
before releasing gates; foreign state and interruption preserve barriers and
recovery records. Account/home deletion verifies identity, ownership, links and
mounts and uses public AccountsService uncache. Ordinary removal retains
preferences/logs; purge deletes owned data only after integration cleanup succeeds.

## Offense and defense scenarios

The table describes current defenses and retained behavioral obligations.
Mechanism-specific expectations are reconciled in
[scope reconciliation](../Kiosk-Session-Confinement-Plan.md#scope-reconciliation) when their
replacement boundary is proven; this document does not edit executable tests.
Proof links identify maintained cases/helpers, not a claim that every current
candidate passed. System checks need independent enforcement negatives and
positive controls; public E2E checks establish observable customer results.

| Scenario ID | Offense scenario | Current defense and proof obligation |
| --- | --- | --- |
| 1 | Select the station with a normal desktop. | Routing checks repair and deny the current attempt; the final PAM boundary separately constrains actual exec. [Admission](../../tests/integration/system_kiosk_admission.py#L363), [final-exec matrix](../../tests/integration/system_kiosk_confinement.py#L1984). |
| 2 | Select an X11 station session. | Saved and actual PAM transport must be Wayland. The account-stage test proves denial/repair/retry, not a complete X11 session. [Admission matrix](../../tests/integration/system_kiosk_admission.py#L363). |
| 3 | Log in to a text console as the station. | Native `login` PAM denies the identity, backed by nologin; ordinary-account positive control remains. [Admission assertions](../../tests/integration/system_kiosk_admission.py#L348). |
| 4 | Log in remotely by SSH as the station. | Installed `sshd` account gate denies it and effective SSH configuration uses PAM. This is not a complete network login proof. [SSH/admission assertions](../../tests/integration/system_kiosk_admission.py#L363). |
| 5 | Use overview, application or terminal shortcuts. | Dedicated compositor exposes no desktop launch routes and the form stays usable. [Public cases 50–52](../../tests/e2e/restricted_station.py). |
| 6 | Enter a wrong parent password, then try shortcuts. | Denial grants no access and retains the confined form/choices; restrictions are repeated. [Case 51](../../tests/e2e/restricted_station.py#L60). |
| 7 | Cancel parent authentication, then try shortcuts. | Cancellation retains the form and a second restriction cycle. [Case 52](../../tests/e2e/restricted_station.py#L92). |
| 8 | Close or cancel the request to uncover a desktop. | Exit returns to usable sign-in without a desktop. [Cancel case 47](../../tests/e2e/kiosk_cancel.py), [guarded surface-close case 48](../../tests/e2e/kiosk_escape.py); these do not prove every native close gesture. |
| 9 | Treat successful parent approval as unrestricted station access. | Approval updates only the selected child's authorization; success exits to sign-in. [Case 50](../../tests/e2e/restricted_station.py#L33), [broker authorization](Broker.md#authorization-and-grant-transactions). |
| 10 | Launch a browser, chooser or management window from About/Help. | Information remains in-app and unfinished request state survives. [Case 192](../../tests/e2e/kiosk_about.py). |
| 11 | Escape through Preferences or nested editors. | Exposed controls reject forbidden actions; cancelled drafts preserve the request and confined process census. [Preferences qualifier](../../tests/integration/check_e2e_kiosk_preferences_confinement.py). |
| 12 | Escape through reporting or privacy disclosure. | Editing/navigation remain in-app; qualifier checks waiting-session confinement without submission. [Feedback qualifier](../../tests/integration/check_e2e_kiosk_feedback_confinement.py). |
| 13 | Ask services to launch a shell, generic interpreter or alternate desktop. | Role-specific MAC restricts manager/service execution with positive native controls and fresh enforcing denials. [Execution matrix](../../tests/integration/system_kiosk_confinement.py#L1984). |
| 14 | Copy/rename an allowed binary or symlink a writable interpreter. | Trusted private paths/inodes and transitions determine execution authority. [Writable-input assertions](../../tests/integration/system_kiosk_confinement.py#L1414). |
| 15 | Execute via loader, open descriptor or memfd. | Actual final-exec gate denies these routes after an allowed native control. [Final-exec matrix](../../tests/integration/system_kiosk_confinement.py#L1984). |
| 16 | Use a user unit with a privileged command prefix. | `ExecStart=+` cannot remove manager MAC or grant root. [User-unit assertions](../../tests/integration/system_kiosk_confinement.py#L1414). |
| 17 | Select no security profile, including ignored setup errors. | Kernel boundary still denies forbidden exec. [Service-API assertions](../../tests/integration/system_kiosk_platform.py#L340). |
| 18 | Inject writable startup scripts/configuration. | Fixed launchers clear injection; audio uses system roots and empty default Lua paths. Qualified inputs are finite. [Startup/Lua assertions](../../tests/integration/system_kiosk_platform.py#L186). |
| 19 | Load a writable native audio plugin. | Kernel executable-mapping denial follows a genuine trusted-library positive control. [Native audio API assertions](../../tests/integration/system_kiosk_platform.py#L285). |
| 20 | Substitute report editor web/media helpers or writable code. | Bootstrap/payload roles and pinned native paths reject tested substitutions. [Bubblewrap assertions](../../tests/integration/system_kiosk_confinement.py#L1245). |
| 21 | Use a decoder/sandbox helper for onward exec or host mount changes. | Finite decoder route has no onward exec; namespace administration belongs only to bootstrap roles. Role policy (`tools/kiosk_confinement_policy.py`), [bubblewrap assertions](../../tests/integration/system_kiosk_confinement.py#L1245); unknown vulnerabilities are outside this proof. |
| 22 | Turn the password helper into a privileged launcher. | Finite vendor helper transition checks credentials, label, parent and pinned executable/namespace. [Helper assertions](../../tests/integration/system_kiosk_confinement.py#L197), [public authentication](../../tests/e2e/restricted_station.py). |
| 23 | Change the station desktop or manage parent policy. | Root routing/Polkit and independent broker roles protect those operations. [Routing recovery](../../tests/integration/system_kiosk_admission.py#L363), [broker matrix](../../tests/system/test_authorization.py#L114). |
| 24 | Use package replacement/reexec to acquire new unrestricted code. | Current private directory dentries preserve code/library inputs; manager thread boundaries remain checked. [Replacement/reexec assertions](../../tests/integration/system_kiosk_confinement.py#L1510). |
| 25 | Retain a manager across required configuration changes. | Current exact material/receipt checks can require reboot. Availability and safe renewal replace that mechanism under the [new acceptance contract](../Kiosk-Session-Confinement-Plan.md#acceptance). [Existing configuration check](../../tests/integration/system_kiosk_confinement.py#L2015), [generation refusal helper](../../tests/integration/system_native_update.py#L743) remain current tests. |
| 26 | Enter with missing/stale/disabled/permissive security policy. | Required loaded enforcement/attestation deny unsafe admission; restoring owned policy permits recovery. This does not prove administrator policy removal from a live session. [Policy-loss assertions](../../tests/integration/system_kiosk_confinement.py#L1710). |
| 27 | Enter during interrupted configuration or before required reboot. | Account expiry remains until configuration completes; restart surface exposes no usable policy controls. [Configuration/reboot histories](../../tests/system/test_install_smoke.py#L36). |
| 28 | Reboot after partial package unpack to adopt unconfigured files. | Successful-load digest pair must match configuration/policy. [Attestation-drift assertions](../../tests/integration/system_kiosk_confinement.py#L1659). |
| 29 | Race login, reload or package writes. | Identity-checked locks serialize current admission/lifecycle publication. Compatibility target must preserve safety while avoiding unnecessary contention rejection. [Held-admission assertions](../../tests/integration/system_kiosk_confinement.py#L1948). |
| 30 | Escape through background processes or login teardown. | Manager/executor/PAM helper retain current enforcing roles through credentials and teardown, including parent exit. [PAM lifecycle](../../tests/integration/system_kiosk_confinement.py#L1005), [waiting census](../../tests/integration/system_kiosk_confinement.py#L93). |
| 31 | Use keyring, namespace setup or cleanup callbacks before/after confinement. | Current kiosk-only guards exclude reviewed callbacks; ordinary users retain them. [Namespace case](../../tests/system/test_enforcement.py#L28), [shared PAM case](../../tests/system/test_enforcement.py#L33). |
| 32 | Activate a desktop service around launcher restrictions. | Finite kiosk unit masks/private D-Bus definitions block reviewed Snap routes. This is not proof against every future activation service. [Scope assertions](../../tests/integration/system_kiosk_scope.py). |
| 33 | Remove the product while kiosk execution persists. | Active state blocks current removal; durable PAM denials precede unload/erasure and account deletion precedes PAM restoration. [Removal cases](../../tests/system/test_removal.py), [ownership contract](Package-Removal.md#pam-and-kiosk-ownership). |
| 34 | Substitute account records, aliases or cleanup inputs. | Alias ancestry and lifecycle identity/ownership/link/mount checks refuse foreign state rather than adopting/deleting it. [Alias assertions](../../tests/integration/system_kiosk_confinement.py#L1615), [removal cases](../../tests/system/test_removal.py). |

## Verification scope and evidence limits

The following R02a work report is historical. At the C01a source baseline
recorded [above](#c01a-session-source-lineage), its startup/controller/visit
replacement is absent; the production dispatcher still calls fresh/retained
startup. This report is not evidence that those reported edits exist in this
checkout or that their tests apply to it.

The superseded R02a report described source adding protected PAM policy
substacks and empty-credential conversation, a package-owned unit graph/private
bus, fixed controller/agent launchers and broker visit/effect-admission controls.
It reported a native dispatcher calling `kiosk_startup_open` with old fresh and
retained view machinery in private regression probes. That is not the current
source route. The historical candidate
connects protected `AdmitKioskSession` proof, the original shared entry budget,
finite configuration/code snapshots and one owned renewal. The first independent
integrated Astra xHigh review withheld completion. The revised candidate changes
renewal receipts, actual child group write authority, durable bounded cleanup,
retained-session inactivity, trusted PAM mount teardown and placeholder ownership.
The second integrated review found those corrections addressed but withheld
completion for finite executable-consumer coverage, the form's typed inactivity
race, uncertain old-caller inspection and a refreshed controller operation cap.
Their corrections require fresh independent review and complete affected validation.
The third integrated review additionally found unchecked intermediate alias hops,
old committed-result display after broker-observed departure/rapid return, and
legacy root/policy mode checks preceding effective child-authority checks.
The fourth integrated review found the revised alias/form/protected-state/expiry
paths coherent but withheld completion for an unchecked live interpreted
notification script and Python's global system-site/module route, plus the
broker's mode-only GDM caller veto. These production compositions remain open
despite 411 passing focused host controls and both package builds against the
preceding candidate. The remaining 2,767 affected regressions also passed with
owned cleanup complete. The native-owned GDM caller correction subsequently
passed 300 focused authority/transaction/approval cases and both builds; it still
required fresh integrated review. The proposed custom Python loading mechanism
was never implemented and is now discarded. The new
[source rebuild](#c02-activated-session-baseline) replaces this development
direction; historical partial results do not qualify it.
Host tests replace OS calls with private PAM configurations or finite
bus/account doubles; they do not prove actual GDM credentials, loaded enforcing
policy, agent registration or paired installed native teardown. No replacement
installed selector is qualified by those results. The new
[TA cleanup](../Kiosk-Prompt-Tasks/C04-installed-ta.md) maps actual retained
behavior to rebuilt-source checks; neither partial source nor old review
completes the new plan.

Persistent identities remain in [system case IDs](../../tests/integration/system_case_ids.py):
4 covers first-configuration interruption/retry, 5 account classification and
real GDM activation across reboot, 267 native execution, 268 login admission,
269 platform integration and 290 sibling isolation across a retained station.
The [installed-suite guide](../../tests/integration/README.md#running-the-current-installed-suite)
owns exact scope and witnesses. Public cases 50/51/52/192 are separately
registered in the [E2E inventory](../../tests/e2e/scenarios.json). Preferences and
feedback qualifiers remain engineering checks, not complete customer cases.

The recorded 2026-10-16 qualification passed affected native, admission,
platform, shared-PAM and real-session checks on both targets, plus repeated
system 6/267 and 4 histories and public 50/51/52/192. Reviewed source was
`512e1fd0fbdfc9a9a69916f635054bbf0ea9d330`; DEB SHA-256
`9abe9da9c5df0aeae86e07af75a0ac2a5bdc7eeaf362a14e1ad15be54ee2eadb`,
RPM SHA-256 `ba44158f0c9f690313aef6fecba23d404bafec4469df76fbb65e6ef4f6885aeb`.

Original Fedora, Ubuntu recovery and review exports are inherited into cumulative
bundles under `output/test-runs/host/exports/`:

- `onpc-evidence-bundle-opzdhw6_/evidence.zip`: 58,595 files, SHA-256
  `3d031877f134e0be39833e9baf2d297a0d66aaa1bd76ec26e5da23bc248b1107`.
- `onpc-evidence-bundle-g99gn1a1/evidence.zip`: 44,882 files, SHA-256
  `b91777276815aec5f21c04e37a1c6e8c55ef9624dd954f0bcb98984daec3fb22`.

Use maintained [artifact readers](../../tests/README.md#prompt-free-test-artifact-access).
Original paths remain archive inventory keys after rotation; retention ownership
is unchanged. These historical candidate results do not qualify the current
fresh/retained composition or prospective architecture.

The 2026-10-17 close-out preserves accepted authorization cases 26–151 and
removal cases 6, 7 and 9–17 on both targets. System 4/5/18–25/267–271 and their
prerequisites passed 73/73 executions per target. Public 47/48/50/51/52/192 and
Preferences confinement passed on both. Fedora RPM recovery case 8 passed eight
executions; the final case 5 restored its combined-VM recording. Recording
indices and surviving reports remain in the cumulative bundles. Raw allocations
`onpc-system-yb33mofd` and `onpc-system-6covjn1o` rotated before archival: accepted
passes and archived host reports remain, but original result/JUnit/TAP records
are unavailable.

Feedback confinement independently passed on Fedora with enforcing SELinux
(report `20261017T213630Z-7d9de2df`, allocation `onpc-graphical-smoke-oc15q7f5`)
and Ubuntu with enforcing AppArmor (report `20261017T225629Z-47b5880c`, allocation
`onpc-graphical-smoke-o6cd5k77`). Editing, privacy navigation, draft preservation
and strict waiting census passed without submission. These engineering qualifiers
record customer product domain `not-run`, no case recording; disabled
sound/scanner observation was explicitly excluded.

This campaign used multiple candidates. The 73-pass system source was
`75f608f67dc164adc835663f4d35b9e94fd79d61`; public E2E source was
`0690f1de71cc41bfad97f494b19087fbb3ce0f85`. Fedora feedback source was
`4e08dcdbaa5ee574d349a4a00c5cd81a5ad4cd79`, RPM SHA-256
`ae32aa2efe5b716840b8025f7edd7d26b5326d22a1118b44749e24331466da6d`.
Ubuntu feedback source was `f0e4dc777f005c611f9dce483f2334edc4592440`, DEB SHA-256
`80fe01b91186386ce7300dae84a1816a753c3bbd6eac4d0bf20b1740b6553814`.
Its result, workers, report and manifest remain in
`onpc-evidence-bundle-g99gn1a1` alongside earlier failures. The earlier
intermittent Ubuntu entry timeout has no established root cause; retry success
does not claim a fix.

An explicitly accepted historical Ubuntu retention loss covers matrix allocations
`onpc-system-o9ryhtxo`, `onpc-system-8efeqxdi`, `onpc-system-4rp3cyvz`,
`onpc-system-ngv1c40y`, 27 removal/rollback/publication executions in
`onpc-system-942mnslh`, and two first-configuration phases in
`onpc-system-8xmuzogd`. Their accepted passes lack raw proof; older results do
not replace it. That missing evidence alone does not reopen qualification;
changed inputs or a demonstrated defect follow affected validation.

Source review and host checks cannot replace installed enforcement and usable
public entry. Changed distro code, plugins, PAM flow, policy, native launchers
and executable inputs require affected qualification. The new plan's
[acceptance](../Kiosk-Session-Confinement-Plan.md#acceptance) requires both platforms and
does not transfer historical passes to the replacement design.
