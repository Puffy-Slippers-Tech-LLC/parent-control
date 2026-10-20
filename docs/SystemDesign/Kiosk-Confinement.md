# Kiosk confinement

The dedicated request station lets a child ask an administrator for more time
without gaining a desktop, terminal, application launcher or policy-management
session. Confinement covers the package-created `oh-no-parent-control` account,
its graphical session, user manager, services and native helper processes.
The child's personal desktop is a separate account: its time and application
restrictions belong to [Screen time](Screen-Time.md) and
[Application policy](Applications.md).

This module distinguishes the current implementation from the prospective
[compatibility-first target](../Kiosk-Resilience-Plan.md#target-design).
The [execution plan](../Kiosk-Resilience-Plan.md) owns that change's finite queue,
acceptance and reconciliation. Replanning does not change runtime enforcement,
tests or installed qualification.

## Security boundary and assumptions

The attacker is a non-administrator child who can operate the request station
and prepare files in their own account. Engineering tests additionally plant
kiosk-owned files, submit service requests and vary trusted configuration as
root to challenge boundaries that the public UI does not expose. Those fixtures
do not imply that a child can write root-owned policy or invoke privileged test
helpers. A fixture that pregrants arbitrary kiosk code execution does not, by
itself, establish a reachable customer escape or justify an admission predicate.

The trusted base comprises the kernel, enforcing AppArmor or SELinux, root-owned
package and distribution code, PAM, systemd, GDM, AccountsService and Polkit.
The implemented platform boundary is Ubuntu 26.04/GNOME 50 with AppArmor and
Fedora Workstation 44/GNOME 50 with enforcing SELinux. Fedora confinement
qualification does not change the product's overall
[release qualification](../System-Design.md).

The required customer result is a usable passwordless request form with genuine
administrator approval and no unrestricted station desktop. A legitimate unusual
host configuration or unrelated installed application must not create an
avoidable admission prerequisite. A normal supported fixture rejected at entry
is a product blocker; an intentional-refusal label cannot waive it. Deliberately
unsafe security fixtures separately prove that inability to establish isolation
never becomes unrestricted success. Explicit administrator access denials remain
effective and ordinary accounts retain their authentication and access policies.

The current implementation requires each admitted route to retain its permitted
role, executable material and private mount namespace. Kernel or trusted-service
exploits, stolen administrator credentials, administrator policy changes and
booting another operating system are outside this boundary. The scenario table
records bounded proof obligations, not exhaustive exploit resistance.

## Admission and account integrity

[Provisioning](../../tools/provision.py) creates a non-administrative account with
`/usr/sbin/nologin`, the dedicated Wayland session and durable visible/saved
AccountsService classification. Its recorded UID and reserved home determine
ownership. The product's Polkit rule denies the station changes to its own
AccountsService metadata. The guarded classification adapter preserves unrelated
metadata and ordinary accounts; [Lifecycle](Lifecycle.md#startup-login-and-update-lifecycle)
owns its distribution-version and persistence details.

Initial configuration creates the account expired. Reconfiguration records its
original expiry in a private UID-bound transaction and expires it before
continuing. Successful PAM and confinement integration restores that expiry.
Interruption and reboot retain the barrier, including for an already
passwordless account. Foreign identities and changed transaction records are
preserved rather than adopted.

The [native PAM module](../../tools/pam_oh_no_parent_control.c) checks the actual
service and account. Terminal and SSH account admission are denied. GDM account
and session checks require the dedicated preference and Wayland transport; a
repaired preference still denies the current attempt. Root-owned no-follow
locks serialize routing, admission, preparation and lifecycle writers. Current
missing state, unsafe lock files and contention deny admission.

The [PAM integration](../../packaging/kiosk_confinement.py) preserves exact
original and generated PAM bytes. It audits logical lines, includes, substacks
and jumps so vendor control flow cannot skip the final session gate. Kiosk-only
guards skip direct keyring and namespace callbacks on open and close. Unknown
session modules, unsupported nested callbacks, added manager credential callbacks
and vendor drift currently require reconciliation. Ordinary accounts retain
vendor callbacks and settings. These are current compatibility constraints,
not a mandate to preserve that parser/module inventory in the replacement.

Saved preferences and a nologin shell do not attest to GDM's next executable.
GDM 50 does not invoke the retained legacy PreSession hook, and `GDMSESSION`
arrives too late. The final native boundary therefore runs in the PAM caller
after vendor session callbacks. Any replacement must cover actual final exec,
earlier children, manager startup and credential/session teardown before this
boundary can be reduced.

## Native execution and executable identity

The [native gate](../../tools/kiosk_confinement.h) selects the production
[fresh manager transaction](../../tools/kiosk_fresh_startup.h) for `systemd-user`
and [retained gate transaction](../../tools/kiosk_retained_startup.h) for
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

The bounded [preparation service](../../tools/kiosk_preparation_service.py)
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
the [implementation baseline](../Kiosk-Resilience-Plan.md#implementation-baseline)
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

The [target design](../Kiosk-Resilience-Plan.md#target-design) is blacklist-led and
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
The plan's [acceptance](../Kiosk-Resilience-Plan.md#acceptance) separates normal
compatibility fixtures from injected unsafe security negatives.

### Architecture decisions required before the entry proof

The replan did not settle these decisions. R01a's execution, R01b's
authentication, R01c's approval and R01d's
[configuration choice](Lifecycle.md#r01d-configuration-and-quarantine-decision)
are recorded in their owners; the remaining readiness decision and their
integration are still pending. R01 must
review one concrete supported design, its source/API basis and a finite proof
plan before R02a starts. The
[task breakdown](../Kiosk-Resilience-Plan.md#task-boundaries) allocates these
decisions to R01a–R01e and integrated review to R01; they are not additional
hardening projects:

- **Execution and activation authority:** identify the boundary at GDM's actual
  first execution, any earlier PAM children, the manager and its descendants,
  and open/setcred/close-session cleanup. Trace consumed unit paths, dependencies,
  drop-ins, user/environment generators, D-Bus activation and module/plugin
  searches, including reload. Decide which are excluded, deliberately consumed
  or confined. A private directory prepended to default searches, XDG autostart
  suppression or masks for known service names alone do not close automatic
  activation. Unknown unrelated services neither start unrestricted kiosk
  applications nor cause admission rejection.
- **Authentication policy:** identify effective account/access and empty-token
  policy separately from optional session callbacks and harmless PAM text.
  Choose a kiosk-scoped passwordless route that honors explicit administrator
  denial and preserves ordinary accounts. Unknown module names alone are not
  denial. Prove genuine parent authentication, including Fedora's privileged
  helper; blanket no-new-privileges/nosuid assumptions cannot disable that path.
- **Session and approval identity:** specify how request bus/process identity,
  the authentication agent and the exact logind session remain associated
  across manager reuse or renewal and competing visits. Resolve the broker's
  sessionless/primary-display fallback for this route. A new visit cannot adopt
  another visit's pending approval. Preserve the existing
  [pending-authentication cancellation contract](Broker.md#authorization-and-grant-transactions)
  and settle the [approval/commit ordering](Broker.md#prospective-kiosk-approval-lifetime),
  including transitions during post-authentication work. Specify when an approved
  original request may complete and when cancellation prevents writes; no late
  result can revive a cancelled request or supply authority to another visit.
- **Configuration and activation lifetime:** resolve the
  [prospective lifecycle decisions](Lifecycle.md#prospective-configuration-and-activation-recovery),
  including product quarantine versus administrator expiry, visibility repair,
  optional provisioning, cross-account broker startup prerequisites, update
  activation classes and the original recovery deadline. Readiness means a usable
  form with an available authentication path, including
  [native-language fallback](Localization.md#translation-lifecycle-and-shared-ui),
  not merely an active unit or a running process.

Record every retained rejection in one ledger here, including pre-GDM failures
that leave the station unavailable. Each needs its exact trigger and source,
reachable risk or effective policy/setup fault, insufficient recovery alternatives,
actionable diagnostic, legitimate-use positive control and negative control. The
[early proof](../Kiosk-Resilience-Plan.md#acceptance) must test the selected
mechanisms on both platforms before broad integration; documentation is no proof
that these decisions have been implemented or work.

### R01c approval and visit decision

**Selected, prospective lifetime:** use the
[Broker's visit association and effect-admission decision](Broker.md#prospective-kiosk-approval-lifetime),
with the visible behavior in the
[specification](../Specification.md#prospective-kiosk-visit-lifetime).
The protected native entry gate supplies the exact logind admission; the broker
owns visit/request identities and cancellation versus first-write ordering.
The fixed lifecycle controller owns only its pinned form/agent generations and
validated locale preparation, never general manager commands or approval power.
Manager reuse cannot reuse a visit, request or authentication result. Only one
live session owns the kiosk UID's manager globally, including across seats.

The kiosk's manager-launched form and stock MATE agent may use primary `Display`
only when it equals that exact admitted session; no sessionless kiosk approval.
Confine agent registration to the fixed agent role, including process-scoped
registration, so an unrelated service cannot divert the prompt. Start a fresh
owned agent for each activation after old requests/agent connections drain;
freeze that generation while authentication and post-authentication checking
remain cancellable. A unit job/PID is not registration or usable-authentication
evidence. Keep the genuine native prompt and vendor privilege path on both
platforms, including Fedora's helper transitions.

The broker's observer must keep dispatching during usage queries, termination
preflight and reversible account snapshot reads. Cancellation wins until the
single effect-admission claim just before the first policy write; afterward
only the original request may finish under unchanged transaction/rollback rules.
No late reply can revive cancellation or reach a later visit's result screen.
Competing logins preserve the owning live/foreign session, wait within R01e's
entry deadline and return an explicit already-open/retry result if it remains
occupied. R01e owns infrastructure recovery/deadlines, R02a the runnable slice,
R06 its recovery composition and R09b2/R10c2/R11c2 the two ordered race histories.
R01 still owns integrated independent architecture review; this is review-only
design, with no implemented or installed acceptance credit.

### R01b effective authentication decision

**Selected, prospective policy:** retain GDM's effective `auth` and `account`
policy, including its existing decision about empty credentials. Select a
kiosk-only session stack before the vendor desktop session stack. The package
does not add `nullok`, an early authentication-success rule, an autologin
service or a second authentication attempt with weaker policy. Passwordless
entry uses the package-owned kiosk identity's empty password only when the
existing GDM authentication stack accepts it and account management allows
access. A locked/nonempty credential, effective access denial or administrator
expiry is not repaired by deleting a password, changing policy or asking the
child for a kiosk password. This decision changes neither shipped policy nor
test expectations; R01 integrates and independently reviews it before R02a.

#### Current source and public mechanism

| Audited source/caller | Current behavior and selected consequence |
| --- | --- |
| [Shared profiles](../../data/pam-configs/oh-no-parent-control-kiosk-only), [time profile](../../data/pam-configs/oh-no-parent-control-session-limits), [Ubuntu lifecycle fragments](../../packaging/ubuntu.inc) | `pam-auth-update --package` adds account/session routing and child-time enforcement. Its kiosk/admin skips cover only product time modules, not the rest of authentication or account management. Neither profile grants empty-token authentication. Preserve that separation and ordinary child exhaustion enforcement. |
| [Fedora profile owner](../../packaging/fedora_pam.py) `configure`, `selection`, `verify_pam`; [stager](../../packaging/stage_distribution.py) `pam_profile`, `pam_stack`; [Fedora lifecycle fragments](../../packaging/fedora.inc) | The custom authselect profile copies the selected base, retains features and prepends the shared product rules with `wheel` replacing `sudo`. Both preinstall and first profile creation currently reject `without-nullok`. Keep the feature and original selection intact; the replacement must evaluate the effective kiosk route, not assume every unfamiliar profile is incompatible or that absence of that feature proves permission. Never use `--force` or edit generated system/password/fingerprint/smartcard stacks behind authselect. |
| [PAM packaging](../../packaging/kiosk_confinement.py) `pam_lines`, `validate_stack`, `guarded_sessions`, `audit_manager_credentials`, `rendered`, `verify_pam`, `install_locked` | Current rendering keeps vendor auth/account rules, appends the final session gate, skips two callback names and rejects unfamiliar session modules, manager auth additions and exact-byte drift. Replace this session inventory with the branch below. Exact before/after records remain transaction/rollback evidence, not an entry policy decision about harmless formatting. Preserve administrator edits and reconcile package updates through the lifecycle owner. |
| [Native PAM](../../tools/pam_oh_no_parent_control.c) `kiosk_identity`, `kiosk_account_check`, `pam_sm_acct_mgmt`, `pam_sm_authenticate`, `pam_sm_setcred`, `pam_sm_open_session`, `pam_sm_close_session`; [login check](../../tools/oh-no-parent-control-login-check) `main`, `verify_session`, `verify_confinement` | The login helper checks integration, service and saved/actual session routing; it does not evaluate passwords, shadow expiry or arbitrary PAM access rules. Normal native authentication enforces child time, not a kiosk password exemption. Account/session modes bind the GDM handle and route; the manager credential mode rejects authentication but permits kiosk setcred. Close currently returns success and PAM-data cleanup releases ownership. Keep route/integrity checks distinct from actual authentication/account results and strengthen lifetime handling in R02a rather than claiming the helper proves policy. |

The public basis is Linux-PAM's separate management groups and
[include/substack and return-action semantics](https://github.com/linux-pam/linux-pam/blob/v1.7.1/doc/man/pam.conf-syntax.xml).
PAM itself evaluates the selected auth/account rules, nested includes, substacks
and control flow; the product must not approximate their outcome with a module
name or a text signature. The
[pam_unix contract](https://www.man7.org/linux/man-pages/man8/pam_unix.8.html)
separates empty-password authentication from account/password expiry. The
[authselect base template](https://github.com/authselect/authselect/blob/1.5.0/profiles/sssd/system-auth)
shows `without-nullok` removing the Unix empty-token option; other auth rules
and account checks still contribute to the effective result. These are source
bases, not qualification of the installed Ubuntu/Fedora builds.

The [GDM 50.1 worker](https://github.com/GNOME/gdm/blob/50.1/daemon/gdm-session-worker.c)
`gdm_session_worker_authenticate_user` and `gdm_session_worker_authorize_user`
pass `PAM_DISALLOW_NULL_AUTHTOK` when `password_is_required`; remote displays
set that requirement. Preserve those flags and the supported local-display
boundary. Its account path can invoke `pam_chauthtok` on
`PAM_NEW_AUTHTOK_REQD`, so a kiosk-only password-group guard must reject token
changes before a password-changing callback can prompt or write. Ordinary
accounts retain that flow. Teardown closes only a fully opened session, deletes
established credentials and calls `pam_end`; partially completed open therefore
needs explicit PAM-data recovery, not reliance on GDM calling close.

#### Selected dispatch and callback lifetime

Keep `PAM_SERVICE=gdm-password` for the real GDM transaction and
`PAM_SERVICE=systemd-user` for its separate manager transaction. Do not switch
to `gdm-autologin`, rename policy services or copy just selected access modules:
service-sensitive administrator rules must retain their context. Preserve all
effective GDM auth/account includes, ordering, control actions and module data.
Account/access policy remains deliberately consumed trusted administrator code,
including an unfamiliar policy module. `PAM_NEW_AUTHTOK_REQD`, expiry, access
denial and authentication failure cannot become success in a product wrapper.
An unavailable/malformed policy check is a setup fault, not proof that an
administrator denied access or that the child attempted an escape.

Before GDM's vendor auth rules, a native kiosk-only prerequisite validates the
owned local identity and empty credential state without publishing shadow data.
It installs an empty-credential conversation for that handle using
[PAM_CONV via pam_set_item](https://github.com/linux-pam/linux-pam/blob/v1.7.1/libpam/pam_item.c).
Secret prompts receive only the empty response; other credential challenges
cannot solicit input from the child. Preserve the original conversation in
handle-owned data for safe restoration/cleanup and bound repeated challenges
within the entry deadline. This guard never authenticates on its own: all
vendor auth/account results and flags still decide access. A policy requiring
a password or another factor remains unsatisfied, with a clear refusal instead
of an unexpected kiosk password dialog. No ordinary-account or Polkit handle
receives this conversation. The kiosk password-group guard rejects both token
change phases; it never clears a lock, resets expiry or provisions a new secret.

Session dispatch is package-owned and bound to the verified kiosk identity,
actual service and the PAM handle. Ordinary accounts delegate to the original
session group unchanged. The kiosk uses a protected session-policy substack,
required core setup and the final native gate in fixed outer control flow.
The policy substack preserves the original non-optional rules and their native
control flow, including unfamiliar modules and effective session access denials.
Only ordinary `optional` desktop callbacks are excluded; extended return-action
controls, `required`, `requisite` and `sufficient` are not guessed to be optional.
Preserve include/substack boundaries and jump slots when replacing optional
callbacks with a kiosk-only inert result, rather than deleting lines and moving
jump destinations. Resolve nested session includes into protected kiosk-specific
counterparts; ordinary accounts keep the originals. Native PAM evaluates policy
results; `done`, `die`, `reset` and jumps inside the policy substack cannot skip
the outer required core/final gate. No module-name inventory decides admission.
An optional-only stack whose result itself controls access must retain that
effective policy, rather than being silently converted to success. This is a
policy-preservation obligation, not permission to assume all unknown code is a
desktop effect. R02a must exercise both account and required session denial and
native control-flow equivalence. Preserve local source edits and reconcile them
without overwriting administrator policy.

The finite GDM substack establishes login audit identity, resource limits and
keyring bookkeeping as needed, logind/runtime ownership through `pam_systemd`,
the selected manager and R01a's first-exec boundary. Fedora retains the ordered
vendor SELinux close/open setup needed for the GDM worker and pending exec
transition. The manager substack establishes its own required limits/audit/MAC
setup without recursively starting another manager. Do not duplicate core
setup already supplied by the policy substack. Desktop keyring daemons and
optional namespace/session effects do not execute on the kiosk branch. Required
administrator integrations remain deliberately consumed policy/setup, with their
children included in the pre-boundary proof; neither their unfamiliar name nor
a failed optional effect is a reason to reject entry. The exact packaged core
rules and policy projection must be source-reviewed and exercised by R02a;
including an unfiltered `common-session`, `password-auth` or `system-auth`
session group would reopen excluded callbacks. If a required integration exposes
an actual escape, isolate that reachable effect while retaining its access
decision; never turn its failure into success or add a name exception.

GDM's credential establishment/deletion continues the same effective auth
transaction, including required policy credentials and their paired cleanup;
do not replace `pam_setcred` with unconditional success. Auth/account callbacks
are trusted policy execution, not optional session integration. Any children
they create are part of R01a's pre-boundary proof, including failures; a pending
final-exec label does not confine them retroactively. For the kiosk manager,
retain a dedicated inert credential path for establish/reinitialize/refresh/
delete calls and an authentication failure, so neither vendor optional auth
callbacks nor implicit `other` credentials execute for that manager. Ordinary
manager auth/setcred behavior stays on the original branch. This manager is
not a second way to log in and its account policy still runs.

Open, failed-open recovery, close, delete-cred and `pam_end` use the selected
branch for the same handle. Record which required setup completed and release
only its owned state in the appropriate paired callback/destructor; preserve
the first failure and incomplete cleanup. Never rediscover a different branch
from changed account metadata during teardown. Required setup and policy results
cannot be ignored to admit the session. Optional excluded callbacks need no
kiosk open or close call; ordinary accounts retain both. R01c owns visit and
approval association; R01d owns account fields and quarantine release.

#### Parent authentication and proof allocation

Selected-parent approval remains the independent system Polkit transaction:
[the authorizer](../../broker/oh_no_parent_control/authorization.py)
`PolkitAuthorizer.check` passes the broker-validated approver and requesting
system-bus identity, and the [admin rule](../../data/polkit-1/rules.d/00-oh-no-parent-control-session.rules)
restricts the challenge to that parent. Kiosk entry success supplies no approval
or reusable management authority. Preserve the vendor Polkit PAM policy and
native conversation; product forms never receive the parent's password.
The [role policy](../../tools/kiosk_confinement_policy.py) `selinux` and
`apparmor` retains Fedora's live setuid `polkit-agent-helper-1`, transition to
`policykit_auth_t` and `unix_chkpwd`/`chkpwd_t` path; Ubuntu retains its vendor
root-helper service and password profile. No blanket NNP or nosuid mount may
disable those privileges, and no product copy/relabel of the vendor helper is
an acceptable substitute. A wrong password, denial or Cancel changes no grant
and leaves the confined form available for a fresh request.

[R02b](../Kiosk-Prompt-Tasks/R02b-pam-fixture.md) supplies an administrator-owned
benign unfamiliar `optional` session callback in the ordinary vendor include tree,
alongside successful required setup, with finite open/close effects. Separate
ordinary child and administrator controls prove the callback actually ran.
For the kiosk, prove the session branch did not invoke
that desktop callback, no early unconfined child appeared, and passwordless
entry, genuine selected-parent approval, Cancel, exit and reentry still work.
No fixture-name exception or weakened policy is permitted. R02a also pairs the
same effective access/expiry/empty-token policy with allowed and denied controls,
including a required session access denial, no secret prompt/token change,
setcred and failed-open teardown.
R03/R04 execute these complete histories on each platform; the selectors remain
unimplemented until R02 registers them.

[R07](../Kiosk-Prompt-Tasks/R07-pam-session.md) extends that proven route to valid
local auth/account include/substack/module variation, harmless comments,
whitespace, case and continuations accepted by native PAM, authselect features,
actual caller groups/umasks and saved-session repair. Pair each policy variation
with its effective denial and unchanged ordinary-role control. Unknown names,
formatting and excluded desktop effects alone are never entry vetoes. Native
PAM errors remain distinguishable from policy denial. R07 does not defer the
unfamiliar-callback or Fedora privilege proof from R02–R04. Historical parser,
exact-byte and module-list tests retain their old scope until R01 explicitly
maps them; R01b grants review credit only and creates no runtime resources.

### R01a execution and activation decision

**Selected, prospective mechanism:** keep the dedicated logind session, one
kiosk-only `user@UID.service` manager, GNOME Session, GNOME Kiosk and the shared
request form. Give that manager an exclusive package-owned unit graph and a
private `dbus-daemon` configuration on **both** platforms. Constrain the actual
GDM and manager first execution with AppArmor on Ubuntu and SELinux on Fedora.
Use narrow private mounts only for necessary entrypoint labels and excluded
configuration searches. Do not reconstruct `/usr`, clone the previous manager's
filesystem, inventory unrelated directories or maintain a universal executable
allowlist. This choice is a contribution to R01, not integrated architecture
approval, a shipped change or installed acceptance.

#### Audited current path and inherited authority

The local source route is
[PAM](../../tools/pam_oh_no_parent_control.c) (`pam_sm_authenticate`,
`pam_sm_acct_mgmt`, `pam_sm_setcred`, `pam_sm_open_session`,
`pam_sm_close_session`),
[routing](../../tools/oh-no-parent-control-login-check),
[native admission](../../tools/kiosk_confinement.h),
[fresh startup](../../tools/kiosk_fresh_startup.h) and
[retained startup](../../tools/kiosk_retained_startup.h).
[Preparation](../../tools/kiosk_preparation_service.py) `measure`,
`retained_plan`, `make_skeleton` and `serve` consume the account, policy and
material machinery in [confinement preparation](../../tools/kiosk_confinement.py).
`required_material`, `initial_directory_layout` and `InitialPreparation` currently
bind far more runtime/cosmetic material than this selected boundary needs.
[PAM packaging](../../packaging/kiosk_confinement.py) owns vendor-stack rewriting;
[policy generation](../../tools/kiosk_confinement_policy.py) owns the current
roles, private unit overrides and known-name D-Bus masks.

The upstream ordering is independently visible in
[GDM 50.1 session selection](https://gitlab.gnome.org/GNOME/gdm/-/blob/50.1/daemon/gdm-session.c),
[its worker](https://gitlab.gnome.org/GNOME/gdm/-/blob/50.1/daemon/gdm-session-worker.c),
[Wayland wrapper](https://gitlab.gnome.org/GNOME/gdm/-/blob/50.1/daemon/gdm-wayland-session.c)
with [environment reader](https://github.com/GNOME/gdm/blob/50.1/common/gdm-common.c),
and [systemd v259 executor](https://github.com/systemd/systemd/blob/v259/src/core/exec-invoke.c).
These sources explain ordering; R02a/R03/R04 must witness the installed builds.

| Stage | Actual current behavior and consequence |
| --- | --- |
| Selection/authentication/account | The saved Wayland desktop selects the fixed native session launcher, but preference repair is not a proof of the next executable. Routing/account checks precede final confinement. Effective access and passwordless policy belong to R01b. |
| GDM session open | `_change_user` sets the kiosk primary GID and calls `initgroups` before credential establishment and `pam_open_session`. Real/effective/saved/filesystem UIDs remain root at the native gate; GIDs are the kiosk primary GID and supplementary groups come from NSS. A root:root test caller with an empty group list is not this caller. |
| Manager startup | `pam_systemd` can start `user@UID.service` during session open. Its `systemd-user` PAM executor runs `setup_pam` before `enforce_groups`/`enforce_user`, after applying the unit umask. Normally it still has root UIDs/GIDs; earlier callbacks can affect credentials. `kiosk_fresh_startup_until` requires root effective/filesystem UID, prepares state and confines this separate execution ancestry before manager exec. |
| Final GDM gate | `kiosk_retained_startup_until` currently requires a measured live manager and clones its source. Ubuntu changes the current caller profile immediately. Fedora sets a pending gate exec context; this does **not** confine already-forked children or the waiting GDM worker. |
| Actual first exec | `gdm_session_start_session` wraps the desktop Exec in the absolute vendor `gdm-wayland-session` path. The worker forks, drops UID to kiosk, applies GDM `env.d` to PAM environment and executes that wrapper. `GDMSESSION` is supplied after PAM open and cannot select the native boundary. The wrapper, not the product launcher, is the first executable to prove. |
| Wrapper → form | The wrapper connects to a session bus, imports manager environment and starts the desktop command. On bus failure it can spawn PATH-resolved `dbus-daemon --session`, which would consume standard activation directories. Only later does [the fixed launcher](../../tools/kiosk_session.c) clear environment and exec `gnome-session --no-reexec --session=oh-no-parent-control`. The [session](../../data/gnome-session/sessions/oh-no-parent-control.session) suppresses XDG autostart; its [target](../../data/systemd/user/gnome-session@oh-no-parent-control.target.d/session.conf) starts compositor, app, agent and optional notification services. |
| Exit/teardown | The form service requests GNOME shutdown on success or exit. GDM's wrapper terminates/waits for its direct subprocesses, not all separately managed services. GDM's parent clears its pending exec context after fork; later it runs close-session, delete-cred and `pam_end` in its vendor context/root UID before process-group SIGHUP. Native `pam_sm_close_session` itself returns success; PAM-data destruction closes the admission lease, while unresolved transaction recovery can retain separate ownership/locks. Systemd's surviving `sd-pam` executes credential deletion/session teardown; Fedora's immediate manager-PAM domain covers it. No final-exec transition can retroactively protect earlier callbacks. |

Neither startup coordinator resets caller IDs, groups or umask. Native
`kiosk_private_creation.h` and Python `private_initialize` require effective and
filesystem root, explicitly set root:root and final modes on **proven newly
created** non-lock private objects, then validate them. New private lock files
instead preserve inherited GID and require the protected UID, exact `0600` mode
and named identity. Existing objects are validation only. Channel helpers inherit
the actual caller credentials. The replacement
keeps this initialization/ownership rule, without inheriting ambient layout
requirements or treating a legitimate kiosk GID/restrictive umask as hostile.

#### Closed consumers, not host cleanliness

The [systemd 259 environment interface](https://www.freedesktop.org/software/systemd/man/259/systemd.html#Environment)
supports replacing unit and generator search paths. Set `SYSTEMD_UNIT_PATH` to
the sole protected kiosk unit directory, and `SYSTEMD_GENERATOR_PATH` and
`SYSTEMD_ENVIRONMENT_GENERATOR_PATH` to protected empty directories **before
manager initialization**. No value ends with `:`; that would append defaults.
The current fresh transaction does end its unit path with `:` and therefore
does not implement this choice. Keep these settings through reload/reexec.
The [unit-loading contract](https://www.freedesktop.org/software/systemd/man/259/systemd.unit.html#Unit%20File%20Load%20Path)
also permits linked files and dependencies; an exclusive path alone is not closure.
The native gate constructs wrapper/manager startup environment from verified
account/session identity and finite validated locale/display fields, replacing
arbitrary inherited PAM loader/module/activation values before first exec.
Protected search paths and the bus address cannot be overridden by later
optional callbacks or GDM environment loading. This protects the wrapper's
loader too; clearing environment only inside the product launcher is too late.

| Consumer | Selected classification and mechanism |
| --- | --- |
| Manager units, aliases, dependencies and drop-ins | **Deliberately consumed:** a small package-owned full graph, including default/basic/socket/shutdown targets, GNOME session/Kiosk units, bus socket/service, fixed form/agent launchers and selected optional services. Follow implicit dependencies, `.wants`/`.requires`, aliases, template, dashed-prefix and type-wide drop-ins inside that graph. Do not symlink back to host units or inherit host `ExecStartPre`, `ExecStop`, `EnvironmentFile` or configuration fragments. Derive the finite graph from the installed GNOME 50 units during implementation and record it as package source; missing essential graph members are setup faults, not reasons to enable default searches. |
| Host user units, transient/control directories and both generator classes | **Excluded:** replacement paths omit host and home roots, including generator outputs. Do not enumerate or mask unfamiliar names. Disable generator execution itself, not just its output directories. Apply the same rule at first startup, reload and reexec. |
| Manager `user.conf` and its vendor/admin/home drop-ins | **Excluded from this kiosk manager:** narrow private configuration mounts provide the fixed manager settings and empty drop-in roots before exec. These searches are independent of `SYSTEMD_UNIT_PATH`. Ordinary user managers retain their configuration. Root system-manager `user@UID.service` integration is deliberately consumed trusted administrator authority, not a user activation search. |
| Manager D-Bus and private control socket | **Confined:** only fixed trusted GNOME bootstrap/lifecycle code receives the manager operations it needs. Deny app, exposed services and optional helpers general transient-unit creation, unit linking/property mutation and arbitrary environment imports; prevent bypass through `systemd/private` with role MAC. Message-bus rules alone cannot inspect command/unit argument values. The trusted controller uses fixed unit names and validated values, and no public UI forwards arbitrary manager requests. Current broad Unix/D-Bus role grants must be narrowed before removing old execution restrictions. |
| Session bus and automatic activation | **Deliberately consumed:** package-owned `dbus.socket`/service launches `dbus-daemon` with an explicit standalone config, not the distro session config. Use `--address=systemd:` to adopt the listening socket and a compatible service readiness/stop contract. Provide only a protected finite service directory; omit standard service-directory expansion, host includes, servicehelper and `--systemd-activation`. Private activators use fixed absolute Exec launchers, not `SystemdService`. Thus no broker-created transient-unit dependency is needed; ordinary Fedora users keep their usual bus. Reload reads the same protected configuration. See the [D-Bus daemon interface](https://dbus.freedesktop.org/doc/dbus-daemon.1.html). |
| GDM wrapper bus and environment | **Confined/excluded:** supply the verified manager-owned bus address before GDM's first exec; bound readiness/recovery before handing it to the wrapper. Do not connect to an unverified existing bus. Deny wrapper execution of its fallback daemon/`dbus-launch` path by role, while the dedicated bus launcher may start the configured daemon. Bus loss must recover within the original entry budget or produce a precise unavailable result, never standard-config fallback. Import only sanitized controller-owned manager environment. Mask GDM's finite vendor/admin `env.d` roots in this caller's private namespace, preserving ordinary accounts; the fixed launcher's clearenv boundary otherwise arrives too late. |
| GNOME autostart and external handlers | **Excluded:** retain `Kiosk=true` and fixed session selection, but also close bus/unit activation above. No kiosk UI exposes URI/file/application handlers, choosers, portals or a general launcher. Suppress the affected optional action, not the whole session. System-bus access remains explicit for broker, AccountsService, logind, GDM and Polkit operations; it must not expose host service launch/management APIs through a permissive proxy. |
| Code, loader/module/plugin/config searches | **Deliberately consumed or confined:** fixed native launchers use absolute commands, Python `-I`, cleared interpreter/loader/plugin environment and protected XDG config/data-home roots. Trust distro/package native libraries and system modules only where the child cannot write them; keep writable caches/preferences data-only. No cwd/home module fallback. GTK/GIO/GJS, GNOME, driver, image/media and audio loaders require concrete search-route controls, not identity of every host sibling. Retain WirePlumber's system config/data roots and empty Lua default paths if enabled. Optional helpers without a closed search/launch boundary stay disabled until qualified; form and genuine approval remain required. |
| Agent locale and privileged authentication | **Confined, not cosmetic:** the current agent unit directly imports a kiosk-owned `polkit-agent.env`. Replace arbitrary EnvironmentFile consumption with a fixed launcher accepting only validated locale keys/values; retain the controller's required fixed agent restart. R01c/R08b own association and locale fallback. Fedora retains the live vendor helper inode, privilege mode, SELinux transition and `unix_chkpwd` route; do not impose blanket NNP/nosuid or copy/relabel the vendor helper. Ubuntu retains its vendor root-helper service. |

This is a finite service/consumer contract, not a catalogue of all executable
basenames. Renamed programs do not gain an exposed handler, activation or
management route. Role MAC protects entrypoints, control sockets, privilege
transitions and child-writable executable mappings; it need not recognize every
unrelated installed application. It does not claim containment after arbitrary
code compromise. Existing direct-exec engineering assertions keep their current
scope until R01 explicitly maps them; this decision edits no tests.

For the module row, **excluded** means no home/cwd Python, GI, GJS, GIO/GTK,
GStreamer, Lua or driver override: clear `PYTHON*`, `GI_TYPELIB_PATH`, `GJS_PATH`,
`GIO_EXTRA_MODULES`, `GTK_PATH`, `LD_*`, `GST_*` and driver override variables
before their respective consumers, not just before the form. **Deliberately
consumed** defaults are the package's Python/JS roots and the distribution's
native library, GI typelib, GIO/GTK module and graphics-driver roots, with actual
child write/replacement authority excluded. They are trusted installed code,
not an inventory that must match a clean image. Protected XDG config/data-home
roots exclude user plugins and GNOME session overrides; fonts/themes/icons are
presentation data and must not grant code or handler authority. **Excluded
initially:** GStreamer's implicit system/home plugin discovery (including the
native Python plugin), using explicit protected empty plugin roots rather than
merely clearing variables that restore defaults. Optional audio/media/rich
rendering can be enabled only with its own closed consumer route; failure uses
the shared form's fallback. Required image decoders remain role-confined native
helpers using trusted system format configuration, without home loader overrides
or onward external-launch authority. R02a must demonstrate these actual defaults
and R01 must resolve any required consumer that cannot satisfy this classification.
Registry caches containing module paths are executable selection inputs, not
inert preferences. Disable cache replay where the consumer cannot revalidate it
against protected roots; an old GStreamer registry must not reopen excluded
plugin discovery. Writable cache contents never authorize executable mappings
or external launches.

Fedora may need independent product-owned copies and exact-file binds for the
GDM/manager entrypoints requiring private SELinux types; never relabel distribution
inodes globally. Ubuntu uses its verified immediate profile transition. Preserve
trusted pre-exec setup and `sd-pam` teardown authority separately from descendant
application authority. The kiosk-only session branch must select required
callbacks before vendor optional session callbacks execute, including manager
PAM. Unknown optional callback names neither run unrestricted nor reject entry;
[R01b's decision](#r01b-effective-authentication-decision) preserves effective
policy while selecting those callbacks. R01 must review the composition.
A pending exec label or a late launcher cannot satisfy that obligation.

For every actually consumed input, establish the relevant kiosk/child UIDs,
supplementary groups, POSIX ACLs, ancestor traversal/replacement authority and
resolved alias target. The personal child and kiosk UID are distinct; kiosk-owned
HOME alone does not prove a public child write route. Pair a reachable writable
input negative with a trusted-administrator-only group-writable positive.
Do not reject on group mode bits alone or inspect unrelated sibling contents.

A read-only bind is not an immutable-byte guarantee. Small product-owned
entrypoint/configuration snapshots use independent inodes, cannot be written by
the child and remain owned until their invocation drains. Live distribution
libraries and the privileged helper remain trusted administrator/package inputs;
no exact old-byte lifetime is claimed for them. Product publication is serialized
with entry; R01e must settle relevant dependency updates and safe renewal without
adopting a stale active visit. This is not an image-generation/cache framework.

#### Single decision/rejection ledger — execution contribution

This is the ledger R01b–R01e and R01 extend, not a second policy table. Causes
below are proposed sanitized diagnostic categories, not newly registered events.
Each negative needs its permitted control and a public usable-entry result after
restoration; a safety refusal grants no positive availability credit.

| Predicate and current source | Decision, risk and recovery limit | Positive / negative control; customer explanation; sanitized cause |
| --- | --- | --- |
| Ambient siblings, encoding, inventory budgets; `directory_layout`, `runtime_input_specs`, fresh/retained staging | **Remove admission dependency.** Unconsumed host contents create no child launch route. Cosmetic assets degrade; never reconstruct the old tree to recover. | Extra apps, odd names, unrelated writable siblings and missing artwork still enter / child-writable consumed module cannot load. “A display effect is unavailable; requests still work.” `optional-resource-unavailable`. |
| Actual identity and required privilege; `kiosk_fresh_account_until`, native admission and routing | **Retain narrow setup/route refusal.** Wrong or privileged identity cannot be safely adopted. Repair only proven owned state; never start unrestricted. TTY/SSH/alternate desktop remain forbidden while the dedicated route stays usable. | Real GDM groups/umasks and dedicated entry succeed / foreign UID, wrong session, TTY/SSH route denied. “Use the request station option at sign-in”; essential identity failure: “The request station needs its account setup repaired.” `route-not-permitted` / `account-identity-unavailable`. |
| Child-write authority on essential code/config/activation; `trusted`, native path proofs, fixed launchers | **Exclude input/route first.** Actual injection into a consumed essential input is a reachable execution risk; reject only if protected replacement cannot establish the essential boundary. Unknown names and trusted-admin group write are insufficient. | Administrator-only writable group path works / child ACL/group permits replacement of a consumed input, so it is excluded or entry safely stops. “The request station cannot safely load a required component.” `consumed-input-untrusted`; record recovery outcome without paths/user data. |
| Loaded enforcement/entrypoint; `enforcing`, native MAC application and policy authority | **Retain essential-boundary refusal after owned repair.** The failed operation must establish confinement; optional inventory/attestation diagnostics are not substitutes. Preserve Fedora helper privilege. | Actual wrapper/manager/form/approval succeed / required MAC operation fails, no unrestricted exec, restored enforcement permits entry. “The request station's protection could not start; retry after setup is repaired.” `execution-boundary-unavailable`. |
| Host unit/generator/D-Bus/plugin activation; current trailing-colon unit path and generated known-name masks | **Exclude consumption; confine exposed control routes.** An unfamiliar automatic external-launch provider must not acquire kiosk launch authority or veto normal entry. Reload cannot reopen it. | Unfamiliar fixture automatically activates and exposes its action for an ordinary account; kiosk still approves / same public action cannot launch an outside application in kiosk, including after reload/reentry. “This action is unavailable at the request station.” `launch-route-excluded`. |
| Exact retained manager/material equality, contention and inherited caller state; retained gate and preparation locks | **Recover, not exact-manager refusal.** Serialize and wait within one deadline; renew only a proven owned inactive/failed instance with no live visit. Preserve healthy/live/foreign instances. No reboot for unrelated drift. R01c selects exclusive live-session ownership and wait/return-to-sign-in for competitors; R01e sets the deadline/recovery. | Reentry, valid inherited GIDs/umask and owned stale renewal succeed / foreign/live replacement remains untouched, no partial startup escapes. “The request station is starting; try again when ready.” Occupied: “The request station is already open; return to it or retry after it closes.” `startup-wait` / `owned-renewal-failed` / `session-conflict`; retain original cause. |
| Pre-boundary callbacks and teardown; vendor PAM rewriting, final gate, PAM-data cleanup | **Select kiosk callbacks and preserve confined lifetime.** Final exec cannot repair an earlier unrestricted callback child. R01b retains effective administrator denial while excluding optional session integration by branch, not module-name exceptions. | Unfamiliar benign callback demonstrably works for ordinary accounts; kiosk still enters/approves/exits / no callback-created unconfined kiosk launch and no orphan authority after failed open, close or delete-cred. “The request station could not finish starting or closing; retry.” `session-boundary-unavailable`; unfinished owned cleanup prevents renewal credit. |
| Effective GDM authentication/account/session policy; native PAM results, shared profiles and Fedora authselect selection | **Honor effective denial.** Run preserved policy with its real service/items/control flow. No global `nullok`, alternate auth service, success bypass or automatic removal of administrator expiry/credentials. An unfamiliar module or harmless source change is not denial. Product quarantine recovery belongs to R01d. | Existing policy permits empty-token kiosk entry and ordinary child/admin authentication stays unchanged / effective empty-token prohibition, locked credential, account or required session access denial, and administrator expiry remain denied; restore the fixture and obtain usable entry. “This computer's sign-in policy does not allow the request station.” `authentication-policy-denied` / `account-policy-denied`; report the failing management group and restoration outcome without credentials or identity data. |
| Required policy/setup evaluation unavailable; PAM loader/result and login helper integration checks | **Report a setup failure, not administrator denial.** Retry transient prerequisites within R01e's budget; never grant success through a fallback stack. Missing required enforcement cannot be degraded, while optional callback failure/name/text alone cannot establish this predicate. | Valid include/substack/formatting and unfamiliar benign callback controls enter / actual required module/load or core setup failure prevents unrestricted entry, restoration permits entry. “The request station could not check a required sign-in setting; retry after setup is repaired.” `authentication-policy-unavailable`; preserve original cause and owned cleanup result. |
| Selected-parent Polkit authorization and vendor privileged helper; authorizer, admin rule and role policy | **Retain genuine authentication independently of kiosk entry.** No reusable approval, different-parent fallback, global null-token change, blanket NNP/nosuid or copied/relabelled Fedora helper. A denied request leaves the form usable. | Selected parent's genuine credential grants once on Ubuntu and Fedora / wrong password, Cancel, other identity or unavailable required helper grants nothing; a fresh permitted request succeeds after restoration. “Request denied” for denial; Cancel returns silently; unavailable authentication offers retry/exit. `parent-authentication-denied` / `parent-authentication-unavailable`; retain finite causes only. |
| Originating visit and native-agent association; `_session_for_caller`, `User.Display`, fixed controller/agent and `KioskAgentLocale.prepare` | **Pin the exact admitted visit and agent; cancel affected stale work.** UID, live bus name, active unit/job or primary-display fallback alone can associate a prompt with another visit. No kiosk sessionless fallback or foreign agent takeover; deny other roles' agent registration, including process-scoped registration. Replace only an owned drained agent, then require fresh authentication. | Fresh/reused-manager entry with exact session and genuine selected-parent approval / changed/empty/foreign Display, old agent on reentry, competing seat or agent replacement during usage cannot transfer authority; fresh request succeeds after safe restoration. Cancellation returns silently; unavailable agent offers retry/exit. `visit-ended` / `agent-association-unavailable` / `session-conflict`; log correlation and finite causes, never bus/session/PID/account data. |
| Pending authentication and post-authentication reads; `_PendingAuthorization.run`, `auth_done`, `_request_access`, preflight and `_apply` snapshots | **Extend cancellation to effect admission.** An authentication-only latch and bus-name check cannot protect an ended visit during slow reads. Keep an independently dispatching observer and a single cancellation/admission decision after all read-only work. No writes or termination if cancellation wins. | Active visit completes a genuine request / pending prompt or delayed usage/preflight/snapshot followed by switch/exit stays cancelled after late completion; reentry has no old prompt/result and fresh approval succeeds. Silent cancellation, with retry on the new visit. `visit-ended`; retain request correlation and cancellation/cleanup outcome only. |
| Original request after first-write admission; `_apply`, `_restore`, `_restore_after_termination` and request cooldown | **Complete only the admitted original transaction.** Departure cannot retract irreversible effects or confer approval on another visit. Preserve current arithmetic, timestamps, child-only effects and rollback; admission alone is no success guarantee. No restart replay. | Release delayed usage while active, witness admission, switch/exit before writes, then observe exactly one original grant and fresh approved reentry / injected transaction failure retains the existing before/after-termination rollback assertions, never false success or transferred authority. New visit shows its own form; transaction failure remains actionable on the original connection where available. `transaction-failed` / `rollback-failed` are prospective finite categories; current diagnostics remain unchanged. |
| Required public/durable visibility and routing; `accounts_service_cache_kiosk`, `_kiosk_cache_visibility`, `_verify_accounts_service_cache_version`, `repair_kiosk_visibility`, `accounts_service_set_kiosk_session` | **Repair by recognized representation and public result.** R05a removes version identity as a veto, retains the clean no-write path and bounds retained repair to one serialized restart/verification. Unknown/ambiguous actual schema gets no private write. A station that cannot be shown or routed is a setup failure, not an attack. Cache deletion, uncaching or unrelated setters cannot safely substitute for preserving metadata. | Compatible unfamiliar version and hidden retained account recover with other bytes/xattrs/ordinary users unchanged, public visible/saved state, entry and approval / ambiguous key-file or missing required public capability remains unchanged and cannot falsely complete setup; restored input recovers. “The request station could not finish its sign-in setup; retry after setup is repaired.” `visibility-schema-unavailable` / `visibility-result-unavailable`; retain first failed result and repair outcome, never cache contents/version strings as authority. |
| Visibility publication ownership/quiescence; `_recover_visibility_transaction`, fixed slot/xattr and AccountsService start-pre boundary | **Recover only exact owned publication.** Wrong UID/home, unsafe path, changed source/metadata/slot or a running writer cannot be overwritten. Recover the matching interrupted slot/committed marker; bounded wait for the actual start boundary, then preserve unresolved state. A blind write or repeated restart risks account metadata and ordinary-user availability. | Interruption before/after rename finishes owned recovery and usable entry / foreign/replaced slot or wrong daemon phase is preserved, not deleted/adopted; restoration then passes. “The request station's saved sign-in settings could not be safely repaired.” `visibility-ownership-unavailable`; finite phase/cause and cleanup result only. |
| Required pre-GDM setup; `provision.main`, template/config/bus policy validation, kiosk `LimitType`, postinst migration/PAM/service/final confinement operations | **Keep closed only for the actual required failure.** R05b releases the separate gate after verified required setup. Missing authorization/configuration or confinement cannot be replaced by display defaults. Retry owned transient work within R01e's budget; never copy untrusted inputs, erase admin edits or report an optional failure as missing enforcement. Broker readiness/activation after release is separately owned by R01e. | Correct setup with icon failure completes and enters / actual required config/routing/limit/PAM/enforcement failure stays closed without unrestricted entry; restore the failed requirement and recover once. “The request station's required setup did not finish; retry after setup is repaired.” `configuration-required-unavailable`; record failed required operation, first cause and recovery outcome without account data. |
| Temporary configuration gate and initial account creation; `configure_account_access`, native admission lease, postinst account creation/UID marker and unconditional credential deletion | **Replace temporary shadow expiry with product-owned durable state.** R05b bootstraps/verifies the gate before creation, binds nonce/UID/GID and staged home before visibility, and releases only its own ready transaction under lifecycle serialization. Native creation is not atomic: the [fixed-account completion matrix](Lifecycle.md#separate-configuration-gate-and-expiry-authority--r05b) permits only absent native-record initialization under the shared native lock. Missing/foreign/unsafe gate or unproven creation cannot authorize entry. Preserve live visits, present native expiry/credentials and ordinary-user data; no repeated password deletion or name/home-only adoption. | Interrupted bootstrap/native records/home/binding/configuration/ready publication recover after required setup with no administrator action; both ordered administrator-write races preserve denial and ordinary users / foreign identity/record, required failure or live-visit conflict is preserved; restoration permits entry. “The request station is finishing setup; retry when it is ready”; unresolved ownership: “The request station's account setup could not be safely recovered.” `configuration-in-progress` / `configuration-ownership-unavailable` / `session-conflict`; retain bounded phase/cause and recovery, no nonce/UID/shadow data. |
| Native administrator expiry/credentials and legacy v1 quarantine; `kiosk_account_expiry`, v1 record/release and effective PAM policy | **Preserve independent policy; never infer writer identity from equality.** New gates never write native expiry. Earlier/later denial, including same-value writes, survives release. A legacy current expiry differing from its captured value has no trustworthy provenance: retain both and require explicit administrator reconciliation, rather than guessed restore. No blind reset or timestamp/log heuristic supplies that authority. | New owned quarantine recovers with unchanged allowed expiry and usable approval / prior/later expiry=1, same captured-value write or credential lock still denies; legacy ambiguous expiry stays unchanged and is not counted as availability success. After explicit administrator reconciliation, required setup and a permitted control must succeed. “The request station's account is disabled or an earlier setup cannot safely decide its sign-in setting; an administrator must review it.” `account-policy-denied` / `legacy-quarantine-ambiguous`; distinguish known effective denial from missing provenance and retain only finite cause/reconciliation outcome. |
| Optional provisioning icon; `accounts_service_set_icon_file`, `accounts_service_provision_kiosk`, postinst release caller | **Degrade without rejecting setup.** R08a bounds and isolates icon get/parse/set failures, then continues required verification and owned gate release. Preserve retained artwork; default display requires no second successful icon call. No confinement or administrator policy is relaxed. | Failed icon lookup, malformed icon metadata and failed setter each still yield visible entry and genuine approval after required setup / pair the same icon fault with required-enforcement failure: gate stays closed; separately, administrator denial remains effective even after required setup publishes ready, with no false entry. Restoration recovers. “The account picture is unavailable; requests still work.” `optional-icon-unavailable`; preserve original cause through recovery without icon paths/content. |

#### Proof handoff and unresolved integration

R02a must witness actual credential tuples (including fsuid/fsgid and NSS groups),
umask, first executable, pre-boundary children, enforcing labels and owned state
at GDM open/establish-cred, manager PAM/exec, wrapper, compositor/form, failed open,
exit, delete-cred and close. Keep identity-bearing engineering observations in
private test evidence; automatic diagnostics use roles and finite causes only.
Track GDM's worker, setup helpers, manager executor/`sd-pam`, bus and services by
their recorded live identities. Demonstrate that wrapper fallback cannot acquire
a standard bus and that reload/reexec cannot add host searches or transient
launch authority. No successful preparation/process census substitutes for the
passwordless form and genuine parent approval on each platform.

R02b supplies the unfamiliar PAM callback control. R02c supplies one unfamiliar
administrator-owned automatic-service/external-launch fixture with an effective
ordinary-account control, kiosk public-action negative, approval positive,
reload/reentry observation and restoration. Exercise automatic activation itself;
do not add its name to masks or assume child code execution. R03/R04 run the
complete early proof on Ubuntu/Fedora, including Fedora's privileged helper.
All selectors for this replacement proof are still **unimplemented** here.

R01 must resolve the remaining cross-boundary obligations before implementation:
composition of R01b's selected account/authentication and callback policy with
[R01c's selected visit/agent/controller authority and effect-admission ordering](#r01c-approval-and-visit-decision);
[R01d's selected provisioning/quarantine ownership](Lifecycle.md#r01d-configuration-and-quarantine-decision);
R01e's single readiness/recovery budget,
safe manager renewal and update activation classes. In particular, the fixed
controller's manager methods, logind association and sanitized agent restart
must compose with R01c without giving the form general manager access. R01 owns
the mandatory independent architecture review, legacy-assertion mapping and any
revision of this choice. R01a creates no runtime resources and claims review only.

## Roles, services and dialogs

The [generated role policy](../../tools/kiosk_confinement_policy.py) separates
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

The [bubblewrap launcher](../../tools/kiosk_bwrap.c) supplies a read-only
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
[scope reconciliation](../Kiosk-Resilience-Plan.md#scope-reconciliation) when their
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
| 21 | Use a decoder/sandbox helper for onward exec or host mount changes. | Finite decoder route has no onward exec; namespace administration belongs only to bootstrap roles. [Role policy](../../tools/kiosk_confinement_policy.py), [bubblewrap assertions](../../tests/integration/system_kiosk_confinement.py#L1245); unknown vulnerabilities are outside this proof. |
| 22 | Turn the password helper into a privileged launcher. | Finite vendor helper transition checks credentials, label, parent and pinned executable/namespace. [Helper assertions](../../tests/integration/system_kiosk_confinement.py#L197), [public authentication](../../tests/e2e/restricted_station.py). |
| 23 | Change the station desktop or manage parent policy. | Root routing/Polkit and independent broker roles protect those operations. [Routing recovery](../../tests/integration/system_kiosk_admission.py#L363), [broker matrix](../../tests/system/test_authorization.py#L114). |
| 24 | Use package replacement/reexec to acquire new unrestricted code. | Current private directory dentries preserve code/library inputs; manager thread boundaries remain checked. [Replacement/reexec assertions](../../tests/integration/system_kiosk_confinement.py#L1510). |
| 25 | Retain a manager across required configuration changes. | Current exact material/receipt checks can require reboot. Availability and safe renewal replace that mechanism under the [new acceptance contract](../Kiosk-Resilience-Plan.md#acceptance). [Existing configuration check](../../tests/integration/system_kiosk_confinement.py#L2015), [generation refusal helper](../../tests/integration/system_native_update.py#L743) remain current tests. |
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
[acceptance](../Kiosk-Resilience-Plan.md#acceptance) requires both platforms and
does not transfer historical passes to the replacement design.
