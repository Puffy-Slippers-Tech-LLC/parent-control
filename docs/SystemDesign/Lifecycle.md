# Startup, installation, and updates

[System design overview](../System-Design.md)

The package lifecycle owns broker readiness, boot/login ordering, kiosk
provisioning and update activation. Removal is defined in
[Package removal](Package-Removal.md). Implementation:
[service.py](../../broker/oh_no_parent_control/service.py),
[Makefile](../../Makefile), [preinst](../../packaging/lifecycle/preinst.in),
[postinst](../../packaging/lifecycle/postinst.in),
[provision.py](../../tools/provision.py) and
[package_activation.py](../../packaging/package_activation.py).

## Startup, login, and update lifecycle

Checkout installation uses `make install`. Its APT invocation allows five
transient-download retries and uses `APT::Update::Error-Mode=any` so an exhausted
index refresh stops before installation. Package configuration failures are not
retried; machine APT configuration is unchanged.

DEB installation/reinstallation/upgrade requires `ID=ubuntu`, version 26.04 or
newer, from `/etc/os-release` or, only when absent, `/usr/lib/os-release`.
Other/unknown distributions and older releases refuse before changing payload,
state or services. Aborted-upgrade recovery and removal remain available.
This OS gate does not qualify later GNOME versions: the child extension declares
GNOME Shell 50. Fedora's separate packaging target admits Workstation 44/GNOME 50;
[the overview](../System-Design.md) owns release qualification.

### Broker readiness

