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
domain; it has no `init_t` waiting-helper exception. Current-package installed
startup, credential/teardown and active namespace engineering qualification
passed on both targets; [Kiosk confinement](Kiosk-Confinement.md#verification-scope-and-evidence-limits)
records the candidate scope and evidence limits separately from public acceptance.
The intermediate domain can write the inherited `kernel_t` datagram socket used
by systemd's pre-exec handoff timestamp; that object label was measured on Fedora
with dontaudit temporarily disabled. It also has `noatsecure` only for transition
to the private manager, preserving the trusted system executor/PAM environment:
otherwise libsystemd ignores `XDG_RUNTIME_DIR` and the manager exits. Other role
transitions retain secure execution. The earlier bounded live supplemental-policy
probe proved only manager/native-service startup and normal stop. The current
installed qualification above separately proves final-package teardown callbacks
and post-parent-exit denials.
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
Ordinary package unlink/replacement cannot detach these private file mounts.
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

GDM admission requires the running kiosk manager to have the same inventory
generation and enforcing security label. A stale manager requires reboot;
configuration never kills or silently replaces it. Completed generations stay
until reboot so live executable mounts remain valid. Preparation permits at
most four generations per boot, 32,768 directory entries and 512 MiB of
executable/library input per generation;
owned incomplete preparations are reclaimed under the exclusive lock. The
installed engineering matrix in
[system_kiosk_confinement.py](../../tests/integration/system_kiosk_confinement.py)
is separate from public kiosk workflow acceptance. Both Ubuntu and Fedora must
pass their current installed and graphical checks before this boundary is
treated as release-qualified.

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
