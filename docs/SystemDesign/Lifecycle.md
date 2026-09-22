# Startup, installation, and updates

[System design overview](../System-Design.md)

Read this for broker readiness, boot/login ordering, installed paths,
provisioning, and package activation. Removal has its own focused document.

Implementation: [service.py](../../broker/oh_no_parent_control/service.py), [Makefile](../../Makefile), [preinst](../../debian/preinst), [postinst](../../debian/postinst), [provision.py](../../tools/provision.py), [package_activation.py](../../debian/package_activation.py), [execution_policy_ready.py](../../tools/execution_policy_ready.py).

## Startup, login, and update lifecycle

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

The packaged fapolicyd drop-in keeps the daemon in systemd's `activating` state
until a root-owned canary execution is denied by the live kernel policy. The
display manager requires completed fapolicyd startup, so a managed graphical
login cannot begin while the daemon rebuilds its trust database. Readiness
failure therefore fails closed before the login manager starts.
The display-manager drop-in depends on fapolicyd, not the product broker.
Broker registration failure prevents product operations but is not a separate
GDM startup gate.

The PAM account stack exempts `systemd-user`, the kiosk account, and members
of Ubuntu's `sudo` group from the Malcontent account check.
For other accounts, the public AccountsService `LimitType` helper skips
`pam_malcontent` only when the account is positively confirmed unrestricted;
unknown or malformed state continues through the enforcing module. The kiosk
account is additionally confined to the dedicated GNOME session. The
[login helper](../../tools/oh-no-parent-control-login-check) admits that account
only for `gdm-password` and `systemd-user`; the owned
[GDM hook](../../data/gdm3/PreSession/Default) checks the selected session.
The product Polkit rule denies the station changing its own AccountsService
metadata. These layers complement the kiosk compositor and disabled XDG
autostart files; hiding desktop controls is not the account confinement mechanism.

Saved-data migration completes before provisioning and package-update activation.
See [Data migration](Data-Migration.md#package-lifecycle) for broker exclusion,
package ordering, and failure/retry behavior.

Package activation is selected from a generated digest manifest. Depending on
the installed file that changed, an update needs no action, a broker restart, a
new child/kiosk session, or a reboot at the PAM/display-manager boundary. See
[Package update](../Publishing.md#package-update-activation) for the classification rules.
In particular, replacing the native PAM module alone is `session-renewal`,
whereas changing PAM profiles or login-routing integration is `reboot`.
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

## Installed layout

```text
/usr/bin/oh-no-parent-control                         kiosk/overlay launcher
/usr/bin/oh-no-parent-control-child                   child overlay launcher
/usr/bin/oh-no-parent-control-parent                  parent launcher
/usr/libexec/oh-no-parent-control-broker              broker launcher
/usr/libexec/oh-no-parent-control-query-usage         child/approver-scoped usage read helper
/usr/libexec/oh-no-parent-control-migrate-state       saved-data migration runner
/usr/libexec/oh-no-parent-control-session-limit-check PAM limit-state gate
/usr/libexec/oh-no-parent-control-login-check         kiosk PAM service gate
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