Construction reconciles current AccountsService filters into fapolicyd, reasserts
the packaged extension for preference-enabled eligible children, and attempts
stale live-session runtime-cap cleanup before registering D-Bus. Shared policy
or extension-dependency failures block readiness. Failed child account/home
validation retains its sanitized diagnostic and leaves that child's
saved controls and live enforcement unchanged while other children continue.
Cap cleanup is best-effort.
[Isolated app-rule omissions](Applications.md#live-filter-and-execution-rules)
permit remaining policy and publish warnings; storage/backend activation failures
remain fatal. Readiness therefore does not certify every saved app rule.

Startup uses live filters plus saved patterns/extension enablement; it does not
replay all saved daily/app choices after removal cleared live state. Reapplying
Parent controls projects retained choices; removed grants are never recreated.

`GetStartupTimings` exposes six role-checked monotonic construction/reconciliation/
cleanup/registration timestamps. Automatic diagnostics record fixed elapsed phases,
not invocation IDs, PIDs, bus names or absolute timestamps. Diagnostic-write
failure does not gate readiness. GDM has no broker-readiness dependency.

### Boot enforcement and recovery

Ubuntu keeps fapolicyd activating until a root-owned canary is denied and exact
packaged child-module trust is live. The display manager requires that readiness,
preventing login while trust rebuilds. Fedora runs the same canary through
`oh-no-parent-control-execution-policy-ready.service`, a 90-second oneshot requiring/
following fapolicyd with `PartOf`. Configuration compiles/reloads before this gate,
including Fedora's early root-canary denial. Separating the Fedora gate preserves
SELinux runtime-directory handling.

A shared fapolicyd drop-in uses `Restart=on-failure`, a five-second delay and five
starts per 300 seconds. Unexpected nonzero exits, signals and timeouts retry;
clean exits and deliberate stops do not. Window expiry alone does not restart a
failed unit, and this is a rate limit rather than a lifetime retry cap. Recovery
does not repair the database or replay failed approvals.

Existing `Requires`/`PartOf` propagation reruns active dependents, potentially
restarting the display manager and ending sessions. Failed/inactive dependents
are not started automatically, so daemon recovery alone need not recover a failed
boot gate/display manager. Live recovery qualification remains pending.
Package installation does not force a running daemon/desktop restart merely to
load changed drop-ins; their activation class is reboot.

### Exact child-module trust

Both packages generate path/size/SHA-256 trust from final staged `.mjs` bytes.
Configuration owns `/etc/fapolicyd/trust.d/oh-no-parent-control.trust` and refreshes
a running daemon before readiness/broker activation. A stopped daemon loads it
at startup. Trust never hashes mutable installed files or grants a whole directory.

For Ubuntu's exact default `debdb` configuration, which omits configuring packages,
the lifecycle enables the file backend and saves the complete original configuration
in owned rollback storage. It refuses to activate pre-existing inactive administrator
trust records. Already file-enabled configurations, including Fedora's, stay unchanged.

Changing a running daemon's backend completes configuration but requests reboot;
restarting its display-manager dependency would end unrelated sessions.
A mode-0600 `/run/oh-no-parent-control-child-trust-reboot` guard selects
[diagnostics-only broker mode](Logging-and-Feedback.md#investigation-coverage):
role-checked logs and kiosk presentation reads remain, policy/session operations
refuse `RebootRequired`. A boot-bound receipt prevents same-boot retry from
mistaking edited configuration for a loaded backend. Legacy records without a
receipt conservatively use this path once. A stopped daemon can start and
acknowledge trust during the same configuration. Reboot expires the guard without
manual configuration retry.

Rollback files, receipt and their directories are flushed before replacing live
backend configuration; its directory is then flushed too. Restoration requires
the owned replacement to be unchanged; local edits block automatic cleanup.

Installation refresh and exact-record confirmation share a 300-second deadline,
allowing Ubuntu's full `debdb` package hashing to finish on cold or busy systems.
Broker and boot readiness retain their 120-second deadline. Each read
runs in a bounded subprocess using liblmdb's public registered read transaction,
not unlocked `--dump-db` output or a journal event. Fresh snapshots retry missing
records. fapolicyd 2.0 publication metadata selects `trust.meta/current` and
`trust.slot_*`; older databases use `trust.db`. Invalid metadata fails closed.

The reader must write only LMDB's reader-table lock file, with read-only database
contents in the broker sandbox. Missing/unwritable locks fail closed rather than
using the unlocked filesystem fallback. An independent Linux open-file-description
read lock on the initialization byte spans environment open through close;
this prevents fanotify-related POSIX lock release from allowing another reader
to reinitialize shared mutexes. Contention yields temporary-unavailable and retries
inside the same deadline; other lock/database/command failures remain fatal.
Both packages depend on liblmdb.

Startup exclusion remains through provisioning, trust wait and configuration retry;
an existing broker is stopped and verified inactive. The direct broker entry also
checks exact trust before importing code, so D-Bus activation cannot bypass it.
The 180-second service startup budget includes the trust wait. Exact database
records do not prove a fresh Shell import or usable UI; a cached failed import
needs a new child session. Configuration never forces logout. Modified owned
trust blocks configuration/removal; removal deletes only owned records and
refreshes a surviving daemon.

### Kiosk provisioning and selected session

The package creates the reserved non-administrative nologin account, publishes its
UID marker, journals original expiry and quarantines configuration before deleting
the password. [Owned migration](#prepared-owned-lifecycle-migration) owns expiry
and recovery; successful native/distro readiness permits release.

The expiry record stores UID, original expiry and phase. Product writers serialize
with each other; unexpected expiry values refuse recovery.

Provisioning verifies account/home/admin-group identity, generates broker/system-bus
configuration, and establishes/readbacks `Session=oh-no-parent-control`,
`SessionType=wayland`, `SystemAccount=false`, `Saved=true`.
Fresh state uses `CacheUser`; already visible/saved state avoids it. Retained hidden
state first uses owned visibility migration at AccountsService start-pre.
Optional icon failures cannot veto routing.

The bounded isolated-Python login helper verifies the reserved account identity;
saved session preferences and routing discovery do not vote on admission. The
native module bounds/reaps the child and rejects the qualified `su-l` route.
Other service names still undergo the account and lease checks.

Native PAM session opening requires successful account authorization on the same
handle, except for the user-manager callback. Both hold shared no-follow
root-owned admission leases through teardown;
exclusive lifecycle/removal, unsafe state or a barrier denies admission. Ordinary
accounts launch no routing helper. The account stack exempts `systemd-user`,
kiosk and administrators from Malcontent; other accounts skip it only when public
AccountsService positively confirms unrestricted limits. Unknown/malformed state
continues through enforcement.

[Distro PAM](../../packaging/distro_pam.py) verifies finite owned blocks using
Ubuntu pam-auth-update or Fedora authselect while preserving opaque vendor policy,
ordinary authentication, administrator denials and time/runtime-cap behavior.
There is no executable inventory/private-view admission mechanism.

The dedicated [session](../../data/gnome-session/sessions/oh-no-parent-control.session)
and [target](../../data/systemd/user/gnome-session@oh-no-parent-control.target.d/session.conf)
use distribution GNOME Session/Kiosk, require the form, want notifications/vendor
MATE agent and exclude the named crash notifier. Form exit uses
[public GNOME logout](../../kiosk/oh_no_parent_control_kiosk/session_logout.py)
with a 750-ms handoff and app-unit shutdown fallback.
Routing preference/nologin alone do not constrain GDM's actual executable;
[confinement](Kiosk-Confinement.md#admission-and-account-integrity) retains route limits.

### Compatibility and recovery boundary

Usable passwordless entry, genuine approval, safe reentry, owned interrupted-state
recovery and live/foreign-session preservation remain required. Unrelated layouts
and optional presentation failures cannot acquire an admission vote. Essential
outages require safe retry/exit with original diagnostics and no unauthorized
grant/unrestricted desktop. Recovery never replays approval; a new request requires
fresh authentication under [Broker lifetime rules](Broker.md#request-lifetime-and-effect-admission).

Aggregate policy reconciliation precedes per-account extension refresh. An
unavailable child's home does not prevent healthy-child kiosk use
or block requests whose authoritative dependencies remain usable. Operations
requiring that integration still refuse. Restoring the dependency and restarting
the broker retries activation for every enabled child; no approval is replayed.
Other activation, command, schema and verification failures retain their startup
refusal.

### Machine work and human pauses

Machine operations own their finite deadlines/retries: trust, routing, locale
preparation and cancellation cleanup have separate limits. There is no shared
entry/configuration/visit clock. Reading, language selection, request decisions
and parent password entry never consume machine-startup time or cause idle logout.
An agent restart or pending Polkit call does not prove a visible prompt.
[Localization](Localization.md#native-authentication-fallback) owns locale fallback limits.

### Package activation and session renewal

[Saved-data migration](Data-Migration.md#package-lifecycle) precedes provisioning
and activation. A generated digest manifest selects no action, process restart,
session renewal or reboot under [package-update rules](../Publishing.md#package-update-activation).
Removed old-manifest members retain their activation impact during comparison.

Native PAM changes require session renewal: new handles load new code while
existing handles retain original leases. Helpers/profiles activate next invocation.
Running Shell/kiosk sessions need renewal for their payload; new windows load
installed code when opened. Configuration never forcibly ends unrelated sessions.

After successful configuration, the verified kiosk UID's failed user-manager unit
is reset through the system manager; running managers are untouched. Query/reset
failure fails configuration and retains retry records; failed configuration does
not perform the reset.

Success prints a completion line. Product-requested reboot is then the final
product notice, terminal-coloured where supported. DEB defers it through triggers;
Fedora transaction framing may follow. Every broker entry uses the shared
[reboot detector](../../common/oh_no_parent_control_ui/reboot.py), recognizing the
child-trust guard, Ubuntu's exact product entry in `reboot-required.pkgs`, or
Fedora's product marker. Unrelated reboot requests do not block startup.
Product requests expire with `/run`; trust import safety is checked independently.

### Prepared owned lifecycle migration

The [migration owner](../../packaging/lifecycle_migration.py), fixed
[entrypoint](../../tools/oh-no-parent-control-kiosk-lifecycle) and distro PAM owner
coordinate configuration/removal. The [renderer](../../packaging/render_lifecycle.py)
embeds pre-unpack capture and post-erase finalization so erased helpers are unnecessary.
The heading preserves its incoming anchor.

The transaction consumes the numeric UID, UID-bound expiry, known legacy/removal
records and a finite capture receipt. Only recorded original/generated/previous/
removal PAM states are accepted; unrelated edits remain untouched and stop work.
Live admissions, kiosk processes and retained executors prevent retirement without
being signalled. Locks/private legacy generations remain until reboot, never swept.
The lifecycle writer may repair safe stale admission-lease permissions to 0600
only after exclusive acquisition and fresh owner, type, single-link and named-inode
checks. It changes the locked descriptor, preserving live/foreign state and strict
legacy-lock validation; native PAM never repairs an existing lease.

1. Verify reserved account, non-administrative UID/home and exact legacy inputs.
   Capture only configuration/backend-policy bytes into private rollback storage.
   A UID/backend/directory/member/hash/inode-bound receipt survives legacy erasure
   and interrupted deletion; foreign/replaced files remain untouched and the
   receipt is erased last. UID mismatch refuses before capture writes.
2. Under exclusive ownership, preserve original expiry, quarantine, record removal,
   publish vendor-module-only kiosk denials and unload old policy. SELinux relabels
   the pinned admission-lock inode for preflight and restores stock label on unload.
   Pre-lease state records a boot boundary requiring reboot; retry cannot reset it.
   Ordinary PAM workers retaining erased code do not alone veto owned retry.
3. Recover only the fixed visibility slot/committed xattr at verified AccountsService
   start-pre, using UID/inode/content/metadata identity. Change only the retained
   SystemAccount boolean; preserve unrelated cache bytes, metadata and accounts.
   A save failure before replacement preserves the original cache and the published
   recovery slot, including when the error is caught. The next daemon start verifies
   that slot, retries the change and removes the recovery state after success.
4. Restore original PAM under quarantine, install replacement integration and invoke
   the real side-effect-free readiness verifier. Recheck state before retiring old
   records and releasing expiry through its retryable phase. A boolean is not a
   readiness witness.
5. Failed post-unpack configuration/legacy recovery keeps quarantine, removal intent
   and journal with vendor-only kiosk denials. Never republish incompatible old
   native-module options that could reject ordinary users. Abort-remove releases
   only a rebuilt baseline with verified native/distro readiness.

Removal uses the same prepared denial, verified account/home deletion and
post-erase finalizer. Retain the UID marker until finalization verifies both name
absence and no UID reassignment, restores owned original PAM and retires records.
Kiosk identity/audit/executor/lease protection remains; an unrelated ordinary
PAM worker alone is not a refusal reason. Purge follows successful integration/
account cleanup under [Package removal](Package-Removal.md). Source retirement
grants no permission to remove installed state or test evidence.

## Installed layout

| Location | Responsibility |
| --- | --- |
| `/usr/bin/oh-no-parent-control{,-child,-parent}` | Request/overlay and Parent entrypoints |
| `/usr/libexec/oh-no-parent-control-*` | Fixed broker, usage, PAM, migration, provisioning, trust and removal helpers |
| `/usr/lib/oh-no-parent-control/{broker,parent,kiosk,common}/` | Product modules |
| `/usr/share/gnome-shell/extensions/oh-no-parent-control@tech.puffyslippers.com/` | Immutable extension and Wellbeing modules |
| `/etc/oh-no-parent-control/config.json` | Private machine configuration |
| `/var/lib/oh-no-parent-control/preferences/` | Authoritative per-user records |
| `/var/log/oh-no-parent-control/<component>/` | Structured events/rotations |
| `/etc/fapolicyd/rules.d/{01-oh-no-parent-control-deny,89-oh-no-parent-control}.rules` | Native policy |
| System/user systemd integration and session files | Readiness, kiosk and helper lifecycle |

The [Makefile](../../Makefile) owns the complete payload map. Runtime assets,
manuals, legal notices and package metadata ship; tests, previews, fixtures and
developer documentation do not. Exports render readable logs from structured
events rather than importing legacy text logs.

The optional Wellbeing service starts independently of extension activation to
recover unfinished overrides, restarts on failure and can survive graphical logout
in a lingering manager. Its resident code/schema/unit/activation requires reboot;
the Shell client needs session renewal. It has no enforcement/readiness dependency.
See [suppression lifecycle](Screen-Time.md#native-wellbeing-banner-suppression).

The child entry selects `--child-overlay` through the shared parser and passes
additional arguments unchanged. Fedora adapts admin group, GDM/PAM paths and
authselect while sharing lifecycle templates and payload ownership.

## Related design

- [Package update](../Publishing.md#package-update-activation): activation classification.
- [Package removal](Package-Removal.md): ownership and rollback.
- [Screen time](Screen-Time.md#countdown-and-expiry-enforcement): PAM and expiry.
