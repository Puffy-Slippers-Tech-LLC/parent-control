# Startup, installation, and updates

[System design overview](../System-Design.md)

Read this for broker readiness, boot/login ordering, installed paths,
provisioning, and package activation. Removal has its own focused document.

Implementation: [service.py](../../broker/oh_no_parent_control/service.py), [Makefile](../../Makefile), [preinst](../../packaging/lifecycle/preinst.in), [postinst](../../packaging/lifecycle/postinst.in), [provision.py](../../tools/provision.py), [package_activation.py](../../packaging/package_activation.py), [execution_policy_ready.py](../../tools/execution_policy_ready.py).

## Startup, login, and update lifecycle

The selected kiosk session/PAM cutover uses the
[owned lifecycle migration](#prepared-owned-lifecycle-migration). C02d/C02e
removed the discarded private runtime and package source; installed legacy state
still follows that migration's ownership and recovery rules.

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
unmounted encrypted home. The current
[compatibility and recovery boundary](#compatibility-and-recovery-boundary)
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
Other accounts and `systemd-user` do not query routing metadata. Both kiosk PAM
services take a shared lifetime lease on the root-owned, no-follow, private-mode
`/run` admission lock; an exclusive lifecycle writer, unsafe lock state or removal
barrier denies admission. GDM session opening also requires a successful account
check on that PAM handle. This lease excludes lifecycle retirement while an
admission is live; it does not serialize competing kiosk logins.

### Kiosk provisioning and selected session

The package lifecycle creates the reserved non-administrative nologin account,
publishes its numeric UID ownership marker, and quarantines configuration with
a UID-bound native-expiry transaction before deleting the password. The original
expiry survives interruption and reboot. Successful distro/native PAM readiness
permits its restoration. [Owned lifecycle migration](#prepared-owned-lifecycle-migration)
owns this transaction and recovery, rather than the provisioner.

Current expiry provenance is limited: the v1 record stores UID, original expiry
and phase, while product callers serialize only with each other. A later
administrator write of expiry day 1 is indistinguishable from the product's
quarantine value; release can overwrite that denial with the recorded original
expiry. Other unexpected values refuse recovery, but neither phase nor matching
readback proves who wrote a matching value. This existing limitation remains a
compatibility/administrator-policy gap for C09 review. Genuine administrator
denial must remain authoritative; retiring the proposed private configuration
gate does not establish that outcome or prescribe its replacement.

[Provisioning](../../tools/provision.py) validates the recorded account, reserved
home and administrative groups. It generates broker configuration and system-bus
policy, then uses public AccountsService operations to establish and read back
`Session=oh-no-parent-control`, `SessionType=wayland`, `SystemAccount=false` and
`Saved=true`. Fresh state uses `CacheUser`; already visible/saved state avoids
that mutation. Retained hidden state must first pass the lifecycle owner's
fixed-account visibility migration at AccountsService's start-pre boundary.
That migration preserves unrelated cache bytes and metadata and has no daemon
or package-version admission predicate. Fresh or empty icons may receive product
artwork, but artwork read/set failure is optional and cannot veto routing.

The login helper checks the dedicated preference during account and session
authorization, and requires PAM `XDG_SESSION_TYPE=wayland` at session opening.
It does not mutate a valid preference or depend on GDM saving its selection
between these callbacks. The helper uses an isolated Python interpreter, bounded noninteractive
system-bus calls and a fixed child environment; the native module bounds and
reaps its helper child. A repaired wrong preference still denies that attempt;
a subsequent login retries against the dedicated default. Failed verification
never becomes successful admission merely because repair was attempted.

The selected [distro PAM owner](../../packaging/distro_pam.py) integrates through
Ubuntu's `pam-auth-update` and Fedora's owned authselect transaction. It verifies
the finite product auth/account blocks and runtime-cap hook while leaving
unrelated vendor modules opaque. Ordinary accounts retain their authentication,
native administrator denials and time policy. The native module retains an
admission lifetime lease for owned lifecycle/removal exclusion; it performs no
private-view construction, executable inventory or MAC-role transition.

The dedicated [session](../../data/gnome-session/sessions/oh-no-parent-control.session)
and [target](../../data/systemd/user/gnome-session@oh-no-parent-control.target.d/session.conf)
use the distribution's GNOME Session and GNOME Kiosk directly. The target requires
the shared request app, wants notifications and the vendor MATE authentication
agent, and excludes the named crash-notifier activation. Form exit uses
[GNOME's public logout protocol](../../kiosk/oh_no_parent_control_kiosk/session_logout.py),
with a bounded 750-ms handoff and the app unit's shutdown fallback. Neither
session startup nor logout uses a private controller/visit protocol.

Saved session preference and a nologin shell do not attest to GDM's next
executable. The removed PreSession hook is not a boundary on GDM 50. Actual
desktop/session selection, TTY, SSH and remote-desktop defenses retain their
[route-review obligations](Kiosk-Confinement.md#admission-and-account-integrity);
host composition alone does not qualify those routes. Local routing diagnostics
remain in [Logging](Logging-and-Feedback.md#kiosk-admission-diagnostics).

### Compatibility and recovery boundary

The [selected confinement baseline](Kiosk-Confinement.md#c02-activated-session-baseline)
and cumulative C02/C03/C04 dispositions replace the removed v1.4 native graph,
private executable images, material/view receipts and prospective R-series
controller design. Historical candidate qualification remains historical in
[its evidence owner](Kiosk-Confinement.md#verification-scope-and-evidence-limits);
it is not current installed acceptance or an alternate execution plan.

The [new confinement acceptance contract](../Kiosk-Session-Confinement-New-Plan.md#acceptance)
requires usable passwordless entry, genuine approval, safe exit/reentry,
owned interrupted-state recovery and preservation of live/foreign sessions.
Unrelated package/layout changes and optional presentation/service failures
cannot acquire an admission vote. A genuine required-service/enforcement outage
must retain safe retry/exit and its original cause without offering an
unrestricted desktop or unauthorized grant. Recovery never replays an approval;
a fresh request requires genuine authentication under
[Broker lifetime rules](Broker.md#request-lifetime-and-effect-admission).

The broker's current global extension-refresh dependency described
[above](#startup-login-and-update-lifecycle) remains a compatibility gap.
`Service._start_policy()` reconciles aggregate execution policy before
`Broker.refresh_enabled_extensions()`; the latter still aborts on a single
enabled child's activation failure. Required shared enforcement must remain
effective, but another child's unavailable home must not unnecessarily prevent
a healthy child's request. The finite unavailable-child/recovery history and
installed qualification remain with the current plan; no per-account isolation
or automatic recovery is claimed here.

### Machine work and human pauses

Bound machine work and retries at the operation that owns them. Current source
has operation-specific limits, including the trust gate, routing helper, locale
preparation and remote cancellation cleanup. It has no shared 180-second entry,
configuration or visit deadline. The retired R-series clock and private lifecycle
transaction are not implementation requirements.

Human time choosing a language, reading a dialog, deciding a request or entering
a parent password never consumes a machine-startup deadline or causes forced
logout. Pending authentication remains user-driven, with lifecycle cancellation
and no new idle timeout. A successful agent restart or pending Polkit call does
not prove a visible prompt; genuine public approval remains the availability
witness. Locale fallback and its current C-only-host limitation belong to
[Localization](Localization.md#native-authentication-fallback), not a
new visit association or countdown.

The following failed-latency record is historical and qualifies no current
entry or deadline. The retained failed
Ubuntu case 293 (report `20261020T015724Z-9595ee55`, exact member in the
[retained accepted bundle](../../output/test-runs/host/plans/eef8d83fd673614a6f0e83adad07b9c3981f98c1618cb827f4a2bf6bd84b72a2/accepted-evidence.json))
took about 8.2 minutes including roughly 295 seconds of snapshot
preparation and a 161-second failed test; it produced no usable form or prompt,
so supplies no successful entry latency.

### Package activation and session renewal

Saved-data migration completes before provisioning and package-update activation.
See [Data migration](Data-Migration.md#package-lifecycle) for broker exclusion,
package ordering, and failure/retry behavior.

Package activation is selected from a generated digest manifest. Depending on
the installed file that changed, an update needs no action, a broker restart, a
new child/kiosk session, or a reboot for boot integration or resident user-manager
recovery code. See
[Package update](../Publishing.md#package-update-activation) for the classification rules.
The rebuilt native PAM module requires `session-renewal`: new PAM handles load
the replacement while existing handles keep their original lifetime lease.
Login and lifecycle helpers and the owned PAM profiles activate on their next
invocation/transaction. Removed old-manifest members retain their original
activation impact, including `reboot` for the disconnected confinement graph;
a graphical logout alone may retain a former user manager
and its private executable generation. The rebuilt session creates no such
generation and package configuration never ends unrelated sessions.
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

### Prepared owned lifecycle migration

The selected [migration module](../../packaging/lifecycle_migration.py), fixed
[entrypoint](../../tools/oh-no-parent-control-kiosk-lifecycle) and
[distro PAM owner](../../packaging/distro_pam.py) replace the former confinement
lifecycle. The shared package templates select them, and
[the renderer](../../packaging/render_lifecycle.py) embeds pre-unpack preparation
and the post-erase finalizer so those phases need no installed helper. The
heading retains its predecessor anchor; C02 activated this composition.
Host composition is not installed update/removal qualification.

The migration consumes the package's numeric kiosk UID marker, UID-bound
configuration-expiry record, schema-1 confinement record and known removal
marker, plus the finite capture receipt described below. It accepts recorded original, generated, previous-publication and removal
PAM states; unrelated edits remain untouched and stop the transaction. It reuses
the existing admission/routing/preparation lock identities and expiry record.
The capture receipt owns only the two retained rollback files and their cleanup;
it is not another runtime admission protocol. Live admissions,
kiosk processes and retained legacy executors prevent retirement without being
signalled. Runtime locks and private executable generations remain until reboot;
this module never sweeps or recursively deletes them.

The atomic runtime/PAM cutover composes these operations:

1. Preserve the package-created UID marker and validate the non-administrative
   reserved account and owned home. Retain the exact old attested configuration
   and MAC policy bytes across unpack until rollback is no longer needed; a new
   file at the old pathname is not a substitute. Pre-unpack capture retains only
   `config.json` and its backend's policy under the private
   `/var/lib/oh-no-parent-control/legacy-kiosk-policy` directory. Missing or
   changed inputs preserve recovery records and refuse the transition.
   The root-private `legacy-kiosk-policy.json` receipt binds one UID/backend,
   the directory identity, the two exact member names, content hashes and inode
   identities. Its capture/ready/retiring phases retain authority across legacy
   state erasure and interrupted member deletion. Changed/replaced files and an
   unexpected other-backend member remain untouched; the receipt is erased last
   after verified directory removal. A changed saved UID refuses before capture
   storage is created or populated.
2. Call `prepare()` before retiring old integration. It checks owned PAM and live
   legacy state, preserves the original native expiry, expires the kiosk account,
   records removal intent, publishes vendor-module-only kiosk denials and unloads
   the old policy. For owned SELinux state, the pinned admission-lock inode
   receives its current policy label before preflight can refuse, including
   recreation and interrupted-relabel retries. Policy unload resets that same
   inode to its stock label. Pre-lease state
   records its first migration boot and must
   complete a reboot before retirement; retry does not reset that boot identity.
   Once this leased transaction has recorded removal under quarantine, an
   ordinary PAM worker retaining the erased native module does not veto retry.
   Exclusive admission ownership, the pre-lease boot boundary and kiosk
   UID/audit/MAC executor checks still apply; no live worker is terminated.
3. Recover retained visibility using `visibility()` at AccountsService's verified
   start-pre boundary. It recovers only the fixed visibility slot or committed
   xattr using the recorded UID, inode, content and metadata digests, then changes
   only the retained `[User] SystemAccount` boolean. Comments, unknown fields,
   groups, custom icons and unrelated xattrs survive. Package/version identity
   supplies no admission vote. Ordinary accounts and their cache are untouched.
4. Call `restore_original_pam()` under native expiry quarantine. Keep the old
   record and removal marker for rollback. Install the replacement account/PAM
   integration and call `commit_migration(real_verifier)` with C02c's real,
   side-effect-free native/distro readiness verifier. It must return `None` only
   after successful verification or raise; a boolean is not a readiness witness.
   The migration rechecks quarantine, saved state and original PAM around that
   call before retiring the old records. Only then call `release_account()`;
   its `releasing` phase makes interrupted expiry restoration retryable, subject
   to the [same-value administrator-expiry limitation](#kiosk-provisioning-and-selected-session).
5. After unpack, failed configuration and legacy-state abort-remove restore
   recorded vendor PAM with vendor-module-only kiosk denials and retain the
   expiry quarantine, removal intent and recovery journal. They never republish
   the old native module options: those would also reject ordinary users under
   the rebuilt module. Ordinary authentication and user-manager startup retain
   their vendor policy while the kiosk remains closed for configuration retry.
   Abort-remove releases only a rebuilt baseline whose real distro/native
   readiness passes. Legacy-state recovery stays quarantined for configuration
   retry, with no second live path.

Removal uses the same prepared denial transaction, followed by verified owned
account/home deletion and `finish_remove()` after payload erasure. Keep the
numeric UID marker until the finalizer succeeds. The finalizer checks absence
of both the reserved name and any reassignment of that UID, restores only owned
original PAM, and retires confinement/removal/expiry records without importing
an erased helper or consuming erased policy files. Its post-erase check retains
kiosk identity, audit/executor and held-lease protection; an unrelated ordinary
PAM worker retaining an erased module is not a reason to refuse finalization.
Purge remains ordered after
successful integration/account cleanup; preferences, logs, Fedora authselect
ownership and all unrelated removal behavior retain their existing owners in
[Package removal](Package-Removal.md).

The explicit package map installs these owners, selects the renderer's one
finalizer slot and preserves the UID marker through it. The selected provisioner,
AccountsService start-pre caller and PAM activation change together. The manifest
comparison includes removed members
from the old manifest and preserves their declared activation impact; do not
drop removed confinement entries before comparing. C02d/C02e removed
unconsumed old provisioning/quarantine/cache adapters, integration/loader and
embedded finalizer source, native/runtime code, generated confinement inputs,
and their build/install/remove wiring. Source deletion grants no installed-state
or test-artifact cleanup authority. Installed update/reentry acceptance remains
with C11c1/C12c1.

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
