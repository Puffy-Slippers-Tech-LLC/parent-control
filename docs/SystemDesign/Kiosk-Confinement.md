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
executable view, clears PAM-granted inheritable and ambient capabilities and
installs mandatory access control. The native clear verifies unchanged effective
and permitted capabilities for the trusted PAM executor's remaining work; it
does not change the bounding set. No subprocess runs after the final MAC operation.

Ubuntu immediately changes and verifies the caller's enforcing AppArmor profile.
Every non-sandbox profile, including the password helper's child profile,
explicitly denies user-namespace creation. Under AppArmor's compatibility ABI,
an absent allow alone does not establish mediation of that feature. Only the
two native bubblewrap roles retain their explicit user-namespace grants.
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
closed categories without paths and cannot change admission if logging fails.
Detailed native cause production follows the
[admission diagnostic contract](Logging-and-Feedback.md#kiosk-admission-diagnostics);
its host acceptance is recorded at [002b](../Kiosk-Prompt.md#native-binding-failure-causes--002b).

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

### Planned retained material and immutable pins

This is the **005a material design with 005's admission proof review**. The native
fresh and retained coordinators implement the material/source split described
here; the [entry queue](../Kiosk-Prompt-Queue.md) owns their finite host evidence,
remaining combined matrix and installed qualification. The historical heading
is retained for incoming links. Neither this design nor component checks supply
installed acceptance.

[006a primitives and host evidence](../Kiosk-Prompt.md#owned-immutable-view-primitives--006a)
now exist in `RuntimeCopyPublication` / `verify_runtime_copies()` and native
`kiosk_pin_acquire()` / `kiosk_pin_attach()` / `kiosk_pin_finish()` /
`kiosk_pin_publish()` / `kiosk_pin_release()`. Callers must independently select
the finite runtime specs and pin receipt provenance; supporting disk copies or
ready records alone grant no admission authority. Preparation selection has
[006b host evidence](../Kiosk-Prompt.md#retained-material-selection--006b); full
fresh and retained composition is allocated to 006c/006d, cumulative host
qualification to 006 and installed qualification to 007a/007.

Preparation uses `required_material()` /
`verify_required_material()` / `select_retained_material()` operations.
The generated attested config binds the exact `runtime_inputs` membership.
Material measurement includes the current attested pair, native substitutions,
vendor privilege requirements, finite runtime inputs and complete required trust
closure; transaction-local inode assertions stay separate from its digest.
Selection accepts only the original layout and a native-owned projection of
source descriptors plus inode provenance, returning stable source indices and
fresh eight-field assertions. It opens no ambient host source, and eligible
ambient failures narrow only the fresh invocation layout, including at its last
source observation. It never acquires a clone, adopts a ready record, publishes
or attaches a view. The native coordinators own receipt parsing, manager proof,
one-clone acquisition, final binding and MAC. Production PAM uses those paired
transactions; the older `prepare()` route is retained for compatibility tests
and supplies no fallback.

**Two identities.** Define a versioned, canonically encoded material record
`M` containing the exact attested config/policy digest pair, backend, configured
native roles and source/destination substitutions, selected optional alternatives,
native/library content hashes, preserved-helper content and privilege metadata,
the required lexical alias/type/link closure, and the finite consumed runtime
inputs below. Required ancestry contributes its trust predicates and exact link
text; directory inode numbers, timestamps, link counts and ambient child lists
do not define material. An ambient addition changes its parent's metadata without
changing a required dependency. Retain current no-follow/trusted-ancestor and
final-proof rechecks independently of that identity calculation.

A separate immutable realization record `V` binds `M` to the original finite
layout and the **actual realized** source mapping: copied-file indices, source
inode assertions, masks/omissions, links, labels and mount coverage. Native
realization must record a late ambient omission in `V`; preparation's intended
layout alone cannot describe the resulting view. Use domain-separated,
length-delimited canonical records for both hashes; never ambiguous byte
concatenation. Local mount IDs are runtime witnesses, not portable hash inputs.
The manager and gate must agree on both the selected `M` and source `V`.
Each later gate also has a bounded invocation receipt `I`, bound to that pair,
which records its own actual source decisions, omissions/masks and attachment.
If a retained ambient inode becomes unsafe, `I` may describe a stricter view
than source `V`; native must verify that exact derivation and its complete
required coverage. It must not claim byte-for-byte realization equality while
changing coverage, alter source `V`, or import a source absent from `V`.
`I` lives only with that invocation's private view and does not allocate another
completed generation. Equal `M` permits selecting an existing safe realization;
it does not authorize mixing its layout with sources from another realization.
Never overwrite a
published realization to fit a new ambient scan.

**Finite required set and runtime consumers.** Preserve every existing native,
library, reserved-directory, lexical alias and privileged-helper requirement in
`inventory()`, `layout_requirements()` and `preserved_inventory()`. Optional
native routes selected in a realization remain material; installing/removing one
can change `M`. The producer derives this set from attested configuration, never
from a permission failure or an ambient flag. A required ancestor cannot become
ambient because a new layout lacks it.

The changed route retains scripts and service data across admissions, so the
following demonstrably consumed, finite inputs also need explicit runtime
records. These are allowlists for implementation, not permission to inventory
all installed packages:

| Actual consumer | Required material in the retained route | Limit |
| --- | --- | --- |
| Fixed app and notification-client arguments in [kiosk_session.c](../../tools/kiosk_session.c), and the [Python entry](../../kiosk/oh-no-parent-control) | `/usr/bin/oh-no-parent-control`, `/usr/bin/gnome-service-client`, and the shipped files in `/usr/lib/oh-no-parent-control/kiosk` and `/usr/lib/oh-no-parent-control/common`, including their import/asset closure | Enumerate the installed production payload's finite membership; hash relative names, kinds, link text and file bytes. Do not discover a new dependency by recursively following arbitrary host links or importing code during preparation. |
| Fixed wellbeing launcher and its direct import/settings lookup in [wellbeingService.js](../../child/wellbeingService.js) | Under `/usr/share/gnome-shell/extensions/oh-no-parent-control@tech.puffyslippers.com`: `wellbeingService.js`, `wellbeingLogic.mjs`, `schemas/gschemas.compiled`, and their trusted ancestry | The extension-local compiled schema is consumed. The rest of the extension and the global compiled schema database are not newly measured by this route. |
| Manager `SYSTEMD_UNIT_PATH` and generated Ubuntu D-Bus prefix in [policy generation](../../tools/kiosk_confinement_policy.py) | Exact generated membership/bytes/links in confinement `user-units`, and Ubuntu-only `session-data` | Include intentional `/dev/null` mask links as exact text; do not copy their targets. Do not turn all distribution user units or service files into new required inputs. |
| Existing Python/GI/GTK, XDG and WirePlumber searches recorded by the [native audit](../Kiosk-Prompt.md#preparation-and-native-admission-audit--001b) | Preserve existing measured ELF/library inputs and required root/alias trust checks; distinguish an actually selected runtime source from an unrelated sibling | `/etc/xdg` and `/etc/wireplumber` stay outside the `/usr` overlay. `/usr/local/share`, `/usr/share`, typelibs, Python libraries and WirePlumber data keep their existing shallow/runtime compatibility limits; do not hash or copy their entire trees or require optional search roots to exist. |

For newly measured runtime files, make independent root-owned non-hardlinked
copies and verify bytes, safe modes, membership and original role-appropriate
SELinux labels before publication and reuse. Do not label script/data copies as
new native entrypoints. Reject unexpected code-bearing members, unsafe ancestry,
escaping links, special nodes, mutable ownership, metadata/read failures and
bound exhaustion. Known non-code build caches are excluded explicitly by the
production membership rule, not by a general unknown-file exception. The bounded
walk is of named product payload roots only. The new records and copies share
the existing 32,768-entry and 512 MiB budgets; there is no larger allowance.

This does not establish recursive immutability for shallow distribution data
binds. A retained root descriptor preserves an inode, not every nested name or
its contents. Missing genuinely consumed system data remains a readiness/runtime
compatibility failure, not proof of harmless ambient drift. Neither a broad
policy read rule nor an unused XDG search root adds a material prerequisite.
Any further runtime addition needs a concrete changed-route consumer and safety
reason under the master's symptom boundary.

**Transition table.** Apply required checks to current host inputs before
selecting a retained view, then check the selected view's required pins against
`M` and their own source assertions. Host trust and retained trust are separate
observations. The following results assume a live verified manager under the
[admission proof](#planned-retained-view-admission-proof) below.

| Change since initial realization | Material result | Later entry and independent control |
| --- | --- | --- |
| Unchanged required inputs; unrelated empty-directory addition/removal | Same `M`; keep original `V` | Admit using retained pins; original added name remains absent. Preserve the historical before/after stale-manager reproduction below. |
| Ambient file/directory/link added, removed, renamed, or replaced by another kind/inode at the host name | Same `M`; no new host source is selected | Keep the original safe retained entry or its original absence/mask. A replacement's bytes/link target cannot enter through a reopened host name. |
| Ambient mode/owner changes, including trusted to writable/non-root and back | Same `M` | If the retained source itself is unsafe, omit its file/link or mask its directory in the fresh invocation tree. Host replacement does not invalidate a still-safe old pin. Restoring trust does not expose a previously omitted source during that invocation. |
| Ambient source disappears after pin acquisition, or a host name disappears/reappears | Same `M` | A valid retained inode/mount pin survives host unlink; never require the vanished host name. If no safe retained source exists, apply ambient omission/masking, not a host fallback. |
| Config/policy bytes change, are missing or no longer attested/enforcing | Required refusal | Refuse at attestation/enforcement as applicable. Reboot alone cannot bless unpacked, unconfigured policy. An earlier refusal is not a generation-stage witness. |
| Required native/library/runtime bytes, selected optional inventory, role/substitution, or required link target/type changes | Different `M`, or inventory/proof refusal | Refuse retained admission without publishing a new view or changing the manager. A safely reattested content change must reach the material mismatch control, independently of attestation negatives. |
| Required source or lexical/target ancestor disappears, becomes unsafe or is replaced during measurement/binding | Required refusal | Never omit, retry against a substitute inode or rely solely on the old copy. Retain required-layout completeness and pre/post-bind proof checks. |
| Required native/runtime file replaced between admissions by identical bytes and compatible role/trust; preserved helper replaced by identical content/privilege metadata | Same `M` after complete current-input verification | Reuse only independently verified old pins. Current host and retained helper have separate eight-field inode assertions; never compare an old pin against the new host inode's assertion. A replacement during either measured transaction still refuses. |
| Preserved helper owner/group/mode, capabilities, label or bytes drift; required root/alias loses trust | Required refusal or different `M` | Preserve exact vendor helper requirements, capability rejection, enforcing domains and every alias/ancestor check. Ambient relaxation cannot reach these inputs. |
| Selected pin, receipt, generation marker or mount source is missing, foreign, replaced or inconsistent | Identity/publication refusal | Deny with bounded diagnostics; do not reconstruct a retained view from host siblings or adopt an equal-looking directory. |

An unsafe retained ambient **ancestor of required material** is a required
failure. Source-only ambient fallback never covers target, manifest, mount,
read-only, labeling, resource or detach failures. If a shallow ambient inode
changes kind/owner/mode, its rejection must not mutate the manager's namespace
or underlying private dentries.

**Pin storage and exact source allowlists.** Select the manager's actual
read-only `/usr` mount tree as the retained source store. The manager's namespace
holds the initial tmpfs skeleton, copied required files, individually bound vendor
helper and accepted shallow sibling mount references after native staging detach.
Root-only `/run` records/copies remain supporting evidence; its detached `tree`
placeholders are never a populated source store. No persistent host mount, pin
daemon or process-killing recovery mechanism is introduced.

Before preparation consumes retained sources, the trusted native caller must
acquire the verified manager root and a recursive detached mount clone of exactly
its `/usr`, held by a close-on-exec descriptor. The public
[open_tree API](https://man7.org/linux/man-pages/man2/open_tree.2.html) supports
`OPEN_TREE_CLONE | AT_RECURSIVE | AT_EMPTY_PATH | OPEN_TREE_CLOEXEC` from an
already checked descriptor. A plain directory or namespace descriptor alone is
not evidence that submounts were cloned. The clone owns its mount references
even if the manager later exits; that guarantees source lifetime, not permission
to admit after losing the manager. The admission proof below defines acquisition,
identity rechecks and the exit/reexec boundary.
Failure of the public API or its existing trusted-caller permission denies;
there is no legacy pathname fallback or new payload mount authority.

An attached source in another mount namespace cannot be cloned directly by the
caller: the kernel's [source-namespace check](https://code.googlesource.com/linux/torvalds/linux/+/f24ba334afafc70c3149e9db9c0cf8ecc6d52a09/fs/namespace.c)
rejects that operation. Native acquisition uses one bounded, non-exec child to
enter the already pinned source mount namespace with
[setns](https://man7.org/linux/man-pages/man2/setns.2.html), clone the already
checked `/usr` descriptor and return exactly one close-on-exec descriptor through
an anonymous descriptor socket. The parent never changes its namespace, root or
working directory. It owns the worker deadline, identity-safe termination/reaping,
strict message validation and repeated source, namespace and clone checks.
The child uses only syscall wrappers and stack storage after creation; it does
not parse receipts, allocate, log, execute preparation or modify source dentries.
The existing trusted caller must have the required namespace-entry permissions,
including `CAP_SYS_ADMIN` and `CAP_SYS_CHROOT`; the host namespace fixture does
not qualify actual PAM permissions on either MAC backend. Native composition and
installed qualification retain that obligation. No payload capability is added.

Use only these closed source classes:

- Initial manager realization: the attested native substitution map and exact
  measured runtime-copy indices below the selected owned generation; the exact
  measured vendor helper path; and explicitly ambient immediate entries of
  covered `/usr` skeleton directories accepted by the existing phase-local
  protocol.
- Retained realization: canonical relative names declared in selected `V`,
  resolved beneath the native-owned retained `/usr` descriptor, with each
  recorded required copy/helper identity and source kind/label checked. A
  receipt cannot authorize an arbitrary process root, another generation or
  an undeclared relative path. Required alias walks use their finite proof
  closure; never follow ambient links to find bind sources.
- Invocation targets: only the independently owned bounded tmpfs skeleton
  and its terminal `/usr` attachment, with the existing component-wise target
  checks. Neither host paths nor manager dentries are writable targets.

Native owns the pin and its identity; a Python helper's path string, FD number
or digest is not independent acquisition evidence. Any inherited descriptor is
passed only to the one bounded preparation child and checked against native's
opened object/selected receipt. A versioned closed protocol must distinguish
initial versus retained sources and bind `M`, `V`, backend and caller role.
The gate's derived receipt `I` must reference the same selected source identities.
Unknown fields/versions, ambiguous source classes, incomplete required coverage
or old-format reuse refuse. The admission proof below owns the protocol composition.

Construct a **fresh invocation skeleton** from selected `V`, not from a new
ambient host scan. Bind checked retained sources into those new private parents;
apply eligible ambient omission/masking there under the existing final-source
rules. This permits unlink of a new private file placeholder without altering
the old view. Never unlink, chmod or create inside the retained source clone:
mount cloning shares underlying dentries and inodes. Safe retained sources are
validated relative to the pin; their host pathname/link count may legitimately
have disappeared. Required current-host checks still run separately. Preserve
the helper's bytes/privilege checks and all eight source-local assertion fields;
support a deliberately unlinked old inode only through this explicit retained
source class, never by relaxing initial-source checks.

Unlink can change a retained vendor inode's ctime/link count without changing
its material. Keep `V`'s original device/inode provenance and `M`'s content,
owner/group, privilege mode, capability and label requirements. At each retained
acquisition, independently rehash/check that same pinned object and capture a
fresh full eight-field source-local assertion; require every field stable
through its pre/post-bind checks. This renews the observation, not the selected
inode or bytes. The retained class alone permits link count zero or the original
single link; unexpected positive hardlinks refuse. Initial/current-host helpers
still require one link. Never drop ctime, mtime or another assertion field to
make an in-flight source change pass.

The invocation tree attaches recursively read-only at `/usr`; labels and native
roles remain visible at their existing final paths. Detach only invocation-owned
staging mounts, then close all setup/source/clone/receipt descriptors before MAC.
The acquired detached clone is first attached to an identity-checked private
staging parent because Linux refuses recursive legacy binds from a detached
mount. Preparation receives a separate empty invocation parent. Lazy detachment
of that source staging tree removes subordinate mount lookups even while its
root descriptor survives; do not use that consumed root as a later complete
source tree. Final source verification instead uses the same originally pinned
manager `/usr` and proc mountinfo, while strict actual `I` coverage and `V`-to-`I`
derivation bind its required inodes to the rehashed original manager sources.
There is no manager refresh or host ambient source lookup at that boundary.
The new `/usr` owns its references after descriptor closure; the original manager
retains its own references throughout. Closing an unattached detached clone
releases it. A later entry takes a fresh verified pin; it never trusts a saved
PID, FD number, namespace number or unpopulated disk tree as a live source.

**Publication, interruption and lifetime.** Keep the existing admission lease,
exclusive preparation lock, runtime mode 0700, owned single-link mode-0600
records and per-inode SELinux checks. Publish complete `M` records/copies and
each `V` receipt atomically under the lock, with exact schema/membership/hash
verification on reuse. Native finalizes the initial `V` or derived gate `I`
after actual binding/omission. Its immutable identity can be placed in the private
tree before read-only attachment; this is provisional until attachment,
read-only verification and staging detach succeed. Only then publish the
root-only completion record under the lock, before final MAC. Interruption
before completion leaves no ready source, even if its private marker exists.
The private view carries `M`, source `V` and, for a gate, its derived `I` bound
to that receipt; a material marker alone cannot certify mount coverage or
completed staging detach. A published receipt without a verified live view is
not an admission source.

Retain at most four completed realization generations per boot, including their
supporting material copies/records; several layouts with equal `M` must not
bypass that ceiling. Reuse selects an existing `V`, so repeated ambient changes
do not consume new generations. A new manager without a reusable live source
may make a fresh current-host realization under the existing bound; gate
admission never silently manufactures a replacement manager. No legacy generation
is adopted as the new format; deployed code/policy changes keep the existing
reboot activation boundary. Preserve 32,768 layout/record bounds, 64 MiB manifest,
512 MiB copy/tmpfs ceilings, bounded alias walks and the 60-second helper deadline.

Only identity-proven owned incomplete publication is reclaimable under the lock,
after owned child termination/reaping. Refuse mounted or hardlinked scratch,
foreign ownership, symlink substitution, unknown members, replaced descriptors,
receipt/marker disagreement and ambiguous completion. Never repair such state
by recursive deletion, relabeling shared software, overwriting a completed
generation or killing a manager. Failure releases only this invocation's
descriptors and identity-recorded mounts; detach failure remains denial with
separate cleanup evidence. Crashed callers lose private clone references through
kernel lifetime rules. Completed supporting records survive until reboot;
actual mounts survive as long as their namespace/clone references. Recovery
uses exact restoration/retry for an owned incomplete attempt or successful
configuration plus reboot for genuine required drift, under
[lifecycle](Lifecycle.md#retained-material-activation-and-recovery).

**Independent implementation witnesses.** These finite acceptance families belong
to 006a/006b; their linked host close-outs record implemented selectors and exact
evidence limits. Descriptor selection does not establish composed native binding
or installed admission, which remain 006/007a/007. Tests must
observe mounted inode/content/absence and independent records, rather than assert
only that producer and parser agree on a digest.

| Owner / family | Positive witness | Independent negative/control witness |
| --- | --- | --- |
| 006a — pin lifetime | Acquire original source clone; detach initial staging; rename/unlink/replace original host file and directory; close original namespace owner; observe original copied bytes, vendor inode and private layout through held clone, then through a new owned attachment after FD closure | Plain placeholder source, missing recursive submount, foreign/replaced root or wrong receipt identity refuses. Host replacement bytes never appear. Source survival after manager exit supplies no admission credit. |
| 006a — immutable required runtime copies | Replace/write original named script, product module, wellbeing import/schema and generated unit/data fixtures after copying; retained copy bytes/membership/labels stay exact | Mutate a private copy, role label, mode, member/link or hash; refuse. Independent inode checks exclude hardlinks; an escaping link/special node is not copied. |
| 006a — publication/cleanup | Complete receipt and identities survive staging detach; repeated verified reuse leaves records/copies and original manager view unchanged | Interrupt before/after each atomic publication and ready boundary; reject partial/foreign/replaced/mounted state. Inject clone/attach/read-only/detach failure and prove only owned resources released; no writable staging alias or descriptor survives success. |
| 006b — ambient transitions | Establish unchanged baseline, then one-at-a-time add/remove/rename/mode/owner/kind and disappearance/reappearance changes for file/directory/link inputs; same `M`, original `V`, original safe pins or eligible private mask/absence | Use new host content tokens and source-open spies to prove no host reopen. Make the retained ambient inode unsafe and prove omission/masking with original manager dentries unchanged; required-ancestor equivalent refuses. |
| 006b — original stale-manager regression | With unchanged required inputs, establish baseline admission, add an unrelated empty directory, then admit again from the original view; assert both material equality and native-selected source identity | Preserve the historical pre-fix `manager-generation-stale` before/after control from run `20261019T061016Z-d39f14ad`. Its retired export is historical evidence only; create a permanent reproduction, not a claimed rerun of removed probes. |
| 006b — required drift and identical reinstall | Identical-byte/trust-compatible reinstall remains compatible using independent host/retained assertions; unlink the old helper and require original inode/content plus a fresh stable eight-field assertion, including changed ctime and zero links; exact restoration recovers | Independently change config/policy, native/library/runtime content, selected inventory, helper privilege metadata, required aliases/ancestors/completeness and source identity during measurement. Retained hardlinks or any change after assertion capture refuse. Distinguish attestation refusal from reattested material mismatch; none publishes/adopts a new retained view. |

006 owns the composed native admission witnesses below.
007a/007 must retain real installed before/after ambient availability, exact
manager/view/source identity, enforcing positive/negative execution, required
drift refusal/restoration, usable public reentry and ordinary-account controls
on both named targets. Existing `verify_updates()` proves retained replacement
and reexec isolation; `system_native_update.stale_admission()` requires a specific
generation reason. Their complete canonical histories and exact input comparison
govern reuse; neither a test name nor case 267's earlier attestation refusal
supplies new generation-stage or immutable-pin acceptance.

### Planned retained-view admission proof

This is **005's reviewed composition**, now dispatched by the production
`kiosk_confinement()` caller through the
[fresh-manager](../../tools/kiosk_fresh_startup.h) and
[retained-gate](../../tools/kiosk_retained_startup.h) coordinators. Each attempt
owns one original deadline, preparation lock and bounded helper, independent
[material](../../tools/kiosk_material_authority.h),
[policy](../../tools/kiosk_policy_authority.h) and
[original-host](../../tools/kiosk_host_proof.h) authority, actual
[realization](../../tools/kiosk_native_realization.h), descriptor closure and
preloaded MAC. Non-kiosk callbacks and the PAM-handle admission lease remain
with their original owners. No legacy format or dispatch fallback is selected.
The old `manager_generation()` and engineering `manager_boundary()` observations
are not the new admission proof.

The [child owner](../../tools/kiosk_preparation_child.h),
[channel](../../tools/kiosk_preparation_channel.h) and
[service](../../tools/kiosk_preparation_service.py) transfer measurement, native
selection and intended result through that one child. Measurement also includes
a sealed finite NSS account snapshot; native matches its UID to the independently
pinned owned marker. Root and administrative groups refuse. NSS runs only in
the bounded child, under the original alarm/deadline. The fixed native entry
checks installed support source bytes and exact inherited lock/lease descriptors;
it changes neither import search nor bytecode caches. Anonymous zero-mount-ID
records require read-only CLOEXEC descriptors, zero links and all four immutable
seals; directories and named sources retain positive mount identity.

The fresh coordinator verifies current material/routes and independently named
copies before combining M/V/pins/copies/ready publication. Runtime manifests keep
their domain/length framing and full-file hash; channel results remain canonical
JSON. Successful child reap precedes scratch acceptance. Ambiguous scratch and
unresolved child identities retain their cleanup owner; completed records survive
a post-ready refusal. Original root/runtime inodes are checked before adopting
namespace-local lookup descriptors, before any helper or overlay. Host sources
are never refreshed after attachment.

The retained coordinator acquires the actual unit/leader/task/executable/root/
namespace proof through the [manager owner](../../tools/kiosk_manager_admission.h).
Its [completed-record owner](../../tools/kiosk_retained_record.h) selects only the
marker-named V, binds boot/root/marker/original attachment and M/V/pins/ready,
checks exact flat membership and independently verifies supporting/native copies
against current M and V. A ready parser supplies syntax only. The native-derived
ambient vector cannot relax a required path or ancestor. Recursive acquisition,
private source staging, one checked preparation result and actual fresh-parent
binding produce invocation-only I, preserving V's slots and origins. No manager
record is changed and no completed-generation slot is consumed.

After identity-owned staging detach, final original-host/routes/policy checks,
strict actual invocation coverage and the same pinned manager's source/topology
proof precede setup-FD closure and MAC. The original manager pidfd/proc/bus stay
open through a last same-manager check and then close before MAC. Explicit failed
recovery has its own bounded cleanup budget, never new admission authority.
An unresolved cleanup keeps the exact PAM-owned state and preparation lock and
denies; it never signals a manager or sweeps ambiguous files.

Finite host fixtures exercise these native transactions with real private mount
trees and a real copied/reexecuted fixture manager. Account/PAM/system-bus/MAC
observations remain fixture boundaries. The [active 006 brief](../Kiosk-Prompt-Tasks/006-generation-implementation.md)
still owns the complete cross-phase race/publication/reexec matrix, both actual
bootstrap-policy checks and cumulative host acceptance. 007a/007 retain actual
public installed histories. Production dispatch, component counts and source
review provide no substitute for those remaining obligations.

**Authority and ordered acquisition.** Keep one native owner in the actual PAM
caller. Its acquisition, helper, binding and final checks share a bounded
transaction; retain the 60-second preparation deadline and five-second external
query limits, without unbounded retries. All setup descriptors are close-on-exec
except explicit duplicates passed to the one bounded preparation child. No
descriptor or mount authority reaches the eventual session payload.

1. Acquire the existing shared admission lease, then the exclusive preparation
   lock. Check each named lock still denotes the opened private, root-owned,
   single-link inode after locking and before releasing preparation ownership.
   Preserve GDM routing's existing login lock and lifecycle lock order. Before
   overlay attachment, separately pin the caller's original host `/usr` lookup
   root and its host `/` root for dependencies outside `/usr`. A `/` descriptor
   alone still crosses a later `/usr` overmount and is insufficient. Later host
   checks must start beneath the original `/usr` descriptor for those paths.
2. Verify the owned account, current attested config/policy and enforcement, and
   measure current required `M`. For a gate, query the system manager's exact
   `user@UID.service` using the public
   [systemd unit interface](https://www.freedesktop.org/software/systemd/man/latest/org.freedesktop.systemd1.html).
   Read MainPID, InvocationID, ControlGroup and active state with bounded calls;
   accept only active or reloading state with the complete invariant below.
   Refuse absent, starting, stopping, failed or unknown state. Acquire the leader pidfd
   and an opened proc directory, then repeat the unit/leader observation. Bind
   all subsequent reads to those objects; do not follow a new numeric PID.
3. Establish the complete manager proof below. Open its root and mount-namespace
   descriptors through the pinned proc object, resolve exactly its `/usr`, and
   acquire the recursive detached clone specified above. Recheck manager identity,
   namespace/root and selected `M,V` after acquisition. Verify the clone's actual
   required mounted inodes, bytes, labels and finite mount coverage against the
   completed source receipt. A recursive flag, matching marker, namespace number
   or successful clone syscall alone does not establish submount coverage.
4. Pass only the selected clone and owned receipt/copy descriptors to preparation.
   Its new skeleton comes from `V`; host measurement contributes required material
   only, never a replacement ambient layout. Native checks the returned closed
   protocol against its own acquisitions before binding. Revalidate current-host
   required paths through their original host lookup roots, and retained sources through
   the clone, with separate source-local assertions. Required aliases use their
   explicit bounded component/target walk in the appropriate root. For host
   proofs, dispatch entry into `/usr` to the original `/usr` descriptor, including
   when expanding lexical or absolute aliases such as `/bin`; never let a kernel
   symlink traversal cross into the overmount. No ambient symlink supplies a
   source and no absolute link escapes into the other source class.
5. Bind into fresh invocation parents, record actual outcomes in `I`, attach
   recursively read-only and verify actual attachment/required coverage. Complete
   identity-owned staging detach and ready publication under the lock. Recheck
   current required observations, policy attestation/enforcement, the manager
   proof and unit identity after binding and before final MAC. Late unit queries
   use a bounded native system-bus call; do not start a verification process in
   the newly attached view. A required pathname replacement during the transaction
   refuses even when the new bytes match. Same-byte compatibility applies only
   to a new transaction with independently verified host and retained assertions.
6. Confirm preparation's child is reaped and close every source, clone, host
   lookup-root, proc, namespace, receipt and bus descriptor after its last check.
   Keep the manager pidfd through
   the last pre-MAC liveness check, then close it before MAC. Set the manager-only
   unit environment, clear inheritable and ambient capabilities and apply/verify
   the existing final MAC transition. Failure at any step denies and releases only owned state.
   Keep preparation ownership through MAC; the admission lease still spans the
   PAM handle as before. No subprocess runs after final MAC.

**Manager proof and reexec.** The proof binds boot, owned UID, unit invocation,
leader PID/starttime, pinned proc/pidfd, cgroup, root, mount/user/PID namespace
objects, selected `M,V` and manager executable identity. A
[pidfd](https://man7.org/linux/man-pages/man2/pidfd_open.2.html) observes process
lifetime; it neither freezes exec/credentials/namespaces nor makes pathname reads
atomic. Treat exit, hangup, poll/read failure or disagreement as refusal, never
as permission to select another manager within this transaction.
The actual leader cgroup must lie within the unit's ControlGroup on component
boundaries; retain that exact observed cgroup through final validation, including
the supported manager's `init.scope` placement.

Enumerate every manager task under the pinned proc directory with finite bounds.
For each opened task, check TID/starttime, all four UIDs and GIDs, expected
unprivileged supplementary groups, absence of effective/permitted/inheritable/
ambient capabilities, exact manager enforcing label, root and the same namespace
objects and private `M,V` view. Bounding capabilities are not active capabilities.
Mount namespace must differ from the original host's; user/PID namespaces must
match the supported system manager's, with no unexpected identity mapping.
The expected executable is the selected role's copied manager ELF inode/content,
not merely the text of `/proc/PID/exe`. Recheck task identities and membership
around the observation and at final validation. Any observed task exit, addition,
credential/label/root/namespace change or unavailable record refuses this attempt;
ordinary task churn may retry as a fresh public admission, not a partial scan.
The leader's process pidfd alone does not witness individual thread lifetime.

These observations are backed by the existing trusted systemd executable and
enforcing role policy: the manager cannot write the skeleton or measured copies,
mount, enter another namespace, acquire privilege or transition to an unrestricted
domain. Reexecution of that same pinned executable preserves the unit invocation,
leader lifetime, material and private mount tree. Allow it only when the full
proof remains identical; an overlapping unstable census refuses for fresh retry.
Repeated observations are not an atomic exec barrier. An unobserved compatible
reexec is safe because it preserves these invariants, not because the pidfd
detects exec. 006 must verify those policy restrictions and both supported
reexec paths alongside its race controls; do not add ptrace, freezing, signalling
or a new manager-coordination service to manufacture atomicity.

**Concurrency and commit boundary.** The preparation lock serializes cooperating
admissions and configuration/publication, not manager exit/reexec or distribution
unpack. The shared admission lease excludes loader/removal writers. Required
descriptor/path checks and attestation close unpack races independently; do not
claim the locks freeze all host files. Poll the same manager and recheck the same
unit invocation at acquisition, after cloning and at final validation. A changed
MainPID, InvocationID, cgroup, namespace, root, executable or receipt denies even
when material hashes match; no refresh to a new identity occurs inside the call.

There is no atomic kernel operation combining remote manager liveness and final
PAM return. The last successful validation is the admission decision boundary.
A manager that exits before it is observed there denies, even though the clone
survives. A subsequent exit cannot substitute sources or remove the gate's owned
read-only mounts: the admitted gate still has its independently confined view.
Existing session startup/exit owns unavailable services and return to sign-in;
this design promises no keepalive or uninterrupted form after manager death.
Fresh admission must prove the actual current manager again. Do not adopt a
replacement manager from a surviving old clone or signal a manager for recovery.

**Native receipts and publication.** The new protocol binds format, caller role,
backend, `M`, source `V`, acquisition identity and a finite source index/class for
every bind. Required/ambient status comes from the attested inventory and complete
required closure. Native cross-checks it against selected records, never a
producer's ambient flag alone. Retained indices resolve only beneath the acquired
clone and must match `V`'s provenance; equal bytes at a foreign inode, an arbitrary
FD or a new host source are insufficient. Initial realization keeps the original
host/copy allowlist. A retained source uses the explicit zero-link allowance and
renewed eight-field assertion above; initial/current-host rules stay strict.

Source `V` is native's original realized view, including late omissions, not the
helper's intended layout. Gate `I` records only that invocation's checked
derivation: eligible ambient omission/masking may narrow it, never add a source
or remove required coverage. Native verifies required mount sources independently
after binding and read-only attachment; clone mount IDs can differ, so relate
them to pinned inode/role/coverage witnesses rather than equating numeric IDs.
No receipt is its own recursive hash input. Private marker fields identify the
canonical receipt whose hash is computed without that self-reference.

Root-only ready records bind the completed receipt, boot, native publisher and
actual private view provenance. Initial publication occurs in the trusted PAM
executor before the final manager exists: the publisher PID is not a claimed
future MainPID. Later acquisition independently binds the live confined manager
and actual mounted sources to that receipt. Pending marker, completed disk copy,
or ready record from failed MAC/exec cannot qualify without that live proof.
Gate publication never changes the manager's `V` or consumes another generation.
Interruption before ready leaves an incomplete attempt; interruption after ready
still requires exact live-view verification. Ambiguous/replaced ownership or
receipt/mount disagreement refuses, with no overwrite, relabel or host rebuild.
Only proven owned incomplete scratch is recoverable under the existing lock;
completed generations and their four-generation budget survive until reboot.

**Finite composition witnesses.** The 005a ambient/required transition table and
006a/006b families above remain unchanged. The following are planned witness
families for **006**, not registered selectors or current passes. Use barriers
and independently opened descriptors/real native fixtures, not timing sleeps or
only producer/parser agreement. Keep tests inside existing resource owners.

| Boundary | Positive witness | Independent refusal/control |
| --- | --- | --- |
| Manager identity | Original unit invocation, leader/tasks, credentials, enforcing role, executable and namespace/view survive a full gate bind | At acquisition, post-clone and final validation inject exit/PID reuse, same-UID impostor, changed unit invocation/MainPID, wrong cgroup/root/namespace/label/executable, privileged task or task-set change; deny without adopting a replacement or changing completed records |
| Exit and reexec | Same-inode reexec retains the original namespace, material, source receipt and enforcing allowed/denied execution | Exit after clone but before final check denies despite readable original clone bytes; incompatible/unstable reexec denies. Exit after the decision cannot expose host replacement bytes or an unconfined gate |
| Concurrent writers | Sequential healthy admissions reuse the same source and leave the manager's dentries/receipt unchanged | Contending admission/configuration and loader/removal barriers refuse without partial publication; exact replaced-lock inode refuses; unlocked required unpack drift at measurement/bind/final proof refuses |
| Current-host lookup after attachment | Independently opened original host `/usr` and retained sources keep distinct lookup identities across overlay attachment, including lexical/absolute aliases | After attachment, change a required original host `/usr` input while private copy bytes remain unchanged; final host proof must refuse. A `/`-only lookup that crosses into private copies cannot satisfy this control |
| Source and invocation receipts | Actual source mount coverage matches `V`; eligible ambient loss produces stricter `I` in fresh parents and retains required sources | Wrong clone, missing submount, placeholders, changed source index/class/role/backend/version, forged ambient-required status, missing required mount, mixed `M,V,I` or source replacement denies; independently prove manager dentries unchanged |
| Completion and cleanup | Complete attach/read-only/detach/ready/MAC order, then close every setup FD; attached view keeps its sources | Interrupt each boundary including ready-to-MAC/exec; fail query/clone/proof/attach/read-only/detach/MAC and prove no partial source is admitted, only owned resources are released, and primary/cleanup failures stay separate |

007a/007 compose the existing canonical `verify_updates()`/manager observer and
specific `stale_admission()` histories with real ambient before/after public entry.
An ambient positive must identify the unchanged manager and original `V`/sources,
observe the actual private absence/mask/content, reach a usable passwordless form,
and retain enforcing native positive/negative and ordinary-role controls. Required
drift needs its actual stage, exact restoration and the declared reboot/reentry
history. A reattested material mismatch must reach manager-material selection;
an earlier payload denial does not cover it. Preserve whole valid existing
histories only after exact changed-input applicability review at 011a/011.

Remaining risks are explicit implementation/qualification obligations: native
bootstrap access to proc/recursive clone and bounded bus queries on both MAC
backends, complete mount/source versus receipt validation, task churn and cleanup
at every publication cut. API failure remains closed, without a pathname fallback
or broader payload permission. Shallow distribution data retains its existing
compatibility limits. No concrete source-store gap requires redesign or a new
prerequisite; 006a/006b/006 own these finite implementation proofs and 007a/007
own installed acceptance. Review acceptance supplies neither runtime pass.

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
login admission, 269 platform integrations and 290 sibling mask/omission
isolation across an owned host replacement in a retained public station. The
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
