# Startup, installation, and updates

[System design overview](../System-Design.md)

Read this for broker readiness, boot/login ordering, installed paths,
provisioning, and package activation. Removal has its own focused document.

Implementation: [service.py](../../broker/oh_no_parent_control/service.py), [Makefile](../../Makefile), [preinst](../../packaging/lifecycle/preinst.in), [postinst](../../packaging/lifecycle/postinst.in), [provision.py](../../tools/provision.py), [package_activation.py](../../packaging/package_activation.py), [execution_policy_ready.py](../../tools/execution_policy_ready.py).

## Startup, login, and update lifecycle

Checkout installation through `make install` gives APT five retries per failed
transient download, covering both package indexes and dependency archives. APT
owns the backoff and transient-error classification, including HTTP 503. An
exhausted index refresh still stops before package installation through
`APT::Update::Error-Mode=any`; package configuration failures are never retried
by the Make recipe. These options apply only to this invocation and do not
change the computer's APT configuration.

The `.deb` pre-installation script requires Ubuntu (`ID=ubuntu`) version 26.04
or newer for installs, reinstalls, and upgrades. It reads `/etc/os-release`,
falling back to `/usr/lib/os-release` only when the former is absent. Other
distributions (including Ubuntu derivatives), older Ubuntu releases, and
missing or unverifiable release information are rejected with an explanatory
message before package files, state, or services are changed. Aborted-upgrade
recovery and removal remain available. This gate activates during package
installation (`none`); it adds no runtime integration or saved-data migration.
The child extension currently declares only GNOME Shell 50 in
[metadata.json](../../child/metadata.json). OS-version admission and desktop
compatibility are separate: acceptance remains Ubuntu 26.04/GNOME 50 until a
later desktop is explicitly supported and qualified.

Broker construction first reconciles the discovered accounts' current
AccountsService filters into fapolicyd. It then reasserts the packaged extension's
activation for every
preference-enabled eligible child and attempts to clear stale live-session
runtime caps. Only after those steps does it register the D-Bus object. An
nonrecoverable execution-policy reconciliation or extension-activation failure prevents the
service from becoming ready. Clearing stale session caps is best-effort:
unavailable sessions may be skipped, and an exception at this stage is logged
without preventing registration.

