# Package removal lifecycle

[System design overview](../System-Design.md)

Read this for APT removal/purge, rollback, package-owned accounts and files,
PAM restoration, execution-policy baselines, and retry behavior.

Implementation: [prerm](../../debian/prerm), [postrm](../../debian/postrm), [postinst](../../debian/postinst), [uninstall.py](../../broker/oh_no_parent_control/uninstall.py), [package_activation.py](../../tools/package_activation.py).

`make installdeb` installs the built Debian package through APT.
`make uninstalldeb` runs `sudo apt remove oh-no-parent-control` (plain `apt`
when root), retaining APT's confirmation and installed maintainer scripts.
The lifecycle targets clean installations: conflicting accounts, hooks, or
fallback rules require administrator resolution and are never adopted or
overwritten.

## Payload and reversible enforcement cleanup

The executables, Python modules, compiled PAM module, GNOME extension, assets,
desktop entries, session descriptors, D-Bus activation files, systemd units,
and drop-ins are dpkg-owned payload. dpkg removes them; debhelper cleans Python
bytecode and reloads systemd.

Debian package removal temporarily masks and stops the broker before changing
enforcement, preventing D-Bus clients from restarting it during removal. While the
packaged code and dependencies are still available, the removal helper finds
the extant accounts named by securely owned preference records and disables the
product extension, clears and verifies `ActiveExtension` before disabling time
limits, clears `DailyLimit`, `LimitType`, and
`AppFilter`, verifies each result, and transactionally removes and reloads the
generated fapolicyd policy. It attempts every managed account before reporting
failure, and package removal stops if any final state cannot be verified.
A mode-`0600` transient snapshot records the exact derived values before the
first write. If `prerm` is aborted, `postinst abort-remove` restores and
verifies that snapshot before releasing the removal mask. Rollback enables and
verifies time limits before restoring a grant, so every intermediate state also
satisfies Malcontent's requirement that an active grant has an enabled limit.
The snapshot is removed after either a successful rollback or successful
package removal.

## PAM and kiosk ownership

Installation uses `pam-auth-update` to enable the product profiles and disable
Malcontent's replacement profile, recording the original Malcontent choice
through debconf's public protocol. Removal restores only that original choice
and never forces replacement of local PAM edits. Product references must be
checked and absent before deleting the PAM module; an unsuccessful check blocks
removal. This follows the [`pam-auth-update` removal guidance](https://manpages.debian.org/testing/libpam-runtime/pam-auth-update.8.en.html).

After dpkg removes the payload, `postrm` removes generated D-Bus and machine
configuration, the product's generated security integrations, transient package
markers, and the dedicated kiosk account only when a root-owned marker proves
that this package created the unchanged account identity. Installation rejects
an existing reserved kiosk account without that ownership record before changing
its credentials or metadata. Existing owned accounts are validated for home
ownership and administrative privileges before reconfiguration or credential
changes; home setup runs as the kiosk user. Removal requires kiosk logout and
an inactive kiosk user service. Cleanup never signals kiosk user processes or
infers process ownership from usernames, environment variables, or host-wide
process scans. The recorded UID, home path and owner, symlinks, and mounts are
validated before deleting the account, its home, and mail. The
public AccountsService `UncacheUser` method clears the package-owned kiosk's
cached icon and session metadata before deleting the account. The
verified package-created home is removed without following symlinks or crossing
mounted filesystems, including files left behind by account deletion. The
ownership marker is retained until cleanup succeeds, allowing safe retries.

## Execution-policy baseline

Before unpacking the first installation, `preinst` saves the original fapolicyd
compiled policy, its backup, and the service's active/enabled state. Removal
rebuilds policy from any remaining administrator rule files. If none remain,
it restores the original compiled policy and undoes the package's service
activation. This explicitly handles fagenrules leaving compiled rules unchanged
when its source directory is empty. Reloads use fapolicyd's supported CLI.
Symlink substitutions are rejected.
The baseline is retained across upgrades and until successful removal.
An upgrade with a missing baseline fails rather than treating the installed
product's enforcement as pre-existing administrator policy. Systemd reloads
the removed display-manager dependency before stopping fapolicyd, so dependency
stop propagation cannot end the desktop session.

## Remove, purge, and retry

After removing its D-Bus activation files, the package releases only its own
temporary mask and clears only its obsolete failed broker unit. Ordinary remove
retains canonical preferences and redacted logs for reinstall. Purge deletes
the product's `/var/lib/oh-no-parent-control` and
`/var/log/oh-no-parent-control` directories. System journals, Ubuntu crash reports,
other packages' state, and reboot markers are not product-owned purge targets.
Purge rejects substituted directory roots and mounted subtrees. Dependencies,
their accounts, usage history, and shared desktop caches remain under their
owning packages' control; removal never performs APT autoremove.
Activation, migration, ownership, and uninstall records are removed only after
successful cleanup. Failed cleanup keeps the records needed for retry; aborted
first unpack removes only its attempt's bookkeeping.

## Reboot notice

Successful removal records Ubuntu's reboot requirement so existing
login-manager/PAM transactions are renewed at the next boot. The packaged
APT `DPkg::Post-Invoke` hook prints
`*** REBOOT REQUIRED: reboot to finish removing Oh No! Parent Control. ***`
after dpkg's triggers as the last printed output, in bold red on a capable
terminal and plain text in redirected output.
`make uninstalldeb` uses this same production APT integration without a
checkout helper. The hook is self-contained because the executable payload
has already been removed. Its APT conffile survives ordinary removal and
reminds on later package transactions while this package's reboot request
is outstanding; purge removes the conffile. Direct dpkg removal records the
Ubuntu reboot requirement without the APT terminal notice.
Removal never forces logout, restarts the desktop, or reboots automatically. It adds
only this package's reboot request, preserving other entries without duplicates;
a later purge does not clear or recreate the request after reboot. The reboot
notifier is optional in `postrm`, when dependencies may already be absent; see
[Debian maintainer-script dependency rules](https://www.debian.org/doc/debian-policy/ch-maintainerscripts.html).

## Generated integration ownership

The generated GDM hook is removed only when it matches the package's ownership copy; an existing
administrator hook blocks installation and a modified hook or substituted
symlink blocks removal before module deletion. A new administrator hook created
after removal survives later purge.
The fallback execution rule uses the same ownership check. Their templates live
under `/usr/share/oh-no-parent-control`, so reinstall recreates these generated
files without relying on dpkg to restore deleted conffiles. Manually deleting a
Debian conffile during ordinary removal preserves its missing state on reinstall;
ownership records and runtime copies avoid resetting administrator conffiles.
See [Debian configuration-file policy](https://www.debian.org/doc/debian-policy/ch-files.html#configuration-files).
The Polkit rule and actions live under `/usr/share/polkit-1` and are removed by
dpkg; polkitd monitors these directories. Administrator rules under `/etc` survive.

## Related design

- For install/update activation and reboot classification, read [Lifecycle](Lifecycle.md) and [Package update](../Package-Update.md).
- For canonical preferences retained by ordinary removal, read [State](State.md).
