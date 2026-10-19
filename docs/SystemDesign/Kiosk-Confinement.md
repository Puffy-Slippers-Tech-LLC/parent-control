# Kiosk confinement

The dedicated request station lets a child ask an administrator for more time
without gaining a desktop, terminal, application launcher or policy-management
session. Confinement covers the package-created `oh-no-parent-control` account,
its graphical session, user manager, services and native helper processes.
The child's personal desktop is a separate account: its time and application
restrictions belong to [Screen time](Screen-Time.md) and
[Application policy](Applications.md).

## Security boundary and assumptions

The attacker is a non-administrator child who can operate the request station
and prepare files in their own account. Engineering tests additionally plant
kiosk-owned files, submit service requests and vary trusted configuration as
root to challenge boundaries that the public UI does not expose. Those fixtures
give the defense stronger inputs; they do not imply that a child can normally
write root-owned policy or invoke privileged test helpers.

The trusted base comprises the kernel, enforcing AppArmor or SELinux, root-owned
package and distribution code, PAM, systemd, GDM, AccountsService and Polkit.
The implemented platform boundary is Ubuntu 26.04/GNOME 50 with AppArmor and
Fedora Workstation 44/GNOME 50 with enforcing SELinux. Fedora confinement
qualification does not change the product's overall
[release qualification](../System-Design.md).

The required invariant is that every admitted kiosk execution route remains
inside its permitted role, executable generation and private mount namespace.
Failed integrity, policy, routing or generation checks deny admission. A UI exit
returns to sign-in; it does not create an unrestricted station desktop. Successful
administrator authentication authorizes the selected request, not general kiosk
execution or management rights.

The scenario catalogue below covers the implemented attack surfaces and their
maintained proof obligations. It is not a mathematical proof of an
“unbreakable” system or an exhaustive list of unknown vulnerabilities. Kernel or
trusted-service exploits, stolen administrator credentials, administrator policy
changes and booting another operating system are outside this boundary. Native
gestures without a qualified automation route have no implied passing result.

## Admission and account integrity

