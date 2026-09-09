# Startup, installation, and updates

[System design overview](../System-Design.md)

Read this for broker readiness, boot/login ordering, installed paths,
provisioning, and package activation. Removal has its own focused document.

Implementation: [service.py](../../broker/oh_no_parent_control/service.py), [Makefile](../../Makefile), [preinst](../../debian/preinst), [postinst](../../debian/postinst), [provision.py](../../tools/provision.py), [package_activation.py](../../tools/package_activation.py), [execution_policy_ready.py](../../tools/execution_policy_ready.py).

## Startup, login, and update lifecycle

Broker construction first reconciles the discovered accounts' current
AccountsService filters into fapolicyd. It then reasserts the packaged extension's
activation for every
preference-enabled eligible child and attempts to clear stale live-session
runtime caps. Only after those steps does it register the D-Bus object. An
execution-policy reconciliation or extension-activation failure prevents the
service from becoming ready. Clearing stale session caps is best-effort:
unavailable sessions may be skipped, and an exception at this stage is logged
without preventing registration.

The packaged fapolicyd drop-in keeps the daemon in systemd's `activating` state
until a root-owned canary execution is denied by the live kernel policy. The
display manager requires completed fapolicyd startup, so a managed graphical
login cannot begin while the daemon rebuilds its trust database. Readiness
failure therefore fails closed before the login manager starts.

The PAM account stack exempts `systemd-user`, the kiosk account, and members
of Ubuntu's `sudo` group from the Malcontent account check.
For other accounts, the public AccountsService `LimitType` helper skips
`pam_malcontent` only when the account is positively confirmed unrestricted;
unknown or malformed state continues through the enforcing module. The kiosk
account is additionally confined to the dedicated GNOME session.

APT stops the broker and runs the packaged, version-stepped migration framework
before newly installed readers can access
saved preferences. A migration-in-progress marker also prevents systemd from
starting the broker. See [Data migration](../Data-Migration.md) for the schema contract.

Package activation is selected from a generated digest manifest. Depending on
the installed file that changed, an update needs no action, a broker restart, a
new child/kiosk session, or a reboot at the PAM/display-manager boundary. See
[Package update](../Package-Update.md) for the classification rules.

Successful configuration prints a green completion line. If this package has
requested a reboot, the helper then prints
`*** REBOOT REQUIRED: reboot before using the kiosk session. ***` as the last
output: bold red on a capable terminal, and plain text when stderr is not a
terminal or `TERM` is dumb. The packaged dpkg hook defers that output until
configuration and triggers finish so later APT/dpkg lines cannot follow it.

## Installed layout

```text
/usr/bin/oh-no-parent-control                         kiosk/overlay launcher
/usr/bin/oh-no-parent-control-parent                  parent launcher
/usr/libexec/oh-no-parent-control-broker              broker launcher
/usr/libexec/oh-no-parent-control-query-usage         child/approver-scoped usage read helper
/usr/libexec/oh-no-parent-control-migrate-state       saved-data migration runner
/usr/libexec/oh-no-parent-control-session-limit-check PAM limit-state gate
/usr/libexec/oh-no-parent-control-clear-session-runtime-max
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

The [Makefile](../../Makefile) is the complete installation map, including
assets, the compiled PAM module, integration templates, and package helpers.

## Related design

- For changed system integration, follow [Package update](../Package-Update.md).
- For saved-data compatibility, follow [Data migration](../Data-Migration.md).
- For removal/purge ownership and rollback, read [Package removal](Package-Removal.md).
- For PAM policy, read [expiry enforcement](Screen-Time.md#countdown-and-expiry-enforcement); for extension activation, read [screen-time enablement](Screen-Time.md#screen-time-model).