This current global extension-refresh dependency can strand an otherwise healthy
kiosk request when another enabled child's home is unavailable, for example an
unmounted encrypted home. The resilience target's
[broker readiness decision](#prospective-configuration-and-activation-recovery)
must address that cause; a generic unavailable-service result is not its resolution.

Local executable or wildcard-directory rendering failures use the
[application-rule isolation contract](Applications.md#live-filter-and-execution-rules):
the broker installs the remaining rules, retains saved choices for retry, and
publishes affected app IDs for the Parent warning/error dialog. Registration
therefore does not claim that every saved app rule is enforced. Storage and
backend activation failures remain fatal; they are not treated as isolated app
errors.

Startup uses live AccountsService filters as its enforcement input and saved
preferences for patterns and extension enablement. It does not restore every
saved daily limit or app block after ordinary removal cleared AccountsService.
Reinstallation can therefore show retained choices without having replayed those
restrictions. Reapplying the corresponding Parent controls projects the choices
back into live state; no removed one-time grant is recreated.

Successful object registration emits fixed `onpc.service` elapsed phase timings.
The role-checked read-only `GetStartupTimings` D-Bus method supplies six real
monotonic nanosecond timestamps for construction, completed policy/extension
reconciliation, attempted cap cleanup, and the start/end of registration.
The [startup observer](../../tests/e2e/README.md#broker-startup-observation)
queries the pinned live bus owner and brackets those timings with the existing
systemd invocation/process and boot continuity checks. Invocation IDs, PIDs,
bus names, and absolute monotonic timestamps are not recorded in automatic
diagnostic logs or feedback reports. Diagnostic-write failure does not gate
readiness. Broker code activates with `process-restart`; this additive method
adds no saved-data migration or GDM dependency.

On Ubuntu, the packaged fapolicyd drop-in keeps the daemon in systemd's `activating` state
until a root-owned canary execution is denied by the live kernel policy and
the exact packaged child-module trust records are present in its live database. The
display manager requires completed fapolicyd startup, so a managed graphical
login cannot begin while the daemon rebuilds its trust database. Readiness
failure therefore fails closed before the login manager starts.
The display-manager drop-in depends on fapolicyd, not the product broker.
Broker registration failure prevents product operations but is not a separate
GDM startup gate.

Fedora uses a separate oneshot `oh-no-parent-control-execution-policy-ready.service`
for the same canary. It requires and follows fapolicyd, has a 90-second startup
timeout, and restarts with the daemon through `PartOf`. The Fedora display manager
requires completed canary readiness, and package configuration starts that gate
before broker activation. Separating the gate avoids systemd preparing fapolicyd's
SELinux-labelled runtime directory again for an unrelated `ExecStartPost` command.
Configuration compiles and reloads rules before the gate, including an owned
Fedora-only early root-canary deny before the distribution's trusted-file allow.
Ubuntu's drop-ins and readiness helper are unchanged.

Both packages also ship a separate
[fapolicyd recovery drop-in](../../data/systemd/fapolicyd.service.d/oh-no-parent-control-recovery.conf).
Systemd restarts the daemon after unexpected nonzero exits, abnormal signals or
timeouts using `Restart=on-failure`, with a five-second delay. This includes
trust-database failures that exit with status 1 and were left down by the
upstream `on-abnormal` policy. The start budget allows five starts within 300
seconds, including the initial and manual starts; exhausting it leaves the
service failed for diagnosis rather than scheduling another retry. Expiry of
that window alone does not start the service. This is a start-rate limit, not a
total retry cap: repeated slow failures, including Ubuntu's 180-second startup
timeouts, can outlast the window and continue retrying. Deliberate service stops
and clean exits remain stopped. Recovery uses the ordinary startup path and its
existing distribution-specific readiness checks; it does not repair the database or
replay a failed approval. A request during the outage can still fail and must be
submitted again after recovery. Existing dependency diagnostics retain earlier
service failures after a successful restart.

Normal automatic restarts propagate through the existing `Requires` and
`PartOf` dependencies to already-active dependents. This reruns Fedora's
readiness gate and can restart the display manager on either distribution,
ending graphical sessions. Failed or inactive dependents are not started by
that propagation: daemon recovery after a boot failure does not by itself
recover a failed readiness gate or display manager. These consequences follow
systemd's [automatic restart](https://github.com/systemd/systemd/blob/v259/src/core/service.c)
and [dependency propagation](https://github.com/systemd/systemd/blob/v259/src/core/transaction.c)
behavior; live recovery qualification remains pending.

The shared drop-in adds no commands, runtime-directory changes or broker service
control. It is package-owned payload and removal restores the distribution's
restart policy through the existing systemd reload. Its activation manifest uses
the existing `reboot` classification for fapolicyd drop-ins; installation does
not force a running daemon or desktop to restart just to load it.

Both packages generate supplemental fapolicyd trust for the shipped child `.mjs`
modules from final staged bytes (path, size and SHA256). Configuration installs
the owned `/etc/fapolicyd/trust.d/oh-no-parent-control.trust` and refreshes a running
daemon before readiness/broker activation; a stopped daemon consumes it at startup.
Ubuntu's default `debdb` backend
[excludes packages still being configured](https://github.com/linux-application-whitelisting/fapolicyd/blob/v1.3.6/src/library/deb-backend.c).
For that exact default, configuration enables the `file` backend, preserving
the complete original configuration in an owned rollback directory. It refuses
to activate pre-existing inactive administrator trust records. Already
file-enabled configurations, including Fedora's default, are unchanged.
If this changes a running daemon's backend, configuration completes successfully
and records the normal Ubuntu reboot request. Restarting its display-manager
prerequisite could log out unrelated desktops, so a root-owned mode-`0600`
`/run/oh-no-parent-control-child-trust-reboot` guard prevents policy activation
for that boot. Both systemd and the direct launcher may start the broker's
[diagnostics-only mode](Logging-and-Feedback.md#investigation-coverage), which
retains role-checked log collection and kiosk presentation reads without starting enforcement or session
operations. The broker's product-specific `Error.RebootRequired` status drives
the shared frontend restart modal.
The global `/run/reboot-required` and other packages' reboot requests do not
select this mode or block policy. Migration completes and its separate exclusion
is released; reboot automatically expires the runtime guard
and starts fapolicyd with the new backend and exact trust readiness gate. No
manual package-configuration retry is required. An activation receipt alongside
the backend rollback records retains the originating boot ID until live trust
is confirmed or a new boot loads the configuration. Same-boot reconfiguration
therefore cannot mistake the edited file for a loaded backend. Legacy ownership
records without a receipt, including earlier failed installs, conservatively
take this activation path once. Clean installation with a stopped daemon starts
it with the new backend and acknowledges live trust in the same configuration.
The broker launcher also verifies exact live trust before importing product
code, covering direct execution and systemd's nonfatal `Wants` dependency. Its
180-second service startup budget accommodates the 120-second trust deadline
and subsequent broker construction. Rollback files, activation receipts and
their containing directories are flushed before replacing the live backend
configuration; the configuration directory is flushed after replacement too.
Removal restores the original configuration only when the owned
replacement is unchanged. Local edits are preserved and block automatic cleanup.
Because the update request is asynchronous, configuration waits up to 120 seconds
for both exact packaged path/size/hash records in the live trust database before
activating the broker. After requesting the refresh, the configuration helper
queries only the packaged path/size/hash records in a registered, read-only LMDB
transaction through liblmdb's public C API. Each transaction retains a consistent
snapshot while concurrent or queued refreshes rebuild the database. It does not
use fapolicyd 1.3.6's unlocked `--dump-db` reader or infer writer exclusion from
an `Updated` journal event. Missing records are retried with a fresh snapshot;
database/command failures preserve pending activation for configuration retry.
For fapolicyd 2.0, the reader resolves `trust.meta/current` and the published
`trust.slot_*` database within that same snapshot. Older databases without
publication metadata retain the `trust.db` route. Invalid publication metadata
fails closed instead of consulting a retired database.
The refresh and exact-record wait share the same 120-second deadline, with each
database read isolated in a bounded subprocess. Boot readiness and direct broker
starts use the same safe reader without requesting a refresh. Only the LMDB
reader-table lock file needs write access; the broker's service sandbox grants
that exact path while retaining read-only access to the database contents. A
missing or unwritable lock file fails closed instead of allowing LMDB's unlocked
read-only-filesystem fallback. Both packages explicitly depend on liblmdb.
The reader holds an independent Linux open-file-description read lock on the
LMDB lock file's initialization byte from before opening the environment until
after closing it. fapolicyd's fanotify descriptor closes can release its POSIX
file locks; without this guard, another reader can mistake the live environment
for an exclusive one and reinitialize or destroy its shared mutexes (including
with Ubuntu's LMDB 0.9.31). Guard contention returns a fixed temporary-unavailable
status; readiness retries within its existing 120-second deadline without
opening an unguarded environment. Other lock, database and command failures
remain fatal. Registered
read transactions continue to protect snapshot pages during concurrent writes.
The existing startup-exclusion marker remains present through a same-boot trust
wait and earlier provisioning, including configuration retries without `preinst`.
D-Bus activation cannot bypass the trust gate; an existing broker is stopped
and verified inactive before configuration proceeds.
This database check does not establish a fresh Shell import or usable child UI.
This covers clean installs, upgrades, reconfiguration and reinstalls even when
the distribution's package trust filter excludes `.mjs` under `/usr/share`.
The filter, language rules and enforcement mode stay unchanged. Trust generation
never hashes mutable installed files or trusts a whole extension directory.
Modified/substituted owned trust files block configuration/removal, and removal
deletes only the package's records and refreshes the surviving daemon.
The lifecycle decision activates during configuration (`none`); the added boot
trust gate changes the fapolicyd startup drop-in (`reboot`). A Shell that already
cached a failed import needs a new child session to retry it. Package configuration
does not force logout.

The PAM account stack exempts `systemd-user`, the kiosk account, and members
of Ubuntu's `sudo` group from the Malcontent account check.
For other accounts, the public AccountsService `LimitType` helper skips
`pam_malcontent` only when the account is positively confirmed unrestricted;
unknown or malformed state continues through the enforcing module. The kiosk
account additionally has dedicated-session admission checks. The shared PAM
profile requires the [native module](../../tools/pam_oh_no_parent_control.c) in
both account and session stacks. It admits that account only for `gdm-password`
and `systemd-user`, and invokes the
[login helper](../../tools/oh-no-parent-control-login-check) only for the kiosk's
GDM routing checks. Ordinary accounts return success without launching a helper;
their native Polkit password check cannot execute the isolated Python gate.
Other accounts and `systemd-user` do not query routing metadata
or acquire a station lock. A root-owned, no-follow, private-mode `/run` lock
serializes station authentication from the account check through session opening;
contention, unsafe lock files and missing account-stage state deny admission.

First configuration creates the reserved account already expired through the
native account tool. Before reconfiguration, the provisioner validates the
package-owned identity, home and administrative groups, records its original
account expiry in a private UID-bound transaction, and expires it before other
configuration work. Native account admission therefore remains closed even for
an already visible passwordless identity. The transaction survives interruption
and reboot; retries preserve the original expiry and refuse changed ownership,
unsafe records or unrelated expiry changes. Home-local initial-setup markers
are written after directly dropping UID, GID and supplementary groups with
`setpriv`, so setup does not need admission through the deliberately restricted
kiosk PAM service. Only after shared PAM verification and successful final
confinement integration does configuration restore the recorded expiry and
retire the transaction. Removal preserves this barrier until verified owned
account deletion under the [account cleanup contract](Package-Removal.md#pam-and-kiosk-ownership).

Provisioning sets and reads back AccountsService `Session=oh-no-parent-control`,
`SessionType=wayland` and `SystemAccount=false`. AccountsService's public
`CacheUser` operation creates retained state for a fresh nologin account; the
provisioner verifies public `SystemAccount=false` and `Saved=true` afterward.
An already retained visible account needs no cache mutation after durable cache
verification. AccountsService's `CacheUser` changes an existing retained hidden
account only in memory and exposes no public classification/save method. The
product therefore owns a versioned, fixed-account cache adapter rather than
toggling unrelated properties or uncaching retained metadata.
The packaged [AccountsService drop-in](../../data/systemd/accounts-daemon.service.d/oh-no-parent-control.conf)
runs [the provisioner's adapter](../../tools/provision.py) at systemd's start-pre
boundary, before the daemon reads its cache. Only the unchanged package-created
kiosk UID and reserved home qualify. The adapter pins root-owned directories and
regular singly linked files without following symlinks, accepts the distributions'
root-group-writable AccountsService parent, and changes only the unambiguous
`[User] SystemAccount` boolean. All other bytes, ownership, permissions and extended
attributes, including Fedora's SELinux label, are preserved.
Anonymous temporary storage avoids interruption residue while writing. Publication
uses one fixed transaction slot with a product xattr recording source inode,
before/after digests, UID and metadata digest. A retry removes only an exactly
matching owned slot, or finishes cleanup of the exact committed marker; foreign
or changed state is preserved and refused. No directory sweep or retained-cache
deletion is involved. Restart and reboot repeat the same guarded start boundary.
The adapter accepts the reviewed 23.13.9 cache schema. Fedora's RPM build derives
runtime version `26.03.0` from its build Git date; that spelling additionally
requires exact reviewed package `accountsservice 23.13.9-16.fc44`. Unknown versions
refuse migration and require renewed source and installed qualification.
The hook's failure is ignored by systemd to preserve AccountsService availability
for ordinary users. Provisioning independently checks public visibility and saved
state plus the durable cache, refusing kiosk configuration when repair failed.
It restarts AccountsService only for retained classification repair or recovery;
fresh accounts continue using public `CacheUser`. Retained icons are preserved;
fresh accounts receive the product artwork. Already-correct routing and disabled
time limits avoid setter calls, so a successful visibility migration is not
followed by an unrelated save that canonicalizes retained metadata. Necessary
routing/time-limit corrections retain their public setters and normal daemon
serialization semantics. Engineering qualification and its limits are described
in [Kiosk confinement](Kiosk-Confinement.md#verification-scope-and-evidence-limits).
The upstream [manager implementation](https://gitlab.freedesktop.org/accountsservice/accountsservice/-/blob/main/src/daemon.c),
[user-state implementation](https://gitlab.freedesktop.org/accountsservice/accountsservice/-/blob/main/src/user.c)
and [public user interface](https://gitlab.freedesktop.org/accountsservice/accountsservice/-/blob/main/data/org.freedesktop.Accounts.User.xml)
own the daemon's persistence behavior. Fedora's
[package definition](https://src.fedoraproject.org/rpms/accountsservice/raw/f44/f/accountsservice.spec)
and upstream [version generator](https://gitlab.freedesktop.org/accountsservice/accountsservice/-/blob/23.13.9/generate-version.sh)
explain its source/runtime-version distinction.
The login helper checks the dedicated preference during account and session
authorization, and requires PAM `XDG_SESSION_TYPE=wayland` at session opening.
It does not mutate a valid preference or depend on GDM saving its selection
between these callbacks. The lock serializes preference checks and repairs.
The helper uses an isolated Python interpreter, bounded, noninteractive
system-bus calls and a fixed child environment; the module bounds
and reaps its helper child. That child retains the lock if its PAM worker aborts,
until its bounded routing work ends. Failed checks never become success after recovery.
A wrong default, rejected selection or interrupted transaction is repaired
through public AccountsService setters and denied; a subsequent login can retry
with the dedicated default. Unavailable metadata or failed verification denies
admission. PAM teardown releases the lock without deleting its inode.

GDM 50's
[worker](https://github.com/GNOME/gdm/blob/50.1/daemon/gdm-session-worker.c) and
[settings save](https://github.com/GNOME/gdm/blob/50.1/daemon/gdm-session-settings.c)
do not provide a public PAM contract attesting to the next executable.
`GDMSESSION` arrives after PAM session opening, so it cannot enforce that boundary.
The saved preference is configuration, not proof of the next command. The
required final execution boundary constrains the caller's later exec even if
GDM's save fails or its selected command changes after the preference check.
Validation against a supported GDM/greeter must include the actual final execution.
The retained legacy [PreSession hook](../../data/gdm3/PreSession/Default) is only
compatibility defense for GDM versions that invoke it; GDM 50 does not invoke it.
Session preference, the account's shell and that obsolete hook are insufficient
to confine a graphical GDM login. Local routing diagnostics are described in
[Logging](Logging-and-Feedback.md#kiosk-admission-diagnostics).
The product Polkit rule denies the station changing its own AccountsService
metadata. These layers complement the kiosk compositor and disabled XDG
autostart files; hiding desktop controls is not the account confinement mechanism.

The [confinement integration](../../packaging/kiosk_confinement.py) prepends an
account integrity check and appends a required final session gate to
`gdm-password` and `systemd-user`. It records exact original/owned PAM bytes,
validates included session control flow, and refuses drift or rules which could
skip the final gate. A kiosk-only guard skips the vendor keyring session module,
which would otherwise start a daemon before confinement. Both includes and
substacks are audited against the supported session-module inventory; unknown
modules, nested keyring callbacks and jumps crossing an inserted guard require
explicit policy reconciliation. Other accounts retain the vendor callback.
The supported inventory includes LXC's `pam_cgfs.so` in direct or included
session rules. Its reviewed [LXC 6.0.6 implementation](https://github.com/lxc/lxc/blob/v6.0.6/src/lxc/pam/pam_cgfs.c)
uses native cgroup creation, delegation, migration and empty-group cleanup;
neither session callback launches a process or changes namespaces. Original
controls, options and shared stack bytes are preserved. The final MAC gate and
its teardown restrictions remain in force; compatibility adds no MAC permission
or executable route. Unknown modules and control flow that could skip the gate
are still refused.
All PAM audits share one logical-line parser, including tab-separated includes
and backslash continuations. Unsupported spelling, malformed directives and
dangling local include overrides fail closed; original vendor bytes are retained.
The same kiosk-only session guard skips direct vendor `pam_namespace` callbacks
on both open and close, including required/requisite entries. Thus active
polyinstantiation configuration, init scripts and temporary-directory cleanup
are never invoked for this account; ordinary users retain the original module
and options. Nested namespace entries and jumps crossing the guard are refused.
Supported vendor `systemd-user` stacks have no auth group: added auth/setcred
callbacks, including through `@include`, require explicit reconciliation and are
refused. An owned native auth-group rule handles the kiosk's credential setup and
deletion without invoking the implicit global `other` stack. It performs only
service/account identity checks and never authenticates the kiosk. Other accounts
return `PAM_IGNORE` and continue through an explicit `auth include other`, retaining
their original fallback. This bounds credential callbacks both before session
confinement and in the surviving `sd-pam` child without relaxing teardown checks.
Fedora's trusted systemd executor enters the restricted `manager-pam` current
domain before returning from the final PAM callback. Its non-exec `sd-pam` child
inherits that domain, including during teardown; clearing a pending exec context
cannot remove a current-domain restriction. This uses libselinux's `setcon_raw`
in the single-threaded executor, with no reverse dynamic transition. Only the
private manager/executor entrypoints can transition to the manager role.
The engineering census requires every kiosk thread to have a confined current
domain; it has no `init_t` waiting-helper exception. Earlier-candidate installed
startup, credential/teardown and active namespace engineering qualification
passed on both targets; [Kiosk confinement](Kiosk-Confinement.md#verification-scope-and-evidence-limits)
records that historical candidate scope and its limits. Those results do not
qualify the current composition or the prospective redesign.
The intermediate domain can write the inherited `kernel_t` datagram socket used
by systemd's pre-exec handoff timestamp; that object label was measured on Fedora
with dontaudit temporarily disabled. It also has `noatsecure` only for transition
to the private manager, preserving the trusted system executor/PAM environment:
otherwise libsystemd ignores `XDG_RUNTIME_DIR` and the manager exits. Other role
transitions retain secure execution. The earlier bounded live supplemental-policy
probe proved only manager/native-service startup and normal stop. The historical
installed qualification above separately covered teardown callbacks and
post-parent-exit denials for its recorded candidate.
A vendor-derived `/etc/pam.d/systemd-user` override is
verified against its `/usr/lib/pam.d` source; a vendor update requires package
reconfiguration before admission. Pending `.dpkg-dist` or `.rpmnew` replacements
for an original local PAM file require explicit distribution-policy reconciliation;
the package preserves them and refuses to replay an obsolete source silently.
Interrupted configuration retains the last
owned published bytes and can resume without adopting local edits. Admission
also requires both the installed configuration and policy bytes to match the
last successful policy load. Native preparation compares its exact snapshot
with the two verified content digests before measuring executable inputs or
publishing a private generation. Payload replacement during package unpack
therefore denies that attempt rather than mixing an unattested configuration
with loaded policy; identical-byte reinstall remains compatible.
Configuration takes shared admission followed by exclusive preparation through
all policy/PAM/attestation writes, allowing existing sessions while excluding an
in-flight native preparation. If the preparation inode is absent it instead
takes exclusive admission, without creating a wrongly labelled runtime inode;
an inode disappearing after selection refuses configuration.
The startup policy loader takes the exclusive admission/routing/preparation
barrier before reading or writing that record. It therefore cannot race
configuration or removal and resurrect a retired attestation or policy. A load
requested while an admission or lifecycle writer is active refuses without
changing state. Boot loading verifies the saved content-digest pair before
reloading, so reboot cannot accept an unpacked but unconfigured generation;
configuration must finish first. On Fedora it also restores the admission lock's
SELinux label after loading policy, before releasing the barrier.

The native module applies the boundary in the PAM caller itself, including the
parent executor which starts the kiosk's systemd user manager. It clears ambient
capabilities granted by earlier PAM modules before entering the profile. A bounded root
[preparation helper](../../tools/kiosk_confinement.py) verifies enforcing policy,
the package-created account identity and a finite native executable inventory.
It makes independent root-owned copies, never hardlinks or relabels shared OS
executables. Distribution aliases, their original ancestors and every symlink
target chain must also be root-owned and stored outside writable directories;
trusted resolved bytes alone cannot establish an executable's role.
Fedora grants the GDM caller read access to the vendor-labelled
`systemd-tmpfiles` inventory member without granting execution of that original.
It also permits file/directory metadata inspection for the private tree's sibling
entries, whose labels depend on the installed distro packages; that grant permits
neither reading their contents nor executing them. Native admission failures
report a fixed preparation stage without paths or account data.
The root GDM PAM caller receives the mount-administration permission needed to
create that private view before entering the gate; the gate receives none.
The native PAM caller creates and validates the root-owned mode-0700 runtime
directory under the preparation lock, before invoking the interpreter. Fedora's
named SELinux transitions therefore label both lock and tree with the dedicated
data type in the actual `init_t`/`xdm_t` caller. An incidental interpreter-domain
transition cannot select the runtime label. GDM can inspect the running manager
through systemd's public service-status API; this grants no unit start/stop
authority. The namespace and existing DAC ownership checks
continue to protect the root-only preparation storage.
A bounded directory skeleton owns every mountpoint from `/usr` to
each protected file, including matching systemd private libraries and the
reserved plugin directory. Original sibling entries are pinned with read-only
binds; copied executables occupy independent private entries. The completed
tree is attached recursively over `/usr` in the caller's private mount namespace.
One recursive read-only operation then protects the entire attached tree; the
root-only staging mounts are never exposed to untrusted execution. Preparation
checks shared ancestors once per directory and every immediate entry separately;
private-tree verification checks its complete inventory without following symlinks.
Ordinary package unlink/replacement cannot detach these private file mounts.
After the read-only `/usr` attachment succeeds, the caller detaches only the
staging mounts recorded during that admission. The `/usr` clones retain the same
inode pins; failed staging cleanup denies admission before MAC is applied.
This avoids exposing a duplicate mount tree to the user manager and dialog sandboxes.
Both targets independently pin the vendor password helper at
`/usr/lib/polkit-1/polkit-agent-helper-1`. Its native bytes, exact root ownership,
mode and Fedora SELinux label contribute to the generation; file capabilities
are refused. The helper keeps its original inode and metadata through an
individual read-only file bind, outside the copied executable inventory.
Preparation requires mode `04755` on Fedora and `0755` on Ubuntu. The native
caller checks the measured inode, size, timestamps and privilege metadata before
and after binding, refusing a replacement between measurement and mounting.
Preparation also refuses a missing, substituted or duplicate helper entry in
the later directory layout, so every measurement reaches that native check.
Fedora also verifies that the vendor `policykit_auth_t` domain is enforcing.
Its helper may exchange the PAM conversation through the confined agent's
inherited pipes and read the private tree's directory metadata/library symlinks;
these permissions add no executable route or write access to the tree.
Fedora's `pam_unix` can delegate its shadow check to the vendor `unix_chkpwd`
in `chkpwd_t`. That helper inherits the same private `/usr` and receives only
directory metadata/traversal and symlink reads for the owned skeleton. Its
executable transitions, libraries and shadow access remain vendor policy.
Ubuntu's Polkit 127 uses its distribution socket-activated root helper outside
the kiosk account; that service is not a kiosk census exception. The finite
private helper bind also covers the agent's direct-execution fallback path.
The engineering census accepts Fedora's vendor helper label only after proving
every thread's exact mixed UID tuple, native executable/inode/metadata, enforcing
domain, read-only file bind, private generation/namespace, live confined Polkit
parent and stable PIDFD/starttime/task snapshots. Unknown labels and `init_t`
remain rejected. Installed acceptance scope is described in
[Kiosk confinement](Kiosk-Confinement.md#verification-scope-and-evidence-limits).
Ubuntu uses an immediate AppArmor profile change. Fedora's systemd caller uses
the immediate PAM domain above; GDM uses a verified pending SELinux execution
context whose entrypoint check applies to the actual next executable. Missing policy, permissive profiles or
domains, unsafe storage and failed setup deny admission.

The [generated policy](../../tools/kiosk_confinement_policy.py) permits specific
transitions for the session, user manager, request app, notifications, audio,
wellbeing, authentication and sandboxed WebKit processes. Generic interpreters
are reachable only through [native fixed-argument launchers](../../tools/kiosk_session.c)
which clear startup injection variables and choose immutable scripts. The compositor's kiosk-only unit
and fixed launchers select GIO's local filesystem backend, avoiding synchronous
GVfs desktop-volume activation that the kiosk does not need. Ubuntu's finite GJS
entrypoints include the canonical `gjs-console` target of `/usr/bin/gjs`.
WirePlumber uses system configuration/data directories and empty Lua default
module paths. Its trusted custom Lua searcher remains available; default
current-directory and native-module fallback searches are disabled only for the
kiosk. This depends on the actual distro Lua library and WirePlumber's trusted
searchers and shipped scripts, rather than treating Lua's sandbox as a security
boundary. Native module/service APIs remain subject to the kernel executable
mapping and transition rules even when they accept user-supplied module names
or profile properties. The bounded installed
[platform qualification](../../tests/integration/README.md#running-the-current-installed-suite)
records package/source identities and mapped bytes, exercises hostile startup
inputs and the real native module API with positive controls, and requires
enforcing denials. Distro updates affecting those inputs need renewed review
and qualification; this does not attest to every optional plugin.
The optional GStreamer Python plugin
cannot be mapped in the confined namespace. Ubuntu's bubblewrap mounts preserve
trusted executable paths; Fedora's transitions use private executable types.
The kiosk manager alone receives an additional root-owned unit search path.
On Ubuntu, wellbeing and WirePlumber drop-ins remove `NoNewPrivileges`
and, for WirePlumber, the distribution settings which implicitly enable it,
so the fixed launchers can enter their interpreter profiles. Other accounts
retain the distribution settings. Native PipeWire and sandboxed WebKit retain
`NoNewPrivileges`: their AppArmor exec transitions stack additional restrictions
with the existing profile. WebKit and its plugin scanner lose bubblewrap's mount
and user-namespace permissions through that intersection.
GTK image decoding uses a separate finite Glycin bubblewrap/decoder route.
The installed native 2+ loaders are pinned with their containing directory;
the decoder cannot execute another program. Its sandbox permits the required
same-path trusted-library, font and private-cache mounts. Ubuntu's Polkit profile
allows root-directory enumeration for Glycin's library-symlink discovery.
Both native bubblewrap bootstraps can open their temporary root directory to
retain the descriptor required by the second pivot and oldroot detach.
Only the native bubblewrap bootstraps can configure loopback in their private
network namespace: SELinux permits non-initial-user-namespace `net_admin` and
routing-message writes; AppArmor mediates `net_admin` without supplying a Linux
capability. The finite native unprivileged bootstrap owns the new namespaces;
the WebKit and Glycin payloads receive no such permissions.
Ubuntu's finite bootstrap mount rules match AppArmor's flag normalization:
propagation and read-only remount retain native bubblewrap's `MS_SILENT`, binds
strip it, and native file binds also use `MS_REC`. Their paths remain bounded.
WebKit's Ubuntu rules include only the paired `/usr/lib` to `/lib` and
`/usr/lib64` to `/lib64` aliases and its distribution's exact native helper
and injected-bundle directories. Runtime/home binds include their roots and
contents; timezone, font, native GStreamer helper and DMA-buffer device binds
remain bounded. Bubblewrap's temporary metadata bind targets only
`.flatpak-info`, never an executable pathname. Both native bootstraps enter through a fixed
[launcher](../../tools/kiosk_bwrap.c) which prepends a read-only `/usr/bin` bind,
then forwards the original arguments and descriptors to independently pinned
distribution bubblewrap. Admission swaps those two executables only in the
private tree; source and destination identities both enter its generation.
The app, authentication agent and services cannot execute the native helper
directly. This supplies WebKit's existing D-Bus proxy inode before its individual
bind, without permitting executable-path placeholder writes or changing the
host's bubblewrap. Both bootstrap profiles retain their code-write denials and
distinct payload routes.
Fedora's native bootstraps may remount and detach the `fs_t` filesystem backing
the pinned `/usr` view and mount on regular-file
placeholders in their private `tmpfs_t` device directories. WebKit's bootstrap
also remounts read-only `sysfs_t` metadata and binds its `locale_t` timezone file.
Its repeated scanner, proxy and vendor PTP file binds retain each source inode's
type; mounting over an executable target never relabels writable source bytes
as that target. No `bin_t` execution is granted. The payload receives none of
these mount permissions. These SELinux grants apply by type, rather than pathname
or detach flag; the pinned native bootstrap and kernel namespace/capability
checks bound their use.
Ubuntu's optional Snap session-agent service/socket, desktop-integration and
prompting services, and firmware-notifier service/timer are masked only in the
kiosk's private unit path, avoiding repeated activation of applications
unavailable in that session.
The kiosk's private D-Bus data path also supplies exact Settings and Launcher
activation definitions bound to that masked unit. Their inert executable fallback
prevents the vendor definitions from launching `snap userd` directly around the
systemd mask. Ordinary sessions retain the vendor activation definitions.
Fedora's dbus-broker drop-in uses a fixed native launcher in the service domain.
It clears startup configuration before same-domain exec, allowing libsystemd to
read the runtime-directory environment without a SELinux `noatsecure` grant.
The role policy permits I/O on inherited Unix-stream descriptors, including
journal sockets; it does not add execution routes. Only the manager receives
Fedora's object-identity constraint attribute for vendor-labelled runtime sockets.
Confined domains may acquire names on the service-domain user bus; name
acquisition against unrelated system-bus service labels is not granted.
The account also has a nologin shell. Broker, D-Bus and Polkit authorization
continue to own data access and parent approval; execution confinement grants
no additional broker authority.

Current GDM admission requires a verified live confined manager and matching
required material/completed source receipts. Required-material drift can require
reboot; configuration does not kill or replace the manager. Completed generations
stay until reboot so live executable mounts remain valid. Preparation permits
four generations per boot, 32,768 directory entries and 512 MiB of copied input
per generation; only owned incomplete preparations are reclaimed under the
exclusive lock. These are current implementation limits, not acceptance criteria
for the replacement architecture. Installed engineering checks remain separate
from usable public entry on both platforms.

### Retained material activation and recovery

The production [fresh transaction](../../tools/kiosk_fresh_startup.h) runs in
the `systemd-user` PAM executor; the
[retained transaction](../../tools/kiosk_retained_startup.h) runs in GDM's PAM
caller. They now separate required material from a realized ambient layout.
The [preparation service](../../tools/kiosk_preparation_service.py) measures
current account, attestation and material; native independently verifies the
measurement and realized mounts. This code is implemented. Host composition and
older bootstrap evidence do not establish final installed entry qualification
for the current composition on either platform.

Fresh startup constructs and publishes independent copies and native realization
receipts, attaches the private read-only `/usr`, completes owned staging cleanup
and applies MAC. Retained entry acquires the verified manager's actual mounted
source through pinned unit/process/namespace identities and source receipts,
clones that source and constructs an invocation-private projection. It does not
rewrite the manager's source record or allocate another completed generation.
The original manager and sources are rechecked before final MAC. A surviving
source pin, disk receipt or saved numeric PID cannot authorize admission after
manager exit or replacement.

Current required material includes code, policy, configuration, units and native
privilege inputs, but also exact cosmetic assets, fonts and translation
catalogues. The latter coupling and ambient sibling enumeration are current
availability limitations. The [implementation baseline](../Kiosk-Session-Confinement-Plan.md#implementation-baseline)
and [scope reconciliation](../Kiosk-Session-Confinement-Plan.md#scope-reconciliation)
replace the old task-numbered future design. They do not loosen runtime code or
executable tests.

Configuration retains shared-admission/exclusive-preparation ordering and never
starts, stops or replaces a live manager. Required drift currently needs
successful configuration plus the existing reboot boundary; partial unpack is
not adopted by reboot alone. Exact restoration may retry unchanged live material
only through a fresh complete admission. Private host lookup descriptors retain
the original `/usr` after attachment, so required-input checks cannot accidentally
read the overmounted kiosk view.

Publication and refusal recovery cover identity-owned incomplete records and
recorded invocation mounts under the preparation lock. Completed generations,
foreign/replaced state and live manager identities are not cleanup targets.
Ready publication before a future manager exec does not prove a live manager;
failed final MAC/exec supplies no admission credit. The PAM admission lease
outlives preparation ownership. See [current view and trust boundaries](Kiosk-Confinement.md#current-private-views-and-retained-admission)
and the [prospective target](../Kiosk-Session-Confinement-Plan.md#target-design) for the
separate replacement lifecycle. No automatic manager renewal has shipped as a
result of this replanning.

### Prospective configuration and activation recovery

The R01/R02-era mechanisms below are historical design analysis. The current
[session-confinement plan](../Kiosk-Session-Confinement-Plan.md#target-design) instead
starts from the pinned v1.3 confinement slice and retains main's other features.
Do not import private graph, transaction, clock or recovery protocols from this
section as mandatory dependencies. C01/C06 select actual bounded mechanisms
under the master's usability and deliberate-child-breach rules.

This is the resilience target, not current shipped behavior. R01's
[architecture decisions](Kiosk-Confinement.md#architecture-decisions-required-before-the-entry-proof)
cover configuration and provisioning through visibility repair, quarantine
release, entry, approval, teardown and subsequent entry. A rejection audit
starting only at GDM misses configuration failures that leave the account expired.

R01 also classifies broker startup prerequisites by the enforcement they protect.
Read `Service._start_policy()`, `Broker.refresh_enabled_extensions()`,
`ExtensionManager.set_enabled()` and their complete account/configuration callers.
Distinguish global enforcement failures from another child's unavailable home or
extension activation. R06b implements bounded per-account isolation/recovery so a
healthy selected child can still receive a genuine approved request. Preserve
required enforcement and accurate unavailable-operation reporting for the affected
child; neither silently skipping its enforcement nor disabling the whole broker
without a concrete global dependency satisfies this target. Family E pairs child
A's unavailable home at broker startup with a successful request for healthy
child B, then restores A and verifies recovery. Keep this a finite readiness
repair, not a redesign of every broker failure path.

R01d selects the [configuration ownership decision](#r01d-configuration-and-quarantine-decision)
below. R05a implements visibility, R05b the separate product setup gate and
R08a optional icon degradation. Their decisions contribute to the
[single rejection ledger](Kiosk-Confinement.md#single-decisionrejection-ledger--execution-contribution).

R01 also maps changed inputs to no action, safe owned renewal, session renewal
or a justified reboot. Retaining the old manager is not a requirement; preserving
live/foreign sessions is. Identify what actual enforcement cannot safely activate
without reboot rather than carrying forward every current classification.
Use one declared end-to-end entry/recovery deadline, including readiness of the
form and authentication path; retries cannot restart that budget. R03/R04
validate the proposed budget against representative observations. Human time
entering parent credentials is separate. A successful unit start alone is not
readiness, and genuine approval still needs a public proof.

### R01e readiness and activation decision

**Selected, prospective design; review only.** One native lifecycle transaction
owns admission, infrastructure reuse/renewal and recovery on both platforms. Its
fixed unprivileged controller operates only the admitted form/agent generations;
the broker owns per-child operational readiness and approval authority. These
are parts of one transaction, not competing lifecycle writers. R02a supplies the
thin runnable route, R06a completes infrastructure recovery, R06b isolates child
readiness and R08b supplies native-language fallback. The
[R01 integrated review](Kiosk-Confinement.md#r01-integrated-admission-contract)
composes these decisions. No runtime behavior or acceptance changes here.

#### Audited readiness path and prerequisite classes

[Service construction and registration](../../broker/oh_no_parent_control/service.py)
currently run `production_dependencies → _compose_broker → _start_policy` before
`main.on_bus_acquired` calls `register`. `Broker.__init__` only composes adapters
and locks. `_start_policy` first calls `AccountsService.sync_execution_policy`,
then `Broker.refresh_enabled_extensions`, attempts cap cleanup, installs signal
subscriptions and starts periodic reconciliation. Any uncaught construction or
registration error ends startup with failure; a bus-name owner or successful
systemd job alone is therefore insufficient evidence of operational readiness.
Diagnostics-only registration deliberately skips policy and is not request-ready.

| Prerequisite / current source | Protected operation and selected failure boundary |
| --- | --- |
| Configuration, migration exclusion, account/caller identities and bus object registration; `Service`, `Broker._load_config`, package launcher | Shared authority: without valid configuration, known roles and a serving broker, no grant or management mutation. Preserve migration/reboot exclusions and read-only diagnostics where safe. Retry only a demonstrated transient service/transport failure. |
| `AccountsService._sync_execution_policy` in [adapters.py](../../broker/oh_no_parent_control/adapters.py) | Shared aggregate native enforcement: reads live filters and root-owned wildcard preferences for discovered accounts, then validates/reconciles the aggregate. A failure to establish that aggregate is global for policy mutations; do not replace it with an empty/partial success. Existing explicitly isolated rule-rendering warnings retain the [application contract](Applications.md#live-filter-and-execution-rules). An unavailable home is not itself this failure: policy preferences do not live in that home. |
| `Broker.refresh_enabled_extensions` in [core.py](../../broker/oh_no_parent_control/core.py) | Per-child countdown/lock integration: current code loops eligible enabled children, loads preferences and calls `set_enabled(..., recover_global_switch=True)`. The first exception is wrapped as `BackendFailure`, aborting registration and preventing healthy B's discovery/request too. R06b removes that cross-child dependency, not the requirement to enforce A's saved policy. |
| `ExtensionManager.set_enabled` in [extension_manager.py](../../broker/oh_no_parent_control/extension_manager.py) | Verifies account/home and shared installed payload, reads enabled/disabled/global-switch settings, then uses live Shell or an offline private bus. Live enable checks configured **and active** state; offline enable verifies durable settings for next login. Subcommands have individual 10-second timeouts; these do not currently form an aggregate budget. Missing/unavailable A home, unsafe A runtime bus, dconf or A activation/rollback failure affects A. Missing shared payload/schema/tool or broken shared service must be classified by its actual failed operation, never guessed from the wrapper error. |
| `Broker.set_parent_control` and extension rollback | Enabling/disabling is an administrator mutation with setting verification, AccountsService writes, preference save and rollback. Per-child startup isolation must not turn a failed toggle/rollback into success or project new policy for another child. Recovery of saved enablement must serialize with changes for that child and reread the desired state. |
| `clear_live_session_runtime_caps` and diagnostic/rescan observations | Cap cleanup is already best-effort at startup; a failed observation is not proof of missing confinement. Preserve its cause and existing enforcement. Signal/rescan machinery needed to maintain live policy must still start; diagnostic timing/export failure cannot gate requests. |
| Form `_preferences_saved → KioskAgentLocale.prepare → _agent_prepared → RequestAccess` | Current [agent helper](../../kiosk/oh_no_parent_control_kiosk/agent_locale.py) discovers locales with a five-second command, rejects C-only results before queueing, writes an environment and waits up to 30 seconds for `RestartUnit`/matching `JobRemoved`. The [form](../../kiosk/oh_no_parent_control_kiosk/main.py) warms it while idle, retries required preparation and reports errors without dispatch. Job success caches presentation, not Polkit registration. R08b removes the translation veto while retaining operational identity/association checks. |

R06b must finish shared enforcement reconciliation before admitting mutations,
but collect each eligible child's extension outcome independently. Store bounded
in-memory readiness keyed by verified account identity and current desired-policy
revision, not a home pathname or cached UID alone. A failed account remains
discoverable with an accurate unavailable-operation result; never delete it from
managed discovery, clear its saved enablement, relax its filters/limits/grants,
or report its extension as active. Block new approval and enforcement-changing
operations for A until their required A integration is verified; unrelated
read-only discovery and healthy B's operations continue. Do not apply this new
gate to the existing control-disabled kiosk API as an accidental policy change;
classify the operation's actual required enforcement under the Broker contract.

Attempt each child's refresh once without letting A consume B's readiness
budget: use bounded workers with per-child serialization, cancel/settle each
owned helper before another for that child, and keep the D-Bus loop responsive.
Retry a transient affected-child failure at most once in the current recovery
transaction, within the shared remaining budget. Recovery is triggered by a
new public operation for that child after its dependency returns; no unbounded
poll/restart loop. Revalidate account eligibility, policy revision and home/bus
authority before retry and before publishing ready. Offline settings prove only
next-login configuration; a live Shell requires the existing active-state check.
An uncertain rollback leaves A unavailable, never marked repaired. Preserve
existing A policy and the live activation/rollback checks; this work cannot
declare a live session safely enforced merely because settings were saved.
There is no existing broker safety action that repairs a live session's absent
countdown/lock extension: PAM checks future authentication, not ongoing desktop
use. R01 bounds R06b's isolation change to the unavailable-home-at-startup control
below, with no live A session. For an already live affected child, retain the
existing verified activation/rollback attempt and an unavailable result if it
fails; do not claim restored enforcement, grant access or introduce a new
session-kill policy. A demonstrated live enforcement loss remains a product
failure requiring its concrete repair before that history can pass. It is not a
new supported degraded state or a reason to fail healthy B's independent request.

Finite R06b/R09b3 control: make enabled child A's home unavailable **before broker
startup**, with no live A desktop/session, retain the first A cause, enter the
station and genuinely approve
healthy enabled B. A cannot receive a false successful enforcement/approval
result. Restore A, retry its public operation, verify its saved policy, live
activation when applicable and genuine approval without restarting B or erasing
either child's state. Pair this with a permanent aggregate/backend failure:
no policy-mutating readiness, bounded unavailable result and safe retry/exit;
restoring the actual shared prerequisite permits a fresh request. Registration
or an error-only form is not the B-success control. This finite change neither
isolates arbitrary corrupt aggregate policy nor redesigns all broker failures.

#### Lifecycle ownership, states and renewal

The native owner serializes against admission, configuration, activation and
recovery under the existing protected lock/lease ordering. It records boot,
account identity, transaction nonce, phase, deadline, renewal-used bit, exact
manager `InvocationID`/process-start identity and live pidfd, bus owner and owned
objects. Broker/controller/visit pins follow the
[approval association](Broker.md#visit-requester-and-agent-association). Records
are protected recovery authority, not frontend tokens or automatic diagnostic
payloads. No saved PID, ready file or unit name alone authorizes mutation.

| State | Entry evidence and permitted next action |
| --- | --- |
| **fresh** | No prior owned infrastructure or unresolved transaction, required setup verified. Claim serialization, record intent before allocating, then prepare. |
| **preparing** | Exactly one owned startup with the original budget. Await required manager/private bus/confinement/form and agent startup; do not publish ready from exec/job success. Repeated callbacks join this transaction without allocating again. |
| **ready** | Healthy owned infrastructure, serving policy-ready broker and usable form for a healthy selected child; agent generation pinned and startup completed. Authentication remains provisional until the genuine native exchange below; neither this state nor a marker proves registration. With no live visit, infrastructure may be reused after identity/activation revalidation. |
| **in-use** | One exact admitted live logind session/visit owns the controller/form/agent globally across seats. Freeze relevant infrastructure and agent generation through the Broker's cancellation/effect-admission boundary. Exit/switch invalidates the visit; drain old work before returning infrastructure to ready or beginning a new activation. |
| **failed** | Failed required operation, deadline exhaustion or unknown ownership; retain first cause and cleanup result. No unrestricted fallback, automatic replay of an approval or immediate fresh retry loop. A deliberate later Retry starts a new transaction only after prior work is settled. |
| **recovering** | One recorded renewal of proven owned stale/failed infrastructure, with no owning public visit or admitted commit still draining. Close admission, settle old work, retire only exact owned state, then prepare once under the original budget. Failed renewal returns failed. |

Healthy reuse checks the selected boundary and actual consumers, not old `/usr`
identity or cosmetic bytes. Every activation still creates new visit/form/agent
generations. A new competing login waits for normal release; it never attaches
to an existing form or prompt. Only returning to the **same** admitted logind
session may reattach to its healthy physical infrastructure after old requests
drain, with fresh visit authority as R01c requires. On expiry return to sign-in
with already-open/retry. Preserve a healthy other-seat session, foreign manager,
changed identity or ambiguous ownership even if a process looks stale.

For renewal, subscribe to systemd/logind ownership and session changes before
reading, then reread under admission serialization. Correlate sessions to the
exact kiosk account and distinguish manager bookkeeping from public graphical,
TTY and SSH sessions; an all-host session count is not a public-visit witness.
Closing public sessions remain occupied until their owned teardown drains. The
current caller's opening admission may proceed only before its public execution
and with no older owner. Never use global `TerminateUser`, a blanket UID signal,
global failed-state reset, or change linger/logind policy.

First request the finite `oh-no-parent-control-quiesce.target` on the **pinned
manager's unique bus connection**, subscribing before dispatch and correlating
its exact successful `JobRemoved` result. This target drains the owned session
units while retaining that manager and its private bus. Its finite GNOME stop
paths cannot indirectly restart or stop the bus. Then dispatch conventional
`StartUnit('exit.target', 'replace-irreversibly')` to that same unique owner.
Final exit can close the bus before its own `JobRemoved`; its dispatch and the
quiesce result are separate receipts. Do not invent a final job success from
disconnect or process exit. Do not use `Manager.Exit`: that is the immediate
forced-exit primitive, not the orderly service shutdown used here. This follows
systemd 259's [exit command dispatch](https://github.com/systemd/systemd/blob/v259/src/systemctl/systemctl-start-special.c)
and [manager method implementation](https://github.com/systemd/systemd/blob/v259/src/core/dbus-manager.c).
If its bus is unavailable, native recovery
may send SIGTERM through the already verified manager pidfd: systemd user
managers start `exit.target` on SIGTERM. Do not send a name-addressed stop/restart
to a possibly replaced `user@UID` invocation. Wait for that invocation, its
recorded services and PAM teardown to end, retaining the original outer
`user@UID.service` InvocationID even after MainPID becomes zero. Final drain
requires that exact manager pidfd to end, the unchanged outer invocation to
become inactive/failed with an empty original cgroup, and the matching native
manager PAM teardown receipt. An already ended pinned owner needs no signal;
neither its PID nor a broker drain reply alone is a teardown receipt. If these
receipts do not drain in time, preserve
the unresolved owner and fail safely, without escalating to a guessed-process
kill. Recheck no public owner/replacement before new startup. This uses
[systemd's manager API](https://www.freedesktop.org/software/systemd/man/259/org.freedesktop.systemd1.html),
[user-manager signal semantics](https://www.freedesktop.org/software/systemd/man/259/systemd.html#SIGTERM)
and [logind session identities](https://www.freedesktop.org/software/systemd/man/259/org.freedesktop.login1.html);
R02a must include the protected exit target/teardown in its finite graph.
These public APIs provide observations and shutdown, not an atomic
compare-and-stop by unit invocation; serialization plus connection/pidfd pins
is required to preserve replacements.

Publish recovery phase/ownership before destructive steps and retain the
renewal-used bit through interruption. A successor may finish only matching
owned teardown/publication, preserving the original cause and deadline; it cannot
adopt a replacement or reset the renewal allowance. After reboot old monotonic
deadlines cannot authorize work: validate current setup and start a new entry,
recovering only proven leftover objects. Missing/changed recovery authority means
preserve/conflict, not sweep. Release locks needed by a draining PAM callback
before waiting for that callback, while keeping the admission fence and durable
recovery ownership; R02a must prove this ordering without deadlock. Cleanup may
outlive admission only to settle recorded owned resources; it cannot admit a
late form or mint a new entry budget.

#### One measured entry and recovery budget

Select **180 seconds of cumulative machine work** from the first native kiosk
authentication/account admission. PAM, native owner, controller and broker share
one remaining budget: callbacks, helpers, bus/service waits, configuration-lock
contention, locale fallback and the one renewal cannot start fresh clocks.
Cap each automatic subcall by that remainder. A usable form may pause the clock
only while it awaits explicit human selection/submission with no automatic work
pending. Charge automatic preparation even while the form is visible; concurrent
helpers consume elapsed wall time once. Carry the remainder into the first real
request; an idle form earns no new agent-startup allowance.

**R01 observable-boundary revision:** the stock MATE agent/Polkit API exposes no
visible-prompt notification to this broker. `RestartUnit`, a running agent and a
pending `CheckAuthorization` do not establish that a prompt exists. Enforcing a
deadline through that unseen boundary could cancel a parent already typing;
calling all of that interval human waiting would conceal missing readiness.
Therefore production enforces the 180-second deadline through usable form,
bounded owned agent startup and dispatch of the genuine native check. An
unfulfilled returned challenge may retry only within that same remainder, under
the original visit/agent pins. Expiry before a dispatch/retry cancels and settles
owned work; denial, dismissal and approval remain terminal.

Each dispatched native exchange retains the existing user-driven authentication
contract without a new idle timeout. While it is pending, visit/sender/agent/
service loss still cancels it; a late result cannot revive it. Its pending time
is recorded as **native exchange, prompt not observable**, not human waiting,
successful registration or request readiness. A hung but still owned exchange
may require the public prompt Cancel or session exit; neither a pending call nor
the production handoff qualifies availability. Do not introduce a custom agent,
password collector, agent-list API, log-based readiness or synthetic password
check. This is a deliberate runtime observability limit, not an assertion that
the stock API enforces a visible-prompt deadline.

Installed acceptance keeps the stronger **180-second admission-to-visible-prompt
machine-time bound**, independently observed through the public form and native
prompt. Pause only the union of observed quiescent human-selection intervals;
automatic work and dispatch-to-prompt latency count. The actual prompt ends this
measurement and parent credential-entry time is separate. R02 registers these
observations; R03/R04 require form/prompt in budget and genuine approval for fresh
entry, healthy reuse and stale renewal. A missing/late prompt fails availability,
even if the production exchange is still pending; safe cancellation, restoration
and a fresh approved request must follow. Host jobs cannot supply this evidence.
Record admission, form, dispatch, prompt and terminal/recovery monotonic times,
human intervals, remaining budget, wall time and first cause.

180 seconds is a design bound, **not an observed performance claim**. It includes
the existing longest 120-second trust wait rather than summing helper clocks;
the broker unit's startup timeout does not implement it. The retained failed
Ubuntu case 293 (report `20261020T015724Z-9595ee55`, exact member in the
[retained accepted bundle](../../output/test-runs/host/plans/eef8d83fd673614a6f0e83adad07b9c3981f98c1618cb827f4a2bf6bd84b72a2/accepted-evidence.json))
took about 8.2 minutes including roughly 295 seconds of snapshot
preparation and a 161-second failed test; it produced no usable form or prompt,
so supplies no successful entry latency. R02 refines history scheduling from
actual registered inputs; R03/R04 validate this bound without silently increasing
timeouts. Later R06/R09 include interrupted renewal, contention, dependency
restart and permanent loss. Subsequent healthy requests retain the transaction
contract; infrastructure loss requires explicit recovery and fresh authentication.

Pre-GDM package configuration has no login admission clock yet. Its required
setup/owned repair uses one separately recorded 180-second machine-work budget
for that configuration invocation, excluding package download/build time and
explicit administrator decisions. No nested setter/restart/recovery extends it;
expiry retains the closed configuration gate and first cause for a later explicit
retry. A later login starts its own single entry budget. If login waits for an
already running configuration, that wait consumes the login remainder too; it
cannot restart or take over configuration. Gate release proves required setup,
not the later public form/prompt result.

#### Changed-input activation decisions

The current [classifier](../../packaging/package_activation.py) and
[postinst](../../packaging/lifecycle/postinst.in) retain their shipped semantics:
`activation_for/changed_impacts` compare installed manifests; configuration may
restart the broker, then reset the verified kiosk's failed manager unit, and
retain comparison records on failure. This is not automatic stale-manager
renewal. The following is the replacement classification for R05, using the
same finite manifest mechanism, not a runtime whole-host digest inventory.

| Changed input | Selected activation and exact limit |
| --- | --- |
| Unrelated packages/host siblings, cosmetic assets, native translation availability or optional feature failure | **No admission action.** Apply presentation defaults on next use; running UI may retain cached artwork/text until reopened. No manager renewal/reboot or exact-material veto. |
| Nonresident provisioning/diagnostic helpers; monitored Polkit rules/actions | **No resident restart solely for these bytes.** Next invocation/request consumes them under existing authority. A real change to a completed required check must revalidate that check; classify its effects, not just the filename. |
| Broker code, contract/unit and aggregate rule inputs | **Owned process renewal** (`process-restart` in the current manifest): reload required service configuration and reconcile actual policy. Cancel/drain unadmitted checks under R01c; an admitted original commit must settle before planned replacement. Unexpected loss never replays it. Form retries freshly against the new owner; no machine reboot solely for broker code. |
| Kiosk-only manager/unit graph, private bus configuration, fixed launchers and protected entrypoint snapshots | **Owned infrastructure renewal** at next safe entry, only after the owned visit/commit and PAM teardown drain. A live visit keeps its valid pinned payload; incompatible/security-critical changes fence new admission until activation completes. Do not hot-reexec into mixed graphs, preserve an exact old manager forever or terminate a foreign/live owner to activate. |
| Shared request form/common UI, agent locale launcher, GNOME Kiosk/session payload and Shell-only child extension | **Session renewal** for resident consumers; newly opened processes load new code. Close/drain owned old form/agent connections first, use a fresh visit/request and preserve vendor privilege paths. Ordinary child sessions renew by normal logout/login, never a forced cross-account logout. Shared files take the union of their consumers' requirements. |
| Compatible AccountsService update with visibility drift | R05a's **one owned capability-based repair**, then public read-back/entry. Coordinate its service restart outside active dependent transactions; no exact version veto or reboot solely for cache visibility. Simulation remains separate from an actual dependency-update history. |
| Other relevant distro library/service updates | Consume trusted installed inputs by their actual residency and public activation needs: next process, kiosk-owned renewal or normal session renewal. Do not snapshot every distro file or infer reboot from a version/digest change. R09c names the actual changed dependency and its loaded-state evidence. |
| PAM already loaded in GDM/ordinary processes, MAC transition/boot ordering, fapolicyd backend requiring display-manager restart, or resident ordinary-user Wellbeing manager helper | **Reboot only when the required old enforcement/resident code cannot safely drain through owned kiosk/session renewal.** Preserve ordinary desktops; current same-boot trust-backend deferral is a concrete example. Record which loaded policy/process cannot activate, its required effect and the post-boot witness. A PAM/login-helper filename alone no longer justifies blanket reboot; retained old GDM PAM code or a shared enforcement boundary does. |

Keep successfully configured inputs and pending activation distinct. Neither
reboot nor successful account-gate release repairs incomplete package setup.
Preserve product-specific reboot exclusions until justified activation; unrelated
packages' markers do not block kiosk requests. R05 updates classifier/tests and
the [publishing activation owner](../Publishing.md#package-update-activation)
only after the new route passes R03/R04. R09c and final F receipts bind actual
changed inputs, activation, fresh/reused public entry, approval and restoration.
No current manifest assertion is changed by this design review.

### R01d configuration and quarantine decision

**Selected, prospective design; review only.** Keep the fixed-account
AccountsService start-pre adapter, but select it by the representation and public
behavior it actually needs, not daemon/RPM version identity. Move temporary
configuration quarantine out of native account expiry into a durable
product-owned native admission gate. Keep native expiry and effective
administrator policy authoritative. Optional icon work has no vote on setup
completion. These choices implement nothing and claim no installed acceptance;
the [R01 integrated review](Kiosk-Confinement.md#r01-integrated-admission-contract)
composes this decision with authentication and readiness.

#### Audited configuration path

[Postinst](../../packaging/lifecycle/postinst.in) uses `set -e`. For an existing
owned account it calls `configure_account_access()` before migration or other
configuration; both platform account templates create a new account with expiry
day 1. Creation precedes both the expiry journal and UID marker, so interruption
there leaves an identity the next configure refuses as unowned. Reconfiguration
also currently deletes the existing password, which can erase an administrator's
later credential lock. [Provisioning](../../tools/provision.py) validates UID/home/admin groups,
writes machine configuration and bus policy, then resolves the AccountsService
object, repairs/caches visibility, assigns the icon, disables kiosk time limits
and verifies session routing. Icon lookup, malformed icon metadata or the setter
can currently abort before required time-limit/routing work. Required package
integration, PAM, services and final confinement installation must then succeed
before `--release-account`. Later broker activation/reset-failed errors can fail
configuration after that release; account release alone is no readiness receipt.
R01e owns that later readiness/activation boundary.

The current v1 expiry record contains only version, UID, original expiry and
`quarantined`/`releasing` phase. Its lock serializes product callers, not ordinary
administrator account tools. Retry accepts native expiry 1 or the captured value;
release writes the captured value and deletes the record after readback. Thus a
later administrator write of 1 can be erased. A matching value, inode timestamp,
phase, private journal or successful `usermod` readback supplies no missing writer
provenance. Preserve current tests/evidence as historical until their allocated
implementation tasks explicitly adapt these mechanism assertions.

#### Visibility capability and schema contract — R05a

Use public `FindUserById`, `CacheUser` for fresh state and typed property
readbacks. Required results are the exact owned UID's `SystemAccount=false`,
`Saved=true`, `Session=oh-no-parent-control`, `SessionType=wayland` and disabled
kiosk `LimitType`, with verification after necessary setters. Preserve an already
correct retained account without setters or a daemon restart. A method/property
failure is a concrete capability failure; an unfamiliar version string is not.

Retained hidden state needs the narrow adapter because current `CacheUser` does
not durably repair it. Accept only the recognized UTF-8 key-file representation
with one unambiguous `[User]` group and at most one `SystemAccount=true|false`
key. Recognized omission of that optional key permits insertion at the validated
group boundary, as in the current adapter. Check the key-file grammar as well as
the target locator; duplicate target groups/keys, NUL, malformed syntax or an
unknown classification representation receive no private-cache write. Unknown
unrelated keys/groups are preserved verbatim and are not an incompatibility.
Fresh state without a cache uses public `CacheUser`, not fabricated private
metadata. Never force a save through icon/session changes just to rewrite a cache.

Retain fixed UID/home/non-administrator ownership checks, pinned no-follow
directories/files, bounded input, metadata/xattr/SELinux preservation and the
single transaction slot with exact before/after/metadata identities. Repair only
at the serialized systemd start-pre boundary with the old daemon gone; recover
an owned interrupted slot before deciding that no write is needed. Patch only
the recognized boolean bytes or insert the omitted key at that boundary.
No version command or RPM package spelling grants
or withholds write authority. Start/restart once for the retained repair and
verify both durable false with no unfinished transaction and public visible/saved
state after reload. A successful file patch alone is insufficient. If this fails,
preserve metadata and the first cause, then finish within R01e's shared budget;
no restart loop, cache deletion or `UncacheUser` fallback. Start-pre refusal stays
nonfatal to AccountsService for ordinary users. Only failed required kiosk results
can fail kiosk setup; a clean public/durable account needs no repair capability.

#### Separate configuration gate and expiry authority — R05b

Use a fixed root-private durable configuration record, read directly by the
native kiosk prerequisite before vendor auth/account work and before either
GDM or `systemd-user` opens a new kiosk session. This is an additional product
setup condition, never an authentication success or replacement account policy.
It does not apply to ordinary accounts or parent Polkit handles. Reuse the
admission/lifecycle lock and handle-owned lease model; configuration cannot
modify a live/competing visit. Wait within the shared budget, preserve that visit
and report a conflict if it cannot drain. Teardown remains possible while the
gate is closed. Do not reuse or clear removal's independent denial marker.

The bounded record has its own schema version, transaction nonce, reserved
identity/UID binding, captured prior native expiry (including no-expiry), and
`creating`, `configuring` or `ready` phase. Pin root-owned private paths and a
regular singly linked record, atomically publish and fsync record and parent;
serialize transitions and revalidate the same nonce/identity before publication.
The record is product state; native shadow expiry, credential locks and
administrator PAM access rules are not. No shadow write is part of closing or
releasing this new quarantine. The captured expiry remains in force without
restoration writes; a later administrator change, even to day 1 or the captured
value, remains in force too. Do not re-delete a password during retry; R01b's
locked/nonempty-credential denial remains effective.

For a fresh identity, first install and verify the native gate on effective
kiosk PAM paths, then publish a reserved-name `creating` record while the account
is absent, before the native account tool creates it. This is a setup-only
bootstrap phase in the maintained confinement installer: it uses the packaged
native module and reserved name, without requiring a UID, provision-generated
machine configuration, AccountsService or completed MAC setup. Install the
prerequisite before vendor auth/account/session callbacks for both GDM and
`systemd-user`; keep ordinary branches unchanged. Journal and verify effective
PAM publication before creation, and retain it through final full integration.
The current installer runs near postinst's end; R05b adds this early phase,
not an early claim of final readiness.

Reserve unused UID/GID values and fresh credential defaults in the intent. Use
native unique-UID creation with a temporary GECOS ownership nonce written with
that UID/name, no temporary expiry and an initially empty credential. The name
is denied even before a UID marker exists. Native name/UID/GID collisions are
not adopted. Disable native home creation: prepare an empty home in a recorded,
root-private adjacent staging directory, with its nonce and inode bound before
publishing it at the reserved home using a no-replace rename. Retry identifies
either location by that same inode/record, rather than trusting an unrecorded
root-owned partial home. Preserve substituted paths and existing homes. After
ownership transfer, home-local work runs with dropped credentials.

Native creation is not a multi-file transaction. Upstream
[`useradd` publication ordering](https://github.com/shadow-maint/shadow/blob/4.19.0/src/useradd.c)
commits passwd before shadow/group records and creates the home later; the
creation nonce alone therefore proves neither credential nor group completion.
Select a fixed-account **absent-only creation completion** helper for that gap,
not a retry of password deletion or a general account editor. It uses the public
libc [shadow entry and locking APIs](https://www.man7.org/linux/man-pages/man3/getspnam.3.html),
[group entry API](https://www.man7.org/linux/man-pages/man3/putgrent.3.html) and
[gshadow API](https://www.gnu.org/software/gnulib/manual/html_node/gshadow_002eh.html).
Hold lifecycle exclusion first, then the native account-database lock through
identity/absence readback and publication. Shadow-utils
[`commonio_lock`](https://github.com/shadow-maint/shadow/blob/4.19.0/lib/commonio.c)
uses `lckpwdf()` for normal non-prefix builds with that libc capability. R05b
must verify the actual Ubuntu/Fedora tools share this lock; a product-only flock
or precheck followed by `usermod` does not serialize administrator changes.

| Interrupted fresh creation state | Owned completion and policy limit |
| --- | --- |
| Name/UID absent and no conflicting native records | Retry the recorded native creation once; retain the gate and intent until all required readbacks pass. |
| Exact creating nonce/name/UID/GID and expected passwd shadow locator (`x`), but a shadow/group/gshadow entry is absent | Under the shared native lock, revalidate the fresh unbound intent, local identity and all target slots. Append only absent entries from that intent, with an empty initial user credential, no account expiry and a locked group credential. Never initialize an existing or previously bound account this way. |
| Any target native entry already exists | Preserve every field, including passwd-level or shadow credential locks, expiry, group password and membership. Verify required identity/non-administrator properties; allow effective PAM policy to decide access. A present denial is never converted into missing setup. |
| Ambiguous/malformed target entry, foreign name/UID/GID, unexpected passwd credential field, substituted home or changed transaction | Preserve it and diagnose the actual ownership/setup failure; do not delete/recreate the account, reset a field or manufacture a new intent. Restoration must precede a permitted control. |

The helper pins local database paths without symlinks, distinguishes an absent
entry from a read/parse error, rejects duplicate target rows and preserves all
unrelated bytes, metadata, ACLs/xattrs and SELinux labels. Serialize only the new
entry with the public API into an atomic, fsynced replacement; read back before
releasing the native lock. It never runs a native tool that reacquires that lock.
Each absent-only publication is independently retryable: a crash after rename
finds a present row and performs no credential/expiry write. Administrator tools
that commit first are observed; those that commit afterward remain authoritative.
This does not claim serialization with direct edits that ignore native locks.
R05b must exercise both ordered administrator-lock/expiry races and every native
record publication on both supported tool implementations before accepting this
route; upstream source is its design basis, not installed qualification.

Publish permanent UID/transaction ownership only after native records and the
recorded home are complete, before replacing the temporary comment with the
display name. Retry after comment replacement requires those permanent records.
After binding, even a matching creation nonce authorizes no credential creation
or clearing. Bind verified UID/home/ownership durably before exposing visibility.
If the gate cannot be established, do not create/expose the account or change
credentials. This closes creation-to-marker recovery without treating native
account creation as atomic or inferring ownership from name/home equality.

For an existing owned identity, durably change `ready` to `configuring` before
any setup mutation. First upgrade from a shipped account without the new record
may publish its first closed `configuring` record only under lifecycle exclusion
after validating the existing package UID marker, home and non-administrator
identity; revalidate the same identity before ready publication. This bootstrap
grants no readiness and changes no native expiry or credential. Missing, unsafe,
unknown, mismatched or non-ready state denies
new kiosk entry, including after reboot; absence is not permission. Required
setup comprises validated account/config/bus policy, visible/saved dedicated
session state and kiosk limits, effective policy-preserving PAM, and the actual
required confinement/enforcement integration. Home markers still run with dropped
credentials. Optional artwork is excluded. After required setup succeeds, publish
`ready` for that same transaction under the lifecycle lock. A crash before
publication stays closed; a crash after it is idempotently ready. Retry reconciles
only proven owned state once within the shared recovery budget, rechecking the
required results before publication. Do not infer readiness merely from a phase,
erase later policy, or manufacture a new transaction to adopt foreign state.
Keep one bounded current receipt, not an image/generation framework.

Legacy v1 expiry transactions cannot retrospectively prove a same-value writer.
Migrate under the new closed gate and preserve native expiry without writing it.
If current expiry already equals the captured prior value, retirement needs no
native write; effective policy, including an expired prior value, still applies.
If they differ (especially current=1 and captured=no-expiry), retain the v1 record
and captured value and report the ownership ambiguity. A bounded retry cannot
infer whether that is product residue or a later administrator denial. Explicit
administrator reconciliation of native expiry is required before retiring that
legacy record. Provide a maintained explicit administrator acknowledgement bound
to that exact v1 record, owned identity and current native expiry; revalidate those
inputs under the lifecycle lock before retirement. The administrator may retain
the current denial or select another expiry through normal account management;
acknowledgement never requires restoring the captured prior value and itself
changes no shadow field. Changed inputs invalidate acknowledgement. This outcome
is not automatic availability recovery and receives no success
credit. No timestamp/audit-log guess or blanket install authorization resolves
this missing historical fact. New gate transactions eliminate this ambiguity and
must automatically recover after interrupted required setup without administrator
intervention. R05b must implement the legacy transition and keep removal's
identity-checked cleanup consistent; never drop the gate while an owned account
survives removal.

#### Optional icon and finite proof allocation — R08a

Catch only icon-specific lookup/parse/assignment failures at the optional operation
boundary, retain a sanitized first cause and continue required setup. Make at
most one bounded assignment attempt; the greeter's display default is the fallback
without another `SetIconFile`, empty-icon setter, file copy or successful icon
read requirement. Preserve a retained custom icon. Failure in later required
visibility, routing, limits or enforcement remains a setup failure, even after
an icon error. Required result verification decides gate release, not whether
the optional step returned success.

R05a's finite host controls pair compatible unfamiliar-version repair with actual
unsupported/ambiguous representation, missing capability, transaction interruption
and byte/metadata/ordinary-user preservation. R05b covers early gate bootstrap,
every partial native-record/home/ownership publication and native-lock ordering,
configuration and ready publication, owned retry, required-setup failure,
prior/later expiry and same-value administrator writes, credential denial,
legacy ambiguity and foreign state. R08a pairs failed icon get/parse/set with
successful required setup/release and with required failure that stays closed.
All must preserve the original cause. R09a/R09c1 compose installed B/F histories;
R10/R11 prove public visibility, passwordless usable entry, genuine approval and
restoration on Ubuntu and Fedora. Compatible-version simulation is not a real
dependency update. The ledger owns rejection/control details; these selectors
remain unimplemented until their owning tasks register them. R01d creates no
runtime resources, changes no executable expectations and needs no package build.

### Package activation and session renewal

Saved-data migration completes before provisioning and package-update activation.
See [Data migration](Data-Migration.md#package-lifecycle) for broker exclusion,
package ordering, and failure/retry behavior.

Package activation is selected from a generated digest manifest. Depending on
the installed file that changed, an update needs no action, a broker restart, a
new child/kiosk session, or a reboot for boot integration or resident user-manager
recovery code. See
[Package update](../Publishing.md#package-update-activation) for the classification rules.
The native PAM module, confinement policy/preparation, fixed launchers, PAM
profiles and login-routing integration require `reboot`: a graphical logout
alone may retain the old user manager and its private executable generation.
New request windows and Parent processes load their installed code when opened;
session renewal is needed for a running Shell or dedicated kiosk session to
consume the corresponding updated payload. Configuration does not forcibly
log users out to achieve that renewal.

After successful configuration, a failed user-manager unit belonging to the
verified package-created kiosk UID has its failed state reset. Earlier denied
admissions can leave that unit loaded without a manager or user bus; native
package triggers would otherwise attempt to reload or contact it. This recovery
uses the system manager, preserves journal diagnostics and leaves running kiosk
managers alone. A state-query or reset error fails configuration and retains
activation records for retry; earlier configuration failures leave the failed
unit untouched. Both Ubuntu and Fedora use this shared completion step. The
installed interruption/retry check also verifies exclusion from native trigger
enumeration and a kiosk-scoped wildcard reload; both targets passed this history
in the [accepted installation receipts](../../tests/README.md#core-installation-and-runtime-compatibility).

Successful configuration prints a green completion line. If this package has
requested a reboot, the helper then prints
`*** REBOOT REQUIRED: reboot before using the kiosk session. ***` as the last
output: bold red on a capable terminal, and plain text when stderr is not a
terminal or `TERM` is dumb. The packaged dpkg hook defers that output until
configuration and triggers finish so later APT/dpkg lines cannot follow it.
For Fedora, this is the final nonempty product-scriptlet line; DNF's framing
and transaction messages may follow it, as described in the
[Fedora output contract](../Fedora-Packaging.md#fedora-lifecycle).

Every broker entry uses the shared
[product reboot detector](../../common/oh_no_parent_control_ui/reboot.py) before
constructing policy adapters. In addition to the child-trust guard, it recognizes
Ubuntu's `/run/reboot-required` only when `/run/reboot-required.pkgs` includes
the exact `oh-no-parent-control` package, and Fedora's product-owned
`/run/oh-no-parent-control-reboot-required` marker. Fresh installation, upgrade
and same-boot reconfiguration therefore select the same diagnostics-only mode
and modal in Parent, Child App and kiosk. Absent requests and unrelated packages
leave normal startup available. Requests expire with `/run` at reboot; no new
persistent state or marker is introduced. The launcher's early child-trust gate
still verifies import safety independently of the frontend reboot guard.

## Installed layout

The optional Wellbeing banner service is packaged as
`/usr/lib/systemd/user/oh-no-parent-control-wellbeing.service`, with a package-owned
`default.target.wants` link and session D-Bus activation file. It runs as the
session user, starts independently of Shell extension activation to recover an
unfinished settings override, and restarts on failure. Its GJS modules and
recovery schema ship in the extension payload. A lingering user manager or
another login can keep this helper alive through GNOME logout/login. Its resident
service module, shared lease/window module, recovery schema (source and compiled),
unit, startup link and D-Bus activation file therefore require a reboot to
guarantee update activation. The Shell-only suppression client still requires
session renewal. Package configuration uses the existing reboot notification
and does not restart users' managers or force logout.
GJS is an explicit runtime dependency on both distributions. It has no readiness
dependency from the broker, desktop or enforcement services. See
[suppression lifecycle](Screen-Time.md#native-wellbeing-banner-suppression).

The [Fedora packaging adapter](../Fedora-Packaging.md#fedora-lifecycle) supplies
`wheel`, `/etc/gdm`, native x86_64 PAM paths and authselect integration for local
Workstation 44 testing. The lifecycle templates and installation map below are
shared; Fedora live acceptance remains pending.

```text
/usr/bin/oh-no-parent-control                         kiosk/overlay launcher
/usr/bin/oh-no-parent-control-child                   child overlay launcher
/usr/bin/oh-no-parent-control-parent                  parent launcher
/usr/libexec/oh-no-parent-control-broker              broker launcher
/usr/libexec/oh-no-parent-control-query-usage         child/approver-scoped usage read helper
/usr/libexec/oh-no-parent-control-migrate-state       saved-data migration runner
/usr/libexec/oh-no-parent-control-session-limit-check PAM limit-state gate
/usr/libexec/oh-no-parent-control-login-check         kiosk PAM service/routing gate
/usr/libexec/oh-no-parent-control-execution-policy-{ready,probe}
/usr/libexec/oh-no-parent-control-uninstall            verified removal helper
/usr/libexec/oh-no-parent-control-{provision,package-activation}
/usr/libexec/oh-no-parent-control-package-notice       deferred package completion output
/etc/dpkg/dpkg.cfg.d/99-oh-no-parent-control-notice    generated dpkg completion hook
/usr/lib/oh-no-parent-control/{broker,parent,kiosk,common}/
/usr/share/gnome-shell/extensions/oh-no-parent-control@tech.puffyslippers.com/
                                                       immutable extension payload
/etc/oh-no-parent-control/config.json                  private machine configuration
/var/lib/oh-no-parent-control/preferences/             authoritative child records
/var/log/oh-no-parent-control/<component>/             daily component logs
/etc/fapolicyd/rules.d/89-oh-no-parent-control.rules   generated UID-scoped denies
/etc/fapolicyd/rules.d/01-oh-no-parent-control-deny.rules
                                                       early concrete UID-scoped denies
/usr/lib/systemd/system/{fapolicyd,display-manager}.service.d/
                                                       boot readiness ordering
```

Current source logs are structured `YYYY-MM-DD.events` files with bounded
rotations and incident files. Readable dated `.log` files are generated in
diagnostic exports; retained legacy `.log` files are not imported by that pipeline.

The [Makefile](../../Makefile) is the complete installation map, including
assets, the compiled PAM module, integration templates, and package helpers.
Its production module lists exclude tests, preview launchers and fixtures,
preview artwork, and developer documentation (including all of `docs/`).
The binary retains runtime assets, user command manuals, legal notices and
Debian metadata. Development previews load their fixtures only when requested;
the child preview supplies a separate entry point in its disposable directory.
Removing developer files requires no new system integration or saved-data
migration; existing path classifications continue to select update activation.

`oh-no-parent-control-child` selects the shared launcher's child-overlay mode,
equivalent to `oh-no-parent-control --child-overlay`. It is available from a
terminal or the desktop Run dialog. Additional arguments pass through the same
parser. The command becomes available on package installation/update; it requires
no service restart or saved-data migration.

## Related design

- For changed system integration, follow [Package update](../Publishing.md#package-update-activation).
- For removal/purge ownership and rollback, read [Package removal](Package-Removal.md).
- For PAM policy, read [expiry enforcement](Screen-Time.md#countdown-and-expiry-enforcement); for extension activation, read [screen-time enablement](Screen-Time.md#screen-time-model).