[Provisioning](../../tools/provision.py) creates a non-administrative account with
`/usr/sbin/nologin`, the dedicated Wayland session and durable visible/saved
AccountsService classification. Only its recorded UID and reserved home qualify;
the child cannot select another identity by supplying a name. The product's
Polkit rule denies the station changes to its own AccountsService metadata.
The guarded classification adapter preserves unrelated metadata and ordinary
accounts; [Lifecycle](Lifecycle.md#startup-login-and-update-lifecycle) owns its
distribution-version and persistence details.

Initial configuration creates the account already expired. Reconfiguration
records its original expiry in a private UID-bound transaction and expires it
before continuing. Only successful PAM and confinement integration restores that
expiry. Interruption and reboot retain the barrier, including when the owned
account is already passwordless. Foreign identities or changed transaction
records are preserved and refused.

The [native PAM module](../../tools/pam_oh_no_parent_control.c) checks the actual
service and account. Terminal and SSH account admission are denied. GDM account
and session checks require the dedicated preference and Wayland transport; an
invalid preference is repaired but the current attempt still fails. Root-owned
no-follow locks serialize routing, admission, preparation and lifecycle writers.
Missing state, unsafe lock files and contention fail closed.

The [PAM integration](../../packaging/kiosk_confinement.py) preserves exact
original and generated PAM bytes. It audits logical lines, includes, substacks
and jumps so vendor control flow cannot skip the final session gate. Kiosk-only
guards skip direct keyring and namespace callbacks, including their teardown
operations. Unsupported nested callbacks, credential callbacks or vendor drift
require reconciliation. Ordinary accounts retain vendor callbacks and settings.

Saved session metadata and a nologin shell are insufficient to constrain GDM's
actual next executable. GDM 50 does not invoke the retained legacy PreSession
hook, and `GDMSESSION` arrives too late. The final native execution boundary is
therefore enforced in the PAM caller itself, after vendor session callbacks.

## Native execution and executable identity

The [native gate](../../tools/kiosk_confinement.h) validates the root-owned
mode-0600 preparation lock and mode-0700 runtime tree, invokes bounded
[preparation](../../tools/kiosk_confinement.py), attaches a private read-only
executable view, clears PAM-granted ambient capabilities and installs mandatory
access control. No subprocess runs after the final MAC operation.

Ubuntu immediately changes and verifies the caller's enforcing AppArmor profile.
Fedora GDM receives a verified pending SELinux exec context whose private
entrypoint type constrains the actual next executable. Fedora's single-threaded
systemd executor instead enters the current `onpc_kiosk_manager_pam_t` domain
before returning from PAM. Its surviving `sd-pam` child remains confined through
credential deletion and teardown. There is no unconfined waiting-helper exception
or reverse dynamic transition.

Preparation verifies enforcing policy, the successful-load attestation and the
exact configuration/policy digest pair before measuring a finite native ELF
inventory. Trust includes lexical aliases, original ancestors and every symlink
target chain. Copies use independent root-owned inodes; global distribution
executables are neither hardlinked nor relabelled. An owned directory skeleton
pins executable, library and plugin parents, with read-only sibling binds, and
is attached recursively over `/usr` in a private mount namespace. Package
unlink/rename cannot detach these private dentries and expose replacement bytes.
Versioned systemd libraries remain coherent across manager reexecution.

Unrelated sibling directories owned by a non-root user or writable by a group
or by everyone become empty private directories in the kiosk view. Non-root
ownership requires masking even without write bits, because the owner can
change those permissions. Untrusted sibling files/symlinks, special types,
names or link text that cannot be represented by the bounded UTF-8 protocol
(including separators and control characters), and unavailable sibling metadata are
omitted. Their contents and aliases are never bound into the kiosk. This handles
unknown applications generically, including root-owned mode-0775 data and
user-owned mode-0755 data, without changing the host. Group root receives no
trust exception. Required executable files, lexical aliases, their trusted
ancestors, reserved directories and every native bind must retain their ownership
and write prohibitions; their failures must never become sibling omissions.
Inventory retains selected lexical aliases, including installed optional routes.
The layout uses their full component/target proof closure, scanning only concrete
directories. A lexical child below a directory link is an explicit proof rather
than an impossible second private dentry. Every measured destination and concrete
required node must have its unique intended layout kind/link before manager
matching or generation writes. Final publication rechecks the complete proof
closure against the layout's required types and link text; transient disappearance,
retargeting or metadata failure refuses rather than forgetting the dependency.

Closed aggregate directory classifications identify mask/omit/refusal action,
reason, entry kind, ownership, access, required/sibling scope and broad system
area without names or paths. The feedback collector projects these and the
preceding admission stages under the
[admission diagnostic contract](Logging-and-Feedback.md#kiosk-admission-diagnostics).
The classification and publication repairs have host coverage recorded in the
[kiosk prompt plan](../Kiosk-Prompt.md). Native installed isolation and
retained-manager availability after ambient layout changes keep their separate
acceptance obligations there.

The manager must have the expected UID, enforcing label and exact private
generation before GDM admission. A stale manager requires reboot; configuration
does not kill or replace it. Completed generations survive until reboot.
Preparation admits at most four generations per boot, 32,768 directory entries
and 512 MiB of executable/library input per generation. Only owned incomplete
preparations are reclaimed under the exclusive lock.

### Planned post-layout ambient binding

The **002aa design** is implemented with host acceptance recorded at
[002ab](../Kiosk-Prompt.md#post-layout-ambient-binding-implementation--002ab).
The historical heading remains a stable reference anchor. This mechanism covers one
preparation's published layout through native attachment; it does not select a
previous admission's material. The complete layout remains in the generation
digest, and `manager_generation()` keeps its exact comparison. Material identity,
retained source pins and ambient changes **between** preparations remain with
005a–007 in the [entry queue](../Kiosk-Prompt-Queue.md).

**Invocation-local skeleton.** Do not unlink a shared generation placeholder or
retry preparation to recover an ambient bind. While holding the existing
admission lease and exclusive preparation lock, the native PAM caller validates
the service-derived `manager` or `gate` role, creates its private mount namespace
and makes propagation recursively private **before** starting preparation.
It validates one fixed, empty, root-owned mode-0700 staging directory,
`/run/oh-no-parent-control-confinement/native-view`, without following links or
adopting an existing mount. It mounts a new, bounded tmpfs there and records the
namespace, mount identity and opened root descriptor. Each invocation gets a
different filesystem even though the mountpoint spelling is fixed. The ordinary
host directory remains empty; no persistent per-login directory is allocated.

Preparation inherits that namespace and the existing locks. It still creates or
verifies the shared generation, its copied executables, `records.json`, exact
tree and generation marker as today. It then uses `make_tree()` to construct a
second skeleton under `native-view/tree`, from that same reviewed layout, and
verifies it before publication. Only this private skeleton receives native
subordinate mounts or ambient placeholder removals. The private manifest is
atomically published inside the same tmpfs; the native caller consumes that
opened file, never a stale shared `bindings` file. Preparation must refuse a
missing, foreign or non-tmpfs invocation root rather than create a disk-backed
fallback. Direct preparation fixtures must explicitly model this new precondition.

SELinux labeling is part of creation, not inferred from the shared runtime's
label. Native mount setup uses fixed `fscontext=system_u:object_r:tmpfs_t:s0`
and `rootcontext=system_u:object_r:onpc_kiosk_runtime_t:s0`, verifies successful
installation of those options and reads back the root's raw inode label before
starting the helper. Filesystem and root-inode labels are separate under the
[public mount contract](https://github.com/util-linux/util-linux/blob/master/sys-utils/mount.8.adoc).
After creation, preparation and native consumption verify the skeleton, links
and manifest have the expected runtime inode labels, including explicit
per-inode labeling where creation transitions require it. Bind mounts retain
their source labels, including the independently copied native roles and vendor
privilege helper. Use per-inode labels; do not apply a filesystem-wide context
override that hides bound executable labels. Do not add `noexec` or `nosuid`
semantics that change the existing native/helper routes. AppArmor still sees the
same final `/usr` paths. The policy generator's comment describing a host-backed
skeleton must be reconciled with the tmpfs backing; existing bootstrap tmpfs
filesystem permissions must be checked for the actual remount/unmount operations.
Any necessary permission belongs only to the existing trusted pre-boundary
callers or finite bootstrap roles, never a new kiosk payload mount capability.
Labeling or permission failure denies entry. Host doubles cannot qualify these
kernel operations; affected Ubuntu/Fedora entry and helper/bootstrap observations
remain required under 003/004 and final-input allocation at 011a.

**Closed publication protocol.** Replace the unversioned source/target list with
a versioned, bounded record stream. The header declares protocol version, backend,
caller role and the unchanged 64-hex generation digest. The role must match the
native service-derived role. Native verifies the selected shared-generation
directory and its marker against the declared digest; it does not already know
that digest. Backend and configured inventory are authoritative outputs of
successful attested preparation, not independently discovered native inputs.
Unknown versions, backend/role values or missing fields refuse.
The preparation producer derives trust roles from attested configuration and the
measured native/preserved inventories, never from a filename, optional assertion,
permission failure or a caller-supplied ambient flag. The stream carries:

- Protected-root records: the producer's configured/measured required
  destinations, native-copy source mapping, reserved roots and lexical alias
  roots, with their closed roles. Native uses these as the authoritative roots
  for independent proof-chain and binding-coverage checks. Producer checks against
  the actual configuration/inventory must catch an omitted configured root;
  parsing the same stream cannot independently rediscover such an omission.
- Skeleton records: relative target, closed node kind (`tree`, `file`, `link`,
  `directory`, `empty-directory`) and exact link text where applicable.
- Required proof records: original required native/privileged destinations,
  reserved roots, covered ancestors and lexical aliases with every intermediate
  symlink target/ancestor, expected node type and link text. These remain required
  even when they have no bind record. Native descriptor-based validation of these
  proofs is mandatory; copied executable sources are additionally checked at their
  shared-generation locations. 002ab supplies this protocol and native checking;
  002a still owns its independently reproduced complete classification/alias
  closure and missing-destination regressions. Neither task receives the other's
  acceptance credit.
- Bind records: explicit `required` or `ambient`, expected `file` or `directory`,
  source, relative target and preserved identity or an explicit absent-assertion
  marker. Required inventories, generation marker, reserved/covered roots and
  alias dependencies cannot receive `ambient`. Privileged helpers always require
  their full existing eight-field identity; an ambient assertion is invalid.
- One terminal attach record: the invocation tree onto exactly `/usr`. It is
  always required and must be last. No later record is accepted.

The producer rejects contradictory or duplicate paths, incomplete required
coverage and required/ambient overlap before publication. The native parser
rejects contradictory/duplicate records, missing closure or binding coverage for
declared protected roots and required/ambient overlap independently, and validates
all structural records before source fallback or attachment. Bind sources must
be canonical absolute paths below `/usr/` or the selected shared generation.
Targets must be canonical relative paths anchored to the recorded invocation
root: no empty/dot/dot-dot components,
embedded NUL, extra fields, truncated lines or path-prefix approximations.
Targets and their parents are opened component by component without following
links; bind targets cannot be link nodes. Skeleton symlinks are copied as link
text, never followed to construct or remove a target. Required host alias proofs
explicitly follow only their validated, bounded chain, including targets outside
`/usr` where the existing inventory allows them. Cycles or incomplete proofs deny.
Unrepresentable names remain omitted or refused by scope under 002a's publication
rules, never coerced to another name. No old-format fallback grants an exception.

**Source decision and descriptor lifetime.** First validate the complete protocol,
required proofs and every target's independent ownership, type and ancestry.
Only an explicitly ambient bind's **final source node** can receive the following
fallback. A source ancestor/proof failure is strict, including one encountered
while opening an ambient source. Separate source and target errors; a failed
target lookup/stat/unlink is never evidence of an unsafe source.

| Final source observation after publication | Ambient file result | Ambient directory result | Required result |
| --- | --- | --- | --- |
| Missing (`ENOENT` at the final component), including removal after opening | Remove private file placeholder | Keep private directory empty | Refuse |
| Final-source open/stat reports `EACCES`, `EPERM`, `EIO` or `ESTALE` after trusted ancestry was established | Remove private file placeholder | Keep private directory empty | Refuse |
| Non-root owner, group/world write bits, wrong expected type (including a substituted link/special node) | Remove private file placeholder | Keep private directory empty | Refuse |
| Path no longer names the checked inode, or checked metadata becomes unsafe before/after bind | Remove private file placeholder after owned detach if needed | Keep private directory empty after owned detach if needed | Refuse |
| Resource exhaustion, invalid descriptor, malformed path/proof, any other source error, target failure or any mount failure | Refuse | Refuse | Refuse |

Use no-follow `O_PATH` source descriptors after checked ancestry; do not open a
FIFO/device for I/O. Hold source, target and needed parent descriptors until
mount and rechecks finish. Bind through those descriptors. Recheck source type,
UID and write restrictions immediately before and after bind, check that the
validated pathname still identifies that descriptor's device/inode and is not
unlinked, and revalidate required ancestry/proofs before final attachment.
For preserved helpers retain **every** identity field before and after mounting.
A disappearance/reappearance or substitution never causes a reopen-and-retry
against a different inode in this invocation. If an ambient source fails after
a successful subordinate mount, detach that exact owned mount successfully
before omission/masking; detach failure refuses. A failed mount always refuses,
even if a later source check would have permitted omission.

Remove a rejected file with descriptor-relative, no-follow unlink only after
matching its private placeholder identity and confirming no mount remains there.
A rejected directory stays the original empty mode-0755 private directory;
never change its kind to match a replacement source. Do not bind any rejected
source or copy its data. Once a record is omitted/masked, do not reconsider it
if its host name reappears. Safe accepted directories keep the existing shallow
bind semantics: this phase does not recursively measure their contents or freeze
future host writes. Descriptor pins and finite rechecks do not establish the
between-admission immutable-material guarantees reserved to 005a–007.

**Attachment, bounds and cleanup.** Recursively clone the completed invocation
tree onto `/usr`, make that clone recursively read-only, then detach only the
recorded subordinate staging mounts and finally the invocation's tmpfs staging
root. Close all setup/source/target/manifest descriptors before MAC. The `/usr`
clone retains its own mount references and private dentries; detaching the staging
root removes its writable alias without deleting those dentries. The kernel
releases that filesystem when its last namespace/mount reference disappears.
Never recursively delete the skeleton after attachment. No shared generation,
record, digest, marker, mode, link or placeholder is modified by realization.

Keep four completed shared generations, 32,768 layout nodes, 512 MiB copied input
and the 60-second preparation-child deadline, with its owned kill/reap behavior.
Bound private tmpfs storage at 512 MiB and 32,776 inodes, and the manifest at
64 MiB, 32,768 protected-root rows, 32,768 skeleton rows, 32,768 proof rows and
32,768 bind rows plus header and terminal record. Paths/link text are bounded by
`PATH_MAX`; assertions use
the existing finite numeric schema with overflow rejection. Bound alias walks
and reject exhaustion rather than truncate proof. Exceeding any bound, running
out of storage or failing an allocation denies; no larger disk fallback exists.
These are ceilings, not a scaling increase or a promise every ceiling-sized
combination fits. Preparation, parser and fixture limits must agree.

Keep mount identities and reverse-order cleanup state in the native invocation.
On preparation timeout/failure, partial publication, bind failure or later
pre-MAC failure, wait for owned children, close descriptors and detach only its
recorded mounts (including its `/usr` clone if attached), then its tmpfs root.
A cleanup mismatch/failure remains denial and must be reported, never adopted
or recursively erased. Process/namespace exit releases surviving private mount
references; do not return successful admission with unfinished detach. A caller
crash leaves no persistent private payload to sweep. Preserve an unexpected
shared mountpoint identity or nonempty directory and refuse it. Diagnostics use
closed categories without paths and cannot change admission if logging fails;
002b retains detailed native cause production.

**Finite host acceptance allocation (002ab).** The following selector families
are registered in `tests/unit/test_kiosk_confinement.py`, including the
`_source_errors` and `_preparation` controls. They reuse `native_mount_binding`
and `preserved_password_preparation`; `tools/regression_unit.py` records their
private storage, descriptor, child-process and simulated kernel resource ownership.

| Selector | Required independent assertions |
| --- | --- |
| `test_post_layout_source_drift` | Both caller roles; ambient and required files/directories independently vanish, become non-root-owned, group/world-writable or wrong-type after publication. Observe native consumption; rejected files absent, directories empty, rejected source never mounted; required equivalent refuses. |
| `test_post_layout_descriptor_drift` | Disappearance/reappearance, rename/type substitution and owner/mode change between checked open, pre-bind and post-bind rechecks; no reopen retry, no rejected mount left behind; required and preserved controls refuse. Use real private file changes at descriptor boundaries in addition to metadata doubles. |
| `test_post_layout_protocol_and_targets` | Missing/unknown caller or source role, old/malformed/duplicate/contradictory/truncated/over-limit records, omitted required proofs, alias/reserved-root drift and unsafe target/ancestor/link all refuse, even paired with a missing ambient source. Source-only fallback must be distinguished from target/stat failures. |
| `test_post_layout_published_roles_and_reuse` | Actual manager and gate `prepare()` outputs reach native parser. Snapshot shared records/tree/digest/copies/marker before native ambient omission; they remain identical afterward. Fresh preparation with restored identical inputs reuses them, and gate passes the same digest to `manager_generation()`; a genuinely different digest still refuses. Changed later layout is not falsely declared compatible. |
| `test_post_layout_owned_cleanup_and_bounds` | Private namespace/tmpfs and label setup, atomic publication, helper failure/timeout, partial bind, attach/read-only/detach failures, storage/row limits and post-attach failure; only owned mounts/descriptors/children are released, foreign state survives, no shared-tree mutation or writable staging alias survives success. Logging failure leaves admission unchanged. |

Retain the existing detach-order selector's 11 independent controls, the eight
preserved-identity field controls and real post-measurement file-change controls.
Host namespace/mount/label doubles are engineering evidence only. The
[002ab receipt](../Kiosk-Prompt.md#post-layout-ambient-binding-implementation--002ab)
retains exact selectors, failing-then-passing evidence, fixture/source identities,
explicit child timeouts, runner cleanup, resource review and final package builds.
No installed acceptance is earned here or at 002ab; 003/004/007 and 011a retain
their full affected-target obligations. Classification, alias-closure,
completeness, publication and metadata-race host controls belong to 002a.

## Roles, services and dialogs

The [generated role policy](../../tools/kiosk_confinement_policy.py) separates
the session, manager, request app, notification, audio, Wellbeing, authentication,
WebKit, scanner and image-decoder routes. Generic interpreters are reachable only
through [native fixed launchers](../../tools/kiosk_session.c), which reject
caller arguments, clear startup injection variables and select installed scripts.
The manager cannot use a user unit or privileged command prefix to run a shell,
generic Python/GJS, GNOME Shell or an arbitrary session. Requests to clear MAC
confinement remain subject to the existing kernel boundary even when a service
asks systemd to ignore profile-setting errors.

The manager alone receives the private root-owned unit search path. Ubuntu's
finite Snap activation masks and private D-Bus definitions prevent direct vendor
activation around those masks. Shared Wellbeing/audio launchers preserve ordinary
users' environments. Kiosk WirePlumber uses system configuration/data roots and
empty Lua default search paths; its trusted custom searcher remains available.
Lua is not the security boundary: native service/module APIs still encounter
kernel executable-mapping and role-transition restrictions. Reviewed native
packages, mapped libraries and shipped scripts define the qualified plugin scope.

Fedora's compositor/service, request-app and notification-provider roles can map
GPU devices labelled `dri_device_t`, as required by their renderers. The GTK
notification provider paints banners in its own role and needs the same mapping
permission as the request app. This character-device mapping permission belongs
only to those three roles; it adds no executable transition or general device
mapping permission. Policy updates use the existing reboot activation boundary
so admission sees the current attested policy and generation.

The [bubblewrap launcher](../../tools/kiosk_bwrap.c) first supplies a read-only
`/usr/bin` bind, then invokes independently pinned distribution bubblewrap.
Only finite native WebKit/Glycin bootstrap roles can create the required private
namespaces, mounts and loopback interface. Payload roles receive none of that
administration authority. WebKit and scanner AppArmor profiles stack with existing
restrictions; Fedora binds retain source inode types without generic `bin_t`
execution. Glycin's native decoder directory is pinned and decoders cannot
execute another program. The optional GStreamer Python plugin cannot acquire
executable mappings in the confined view.

Polkit owns administrator authentication; product front ends never receive the
password. Its vendor native helper is independently pinned read-only with its
original inode and privilege metadata: mode 04755 on Fedora and 0755 on Ubuntu,
without file capabilities. Fedora's vendor helper role requires its enforcing
domain, exact mixed UID tuple, private generation/namespace and live confined
agent parent. Ubuntu's socket-activated root helper runs outside the kiosk
account. These are finite native authentication routes, not generic execution
exceptions. [Broker](Broker.md#broker-interface-and-roles) owns method-level
authorization and approval transactions.

About, Preferences, nested editors, error reporting and privacy disclosure stay
inside the request application. Kiosk mode suppresses external handlers, file
choosers, management controls and arbitrary program actions. In-app reporting
and editing remain usable. [Front ends](Frontends.md) and
[Logging and feedback](Logging-and-Feedback.md) own those feature contracts.

## Installation, updates and removal

Configuration excludes native preparation while publishing policy, PAM and
attestation changes. The boot loader takes the exclusive lifecycle/admission
barrier and verifies the saved digest pair before loading policy. An interrupted
unpack cannot become a trusted generation merely by rebooting. A loader racing
an active admission refuses without changing policy or attestation.

Native confinement, PAM, fixed-launcher and routing updates require reboot:
graphical logout can retain an old manager and private executable generation.
Before the required reboot, public station entry offers the restart explanation
with policy controls unavailable. Missing, stale or non-enforcing policy denies
native admission independently of display-manager ordering.

[Package removal](Package-Removal.md#pam-and-kiosk-ownership) owns the complete
cleanup and recovery contract. Exclusive admission/routing/preparation locks
exclude active admissions; live kiosk threads, pending MAC state and stale native
mappings refuse removal without signalling them. Before policy unload, durable
distribution-PAM kiosk denials are published so payload erasure cannot expose
the account. Exact original PAM is restored only after verified owned-account
deletion. Abort restores enforcement before releasing gates; interruption or
foreign state preserves barriers and recovery records. Account/home deletion
checks identity, ownership, links and mounts and uses public AccountsService
uncache. Ordinary remove retains preferences/logs; purge deletes only owned data
after integration and account restoration succeed.

## Offense and defense scenarios

Each proof link identifies a maintained VM case or its exact assertion helper.
System cases exercise native boundaries with positive controls and independent
enforcing denials; public E2E cases establish the stated visible result. A case
definition is a reproducible proof obligation, not evidence that it passed on
every version or distribution. The qualification scope follows the table.

| Scenario ID | Offense Scenario | Confinement Defense |
| --- | --- | --- |
| 1 | At sign-in, select the request-station account but choose a normal desktop instead. | Dedicated-session routing is checked and repaired with denial of the current attempt; the final PAM boundary separately constrains the executable GDM actually starts. Proof: [system login admission](../../tests/integration/system_kiosk_admission.py#L363) and [system final-exec matrix](../../tests/integration/system_kiosk_confinement.py#L1984). |
| 2 | Choose an older X11 session for the request station. | Saved transport must be Wayland, and session opening checks the PAM transport. The installed wrong-transport test proves account-stage denial, repair and successful fresh retry; it does not itself open an X11 session. Proof: [system admission matrix](../../tests/integration/system_kiosk_admission.py#L363). |
| 3 | Switch to a text console and try signing in as the request-station account. | The installed `login` PAM account gate denies the kiosk identity, backed by its nologin shell. An ordinary-account positive control prevents a broken PAM service counting as protection. Proof: [system admission matrix](../../tests/integration/system_kiosk_admission.py#L348). |
| 4 | Connect remotely by SSH and try using the request-station account. | The installed `sshd` account gate denies the kiosk; effective SSH configuration must use that PAM service. Proof: [system SSH configuration and admission assertions](../../tests/integration/system_kiosk_admission.py#L363). This checks the installed gate, not a complete network SSH login. |
| 5 | Press Super to show the desktop overview, Super+A to show applications, or Ctrl+Alt+T to open a terminal. | The dedicated compositor exposes the request station without those desktop launch routes. Public checks require the form to remain usable and independently observe absence of forbidden windows after each input. Proof: [E2E cases 50–52](../TestAutomation/E2E-Scenario-Recipes.md#e2e-016), [case implementation](../../tests/e2e/restricted_station.py). |
| 6 | <ul><li>Submit a request with a wrong administrator password.</li><li>After rejection, try the desktop and terminal shortcuts again.</li></ul> | Authentication denial grants no access and preserves the confined request form and choices. Restrictions are repeated after rejection. Proof: [E2E case 51](../../tests/e2e/restricted_station.py#L60). |
| 7 | <ul><li>Submit a request and cancel the administrator password prompt.</li><li>Try the desktop and terminal shortcuts again.</li></ul> | Password-free cancellation leaves the same confined form; the second restriction cycle still rejects all three routes. Proof: [E2E case 52](../../tests/e2e/restricted_station.py#L92). |
| 8 | Cancel or close the request window to uncover a desktop behind it. | Normal request exit ends the station surface and returns to usable sign-in, without exposing a station desktop. Proof: [E2E Cancel case 47](../../tests/e2e/kiosk_cancel.py), [surface-close case 48](../../tests/e2e/kiosk_escape.py). Case 48 uses the guarded close operation, not proof of every native close gesture. |
| 9 | After a parent approves more time, stay in the station and use it as an unrestricted account. | Approval updates the selected child's authorization and the restricted-station success route exits to sign-in. It does not remove kiosk MAC policy or grant administration. Proof: [E2E case 50](../../tests/e2e/restricted_station.py#L33), [broker authorization](Broker.md#authorization-and-grant-transactions). |
| 10 | Open About or Help and look for a website, file browser or management window to launch. | Kiosk About keeps information in-app and excludes external-handler, chooser and management actions; closing it preserves the unfinished request. Proof: [E2E case 192](../../tests/e2e/kiosk_about.py). |
| 11 | <ul><li>Open Preferences.</li><li>Visit Language, Reminders and Preset Times.</li><li>Open the Add/Edit dialogs and look for a way to launch another app or browse files.</li></ul> | The exposed controls are checked for unexpected surfaces, external links and forbidden actions. Cancelling drafts returns to the unchanged request, followed by a strict confined-process census. Proof: [installed Preferences qualifier](../../tests/integration/check_e2e_kiosk_preferences_confinement.py), [journey assertions](../../tests/e2e/kiosk_preferences_confinement.py). |
| 12 | Open an error report, edit its text, or open the privacy disclosure to reach files or another app. | Reporting remains in-app; kiosk chooser/external-handler actions are suppressed. The qualifier proves usable editing, privacy navigation and a waiting-session census without submitting a report. Proof: [installed feedback qualifier](../../tests/integration/check_e2e_kiosk_feedback_confinement.py), [journey assertions](../../tests/e2e/kiosk_feedback_confinement.py). |
| 13 | Ask a background service to open a shell or run a Python/GJS command, desktop shell or alternate session. | The user manager and service executors retain role-specific MAC restrictions. Each prohibited command requires an executor failure and fresh matching kernel denial after successful native execution. Proof: [system execution matrix](../../tests/integration/system_kiosk_confinement.py#L1984). |
| 14 | Copy an allowed program into a writable folder, rename it, or make a shortcut to an interpreter and run it. | Execution authority depends on trusted private paths/inodes and role transitions, not matching file contents or a friendly name. A copied executable and interpreter symlink are explicitly denied. Proof: [system writable-input assertions](../../tests/integration/system_kiosk_confinement.py#L1414). |
| 15 | Run a program through its library loader, an already-open file, or a program held only in memory. | The final GDM execution gate denies explicit loader invocation, file-descriptor execution and memfd execution with native permission errors. An allowed actual final exec precedes those negatives. Proof: [system final-exec matrix](../../tests/integration/system_kiosk_confinement.py#L1984). |
| 16 | Create a background startup job and mark its command as privileged to bypass restrictions. | A user unit's `ExecStart=+` does not remove the manager's MAC boundary or turn the kiosk into root. The test verifies the exact writable unit and effective prefix before requiring the shell execution denial. Proof: [system user-unit assertions](../../tests/integration/system_kiosk_confinement.py#L1414). |
| 17 | Ask the background service manager to run a job without its security profile, including “ignore errors.” | Unconfined profile/context selection is denied; ignoring that setup error still leaves forbidden shell execution blocked by the kernel. Proof: [system service-API assertions](../../tests/integration/system_kiosk_platform.py#L340). |
| 18 | Put custom startup settings or scripts in a writable folder so notifications, audio or Wellbeing will run them. | Fixed launchers reject extra arguments and clear startup injection. Audio uses system roots and empty default Lua paths. Proof: [system hostile-startup and Lua assertions](../../tests/integration/system_kiosk_platform.py#L186), [fixed launcher implementation](../../tools/kiosk_session.c). Qualification covers the reviewed native inputs, not every optional plugin. |
| 19 | Ask the audio service to load a custom plugin from a writable folder. | Kernel executable-mapping policy rejects the user-owned ELF even when requested through the real native metadata API. A genuine trusted-library load is observed first. Proof: [system native audio API assertions](../../tests/integration/system_kiosk_platform.py#L285). |
| 20 | Use the report editor's web or media helpers to substitute a program or load writable code. | Separate bootstrap/payload roles, pinned native proxy/scanner paths and read-only executable binds prevent tested substitutions. Six bind/data/file attacks require an independent native positive and enforcing denial. Proof: [system bubblewrap substitution assertions](../../tests/integration/system_kiosk_confinement.py#L1245), [installed feedback qualifier](../../tests/e2e/kiosk_feedback_confinement.py). |
| 21 | Use an image decoder or a sandbox helper as a way to launch another program or change the system's mounts. | Glycin has a finite pinned decoder route with no onward exec; only native bootstrap roles have bounded private-namespace setup authority. Proof: [role policy](../../tools/kiosk_confinement_policy.py) and [bubblewrap assertions](../../tests/integration/system_kiosk_confinement.py#L1245). These checks do not establish immunity to unknown decoder vulnerabilities. |
| 22 | Use the administrator password helper as a general privileged program launcher. | Only the pinned vendor authentication helper and its finite transitions are permitted; native binding checks privilege metadata before and after mounting. Fedora's helper census requires exact credentials, label, parent, namespace and generation. Proof: [system helper identity assertions](../../tests/integration/system_kiosk_confinement.py#L197), [public authentication in cases 50–52](../../tests/e2e/restricted_station.py). |
| 23 | Change the request station's default desktop or ask it to manage parental-control settings. | Root-owned routing and Polkit protect the account metadata; the kiosk has no management UI route. Broker methods independently check caller roles, targets and approval. Proof: [system routing denial/recovery](../../tests/integration/system_kiosk_admission.py#L363), [system broker role matrix](../../tests/system/test_authorization.py#L114), [E2E restrictions](../TestAutomation/E2E-Scenario-Recipes.md#e2e-016). Broker authorization is a separate boundary from execution confinement. |
| 24 | Wait for a software update, then reuse an old background session to run newly replaced programs. | Private directory dentries pin executable/library/plugin inputs across package rename/replacement and manager reexec. The manager's every-thread boundary is rechecked and a fresh shell denial is required while replacement files are present. Proof: [system replacement/reexec assertions](../../tests/integration/system_kiosk_confinement.py#L1510). |
| 25 | Keep an old station manager alive after its required configuration changes, then sign in again. | GDM admission requires an exact matching private generation and enforcing manager label. The [configuration-mutation check](../../tests/integration/system_kiosk_confinement.py#L2015) proves refusal without restarting the manager, but reaches payload attestation before generation comparison. The separate [native-update generation-refusal implementation](../../tests/integration/system_native_update.py#L743) requires the specific stale-generation reason; reuse requires matching candidate evidence. Final-candidate generation qualification remains with [the kiosk entry plan](../Kiosk-Prompt.md). |
| 26 | Try entering while security policy is missing, stale, disabled or permissive. | Preparation independently verifies loaded enforcement and attested bytes; failed prerequisites deny native manager/GDM admission. Restoring the exact owned policy permits recovery. Proof: [system policy-loss assertions](../../tests/integration/system_kiosk_confinement.py#L1710). This tests fail-closed admission, not administrator removal of policy from an already-running session. |
| 27 | Try entering during an interrupted installation or before the first required reboot. | Account expiry remains durable until configuration completes; the pre-reboot public station has no usable policy controls. Proof: [system first-configuration history](../../tests/system/test_install_smoke.py#L36), [installed/rebooted GDM history](../../tests/system/test_install_smoke.py#L43). |
| 28 | Reboot after only part of an update was unpacked, hoping the new files will be trusted automatically. | Configuration and policy must match the successful-load digest pair. Native preparation and boot loading both refuse drift without adopting it. Proof: [system attestation-drift assertions](../../tests/integration/system_kiosk_confinement.py#L1659). |
| 29 | Try entering while another login, policy reload or package change is in progress. | Identity-checked locks serialize the admission and lifecycle boundaries. A loader cannot publish an attestation across an active admission; contention refuses with state preserved. Proof: [system held-admission loader assertions](../../tests/integration/system_kiosk_confinement.py#L1948). |
| 30 | Leave background processes running or wait for login cleanup to execute something outside confinement. | The manager, executor and surviving PAM helper retain enforcing current roles through credentials, close and teardown, including after parent exit. The strict census rejects unknown labels and unconfined threads. Proof: [system PAM lifecycle assertions](../../tests/integration/system_kiosk_confinement.py#L1005), [waiting-session census](../../tests/integration/system_kiosk_confinement.py#L93). |
| 31 | Rely on a system login hook to start a keyring, run a namespace setup script or execute cleanup code for the station. | PAM control-flow audit and kiosk-only callback guards exclude those vendor routes on both open and close; ordinary accounts retain them. Proof: [system namespace callback case](../../tests/system/test_enforcement.py#L28), [shared integration case](../../tests/system/test_enforcement.py#L33). |
| 32 | Use an optional desktop background service to open an app even though the normal launcher is unavailable. | Kiosk-only unit masks and inert private D-Bus activation definitions block the finite Snap routes; required service roles remain confined. Proof: [private activation policy](../../tools/kiosk_confinement_policy.py), [system shared-scope assertions](../../tests/integration/system_kiosk_scope.py). Ordinary-account scope checks are not a proof against every possible future activation service. |
| 33 | Keep using the station while an administrator removes the product, hoping restrictions disappear first. | Active admissions/processes refuse removal. Durable PAM denials precede policy unload and survive payload erasure; account deletion precedes original-PAM restoration. Abort/retry retains enforcement or admission barriers. Proof: [installed removal and recovery cases](../../tests/system/test_removal.py), [removal contract](Package-Removal.md#pam-and-kiosk-ownership). |
| 34 | Prepare misleading shortcuts, changed account records or substituted files and wait for installation or cleanup to trust them. | Preparation checks trusted alias ancestry; lifecycle operations refuse foreign identity, ownership, links, mounts and records rather than adopting or deleting them. Proof: [system untrusted-alias refusal](../../tests/integration/system_kiosk_confinement.py#L1615), [installed removal ownership cases](../../tests/system/test_removal.py), [account ownership contract](Package-Removal.md#pam-and-kiosk-ownership). |

## Verification scope and evidence limits

Persistent system case identities are registered in
[system case IDs](../../tests/integration/system_case_ids.py):
4 covers first-configuration interruption/retry, 5 account classification and
real GDM activation across reboot, 267 native execution confinement, 268 installed
login admission and 269 platform integrations. The
[installed-suite guide](../../tests/integration/README.md#running-the-current-installed-suite)
defines their exact scope, positive controls and failure witnesses. Public cases
50, 51, 52 and 192 are independently registered in the
[E2E inventory](../../tests/e2e/scenarios.json). Preferences and feedback
confinement qualifiers are engineering checks, not complete customer cases.

The recorded qualification on 2026-10-16 passed the affected native, admission,
platform, shared-PAM and real-session checks on both targets. The final reviewed
package source was revision `512e1fd0fbdfc9a9a69916f635054bbf0ea9d330`, with DEB
SHA-256 `9abe9da9c5df0aeae86e07af75a0ac2a5bdc7eeaf362a14e1ad15be54ee2eadb`
and RPM SHA-256
`ba44158f0c9f690313aef6fecba23d404bafec4469df76fbb65e6ef4f6885aeb`.
Its repeated system 6/267 and system 4 histories passed on both targets; public
cases 50/51/52/192 also passed independently on both. These are historical
candidate-specific results, not new VM execution performed for this design edit.

The original Fedora, Ubuntu recovery and review exports are inherited into
these verified cumulative bundles under `output/test-runs/host/exports/`:

- `onpc-evidence-bundle-opzdhw6_/evidence.zip`: 58,595 files, SHA-256
  `3d031877f134e0be39833e9baf2d297a0d66aaa1bd76ec26e5da23bc248b1107`.
- `onpc-evidence-bundle-g99gn1a1/evidence.zip`: 44,882 files, SHA-256
  `b91777276815aec5f21c04e37a1c6e8c55ef9624dd954f0bcb98984daec3fb22`.

Use the maintained [artifact readers](../../tests/README.md#prompt-free-test-artifact-access).
Original report and allocation paths remain archive inventory keys even after
their originals rotate; existing retention ownership applies.

The 2026-10-17 close-out preserves accepted authorization cases 26–151 and
removal cases 6, 7 and 9–17 on both targets. System cases 4, 5, 18–25 and
267–271, including their prerequisites, passed 73/73 executions per target.
Public E2E cases 47, 48, 50, 51, 52 and 192 and Preferences confinement passed
on both targets. Fedora RPM recovery case 8 passed all eight executions;
the final case 5 history restored its combined-VM recording. Final recording
indices and surviving system reports are preserved in the cumulative bundles.
The raw 73-pass allocations `onpc-system-yb33mofd` and `onpc-system-6covjn1o`
rotated before archival; their accepted passes and archived host reports remain,
but their original result/JUnit/TAP records are unavailable.

Feedback confinement passed independently on Fedora with enforcing SELinux
(report key `20261017T213630Z-7d9de2df`, result allocation
`onpc-graphical-smoke-oc15q7f5`) and Ubuntu with enforcing AppArmor
(report key `20261017T225629Z-47b5880c`, result allocation
`onpc-graphical-smoke-o6cd5k77`). Both proved editor usability, privacy reading,
draft preservation and the strict waiting-session census without submission;
infrastructure, collection and owned cleanup passed. These engineering
qualifiers correctly record the customer product domain as `not-run` and
publish no case recording. Disabled sound/scanner observation is excluded from
this qualifier by the developer's explicit scope decision.

This campaign spans multiple candidates, not one immutable revision. The
73-pass system inputs used package source `75f608f67dc164adc835663f4d35b9e94fd79d61`;
the public E2E inputs used `0690f1de71cc41bfad97f494b19087fbb3ce0f85`.
Fedora's feedback pass used source `4e08dcdbaa5ee574d349a4a00c5cd81a5ad4cd79`
and RPM SHA-256 `ae32aa2efe5b716840b8025f7edd7d26b5326d22a1118b44749e24331466da6d`.
Ubuntu's final feedback pass used source `f0e4dc777f005c611f9dce483f2334edc4592440`
and DEB SHA-256 `80fe01b91186386ce7300dae84a1816a753c3bbd6eac4d0bf20b1740b6553814`.
Its exact result, worker records, host report and input manifest are preserved
in `onpc-evidence-bundle-g99gn1a1`; earlier failures remain archived alongside
the passing results. The earlier intermittent Ubuntu station-entry timeout
has no established root cause; this successful retry does not claim a fix.

An explicitly accepted historical Ubuntu retention loss covers four matrix
allocations (`onpc-system-o9ryhtxo`, `onpc-system-8efeqxdi`,
`onpc-system-4rp3cyvz`, `onpc-system-ngv1c40y`), 27 removal/rollback/publication
executions in `onpc-system-942mnslh`, and the two first-configuration phases in
`onpc-system-8xmuzogd`. They passed, but their raw proof is unavailable; older
package results do not replace it. The developer accepted those passes despite
that loss. The same missing files alone do not reopen qualification; changed
inputs or a newly demonstrated defect require normal affected validation.

Source review and passing host checks cannot replace installed enforcement or
public acceptance. Changed distro code, plugin inputs, PAM control flow, policy,
native launchers or executable inventory need renewed affected qualification.
Neither this catalogue nor historical passes establish exploit resistance beyond
the declared trusted base and tested attack surfaces.
