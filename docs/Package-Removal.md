# Package installation and removal audit

`make installdeb` installs the built Debian package through APT.
`make uninstalldeb` runs `sudo apt remove oh-no-parent-control` (plain `apt`
when root), retaining APT's confirmation and installed maintainer scripts.
Removal requests a reboot to finish renewing PAM and login-manager state; it
never forces a logout, restarts GDM, or reboots automatically.

## Ownership inventory

| Resource | Installation | Removal / purge |
| --- | --- | --- |
| Executables, Python modules, compiled PAM module, GNOME extension, assets, desktop entries, session descriptors, D-Bus activation, systemd units and drop-ins | dpkg-owned payload | dpkg removes these files; debhelper cleans Python bytecode and reloads systemd. |
| Polkit rule and actions | Installed under `/usr/share/polkit-1` | dpkg removes them; polkitd monitors the directories. Administrator rules under `/etc` are not deleted. |
| `/etc/gdm3/PreSession/Default` | Generated from the packaged template, with an ownership copy in package state. A pre-existing hook blocks installation. | Removed only if still identical to the ownership copy. A changed file or symlink blocks removal before module deletion. A new administrator hook created after removal survives later purge. |
| fapolicyd fallback rule | Generated from the packaged template with an ownership copy | Removed with the same ownership checks; reinstall recreates it. |
| fapolicyd generated UID rules and compiled policy | Broker generates product denies; first install records the original compiled policy and activation state | Helper clears product denies while dependencies are present. Remaining administrator rule sources are rebuilt; otherwise the original policy and service activation are restored. Symlink substitutions are rejected. |
| PAM profiles | `pam-auth-update` enables product profiles and disables Malcontent's replacement profile; the original Malcontent choice is captured using debconf's public protocol | Restores only that original profile choice. Refuses removal if product references remain or cannot be checked, rather than removing a still-referenced module. Never forces replacement of local PAM edits. |
| Kiosk identity, home, mail and AccountsService metadata | Only a newly created, package-recorded identity is accepted. Reconfiguration validates the identity and home before changing credentials. Home setup runs as the kiosk user. | Requires kiosk logout. Validates the recorded UID, home path/owner, symlinks and mounts before account deletion. Uncaches metadata through AccountsService and removes the verified home. Keeps the ownership record on failure for retry. |
| Child AccountsService restrictions and extension settings | Broker owns derived product enforcement for managed child records | Removal helper clears and verifies restrictions and disables the live extension. Aborted removal restores its snapshot before releasing the broker mask and starting the broker again. |
| Generated machine configuration and D-Bus policy | Root-owned generated files | Removed with package removal. |
| Activation, migration, ownership and uninstall records | Root-owned package lifecycle state | Removed after successful cleanup. Aborted first unpack removes its attempt's bookkeeping. Failed cleanup retains the records needed to retry. |
| Saved child preferences and product logs | Customer data under `/var/lib/oh-no-parent-control` and `/var/log/oh-no-parent-control` | Normal remove preserves them. Explicit purge removes these product directories, rejecting substituted roots and mounted subtrees. |
| Dependencies, their accounts, state and shared services | APT installs dependencies; their packages own them | Retained under APT's control. The package does not perform autoremove or delete dependency-owned accounts, usage history, system journals, crash reports, or shared desktop caches. |
| Ubuntu reboot markers | Shared operating-system notification state | Adds only this package's request, preserving other entries and avoiding duplicates. Later purge does not clear or recreate a request after reboot. |

## Safety and retry behavior

These rules target clean installations. A reserved account, pre-existing GDM
hook, or conflicting fallback rule requires the administrator to resolve the
conflict; the installer does not adopt or overwrite it. Mounts and changed
identities likewise require resolution before cleanup can complete. Cleanup
never discovers process ownership by username, environment, or a host-wide
process scan and never signals a kiosk user's processes.

Generated integration templates are deliberately outside `/etc`: manually
deleting a Debian conffile on ordinary removal causes its missing state to be
preserved on reinstall. Runtime copies and ownership records give removal and
reinstall an explicit, repeatable lifecycle without resetting administrator
conffiles. See [Debian configuration-file policy](https://www.debian.org/doc/debian-policy/ch-files.html#configuration-files).

PAM references are checked before the package payload disappears, following
[`pam-auth-update` removal guidance](https://manpages.debian.org/testing/libpam-runtime/pam-auth-update.8.en.html).
The reboot notifier is optional in `postrm`, because dependencies may already
be absent at that stage. See [Debian maintainer-script dependency rules](https://www.debian.org/doc/debian-policy/ch-maintainerscripts.html).

## Validation scope

The maintainer-script tests execute shell scripts against temporary filesystems
and fake account/service commands. Regressions cover removal and purge, retry,
aborted removal and first unpack, saved-data retention, symlinks, mounts, changed
identities and hooks, original PAM selections, local PAM edits, reboot notifier
absence/failure/deferral, preservation of other reboot requests, and reinstall.
The staging build checks the real payload and activation manifest without
installing it on the development workstation.

These checks do not replace a disposable Ubuntu VM install → reboot → remove
→ reboot → reinstall → purge acceptance run with real GDM, PAM, AccountsService
and fapolicyd. The audit does not claim that this full VM sequence has passed.
