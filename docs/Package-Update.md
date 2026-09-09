# Package update activation

Each Debian package contains `/usr/share/oh-no-parent-control/package-activation.json`. The file lists each activation-relevant installed file, its SHA-256 digest, and the action needed when that file changes. It is generated from the staged package by `tools/package_activation.py`; it must never be edited by hand.

During an APT install or upgrade, `debian/preinst` records that an activation comparison is pending and, for upgrades, saves the manifest from the currently installed package. After unpacking, `debian/postinst` compares that saved manifest with the new one. Added, changed, and removed files all count. The pending marker prevents a later `dpkg --configure` retry from inventing a reboot requirement. A package without a prior manifest is treated as a first installation and requires a reboot, which is conservative for migrations from releases that predate this mechanism.

## Activation levels

| Level | Package action | Reboot marker |
| --- | --- | --- |
| `none` | Nothing | No |
| `process-restart` | Reload systemd and D-Bus, then restart the broker | No |
| `session-renewal` | Reassert child activation through broker startup; the next child or kiosk GNOME session uses updated payloads | No |
| `reboot` | Normal Ubuntu reboot-required marker is created | Yes |

`reboot` is reserved for changes to PAM or login-manager/pre-session integration. These must activate at a clean login-manager boundary. This includes the kiosk login-check helper as well as the PAM profiles which invoke it. The system GNOME extension payload, kiosk session units, and GNOME session descriptors are `session-renewal`, because an existing graphical session cannot load their replacement safely but the machine does not need to reboot. For this activation level, the package starts the broker, which reasserts extension activation for enabled managed children; a new Shell session loads the updated immutable system payload. Broker code, its systemd unit, and its D-Bus contract are `process-restart`. The packaged fapolicyd fallback rule is also `process-restart`: broker startup regenerates the UID-scoped deny rules and asks fapolicyd to load the resulting aggregate before the broker begins serving requests. Polkit action definitions and administrator-selection rules are `none` because polkitd monitors both directories and loads their changes for subsequent authorization requests. A request-flow update can still require a broker restart or session renewal through its changed broker and child payload files. The display-manager/fapolicyd readiness gate and its executable canary are also `reboot`: their fail-closed ordering can only be guaranteed when the login manager starts in the same boot transaction after fapolicyd becomes ready.

The uninstall helper is `none`: it is invoked only while removing the package
and cannot affect an installed update. It is therefore intentionally excluded
from the activation digest manifest even though it is shipped in the package.
The maintainer-script removal guard and execution-policy baseline likewise
activate in the install/remove lifecycle (`none`); they add no running service,
session integration, or saved-preference schema change.

The package never clears `/run/reboot-required` or removes package names from `/run/reboot-required.pkgs`: either may have been created by Ubuntu or another package. It adds its own package name when this package's comparison finds the `reboot` level or after package removal.

For that level, `postinst` invokes Ubuntu's
`/usr/share/update-notifier/notify-reboot-required` package hook with this
package's name. The runtime dependencies include `update-notifier` (the desktop
indicator) and `update-notifier-common` (the hook). Ubuntu owns the restart icon,
tooltip, notification timing, and user notification preferences. The package
does not launch a desktop process from the root maintainer script. If the hook
defers marker creation for Livepatch, `postinst` still records the reboot needed
by our PAM/display-manager integration. Configuration retries avoid duplicate
entries and retain the activation comparison if the hook fails.
`make installdeb` locates the built `.deb` and hands off to ordinary
`apt install <deb>`; `make uninstalldeb` runs `apt remove oh-no-parent-control`.
Both use only the package payload, installed maintainer scripts, and package
manager integration. They must never add checkout-side setup, cleanup, notices,
or success messages. Installation does not force repair or reinstallation; APT
decides whether the supplied version needs installation just as in production.
APT installation output is deferred until dpkg finishes configuration and
triggers. `preinst` generates the package-owned
`/etc/dpkg/dpkg.cfg.d/99-oh-no-parent-control-notice`, using dpkg's documented
[`post-invoke` hook](https://manpages.debian.org/unstable/dpkg/dpkg.1.en.html#OPTIONS).
APT starts a new dpkg process for configuration after unpacking, so that
process reads the hook even on the first installation. An APT hook shipped
as a conffile would be too late for the already-running APT process; a dpkg
conffile would likewise become available too late during configuration.

After successful configuration, `postinst` calls the packaged
`/usr/libexec/oh-no-parent-control-package-notice --configured`, which queues a
private completion marker in `/run` when a frontend holds the dpkg lock.
The post-invoke hook reads dpkg's public status fields and waits until this
package is installed and no package remains unconfigured, broken, or awaiting
triggers. It consumes the marker and prints the green PASS line, immediately
followed by the kiosk reboot reminder when this package has an outstanding
reboot request. This places both lines after dependency configuration and
triggers for ordinary APT installs, including `make installdeb`. Failed
configuration retries clear stale completion markers; unrelated later
transactions do not repeat a consumed PASS message. Other independently
configured APT hooks can still emit their own output after dpkg returns.

Direct `dpkg --install` may unpack and configure in a single process, which
cannot load its newly generated hook. Without a frontend lock, `postinst`
therefore retains immediate PASS/reboot output. Removal, purge, and aborted
installation remove the generated hook only if its contents still match;
administrator replacements are preserved. The inline hook checks for the
helper before calling it, so removal of the executable payload is harmless.
The notice helper and generated dpkg configuration activate on invocation
(`none`), are excluded from activation digests, and introduce no saved-data
migration. All of this behavior ships in the `.deb`.

This follows [Ubuntu's package reboot-notification guidance](https://discourse.ubuntu.com/t/ubuntu-deb-package-maintainer-scripts-hooks-triggers-tips-tricks/36174).
The notification wiring activates during package configuration (`none`); it
does not itself change the reboot classifications or saved application data.

The broker remains a static, D-Bus-activated unit. Migration stops it even for an
unchanged reinstall, so every successful configuration requests a broker start;
`process-restart` and `session-renewal` instead request a restart to reassert
policy if a client already activated it. The maintainer script consults
`policy-rc.d` before invoking systemd directly, because `deb-systemd-invoke`
skips inactive static units. A policy denial defers activation; a policy error
or service startup failure fails configuration. Activation comparison markers
are retained on failure for a configuration retry. Debhelper's automatic starts
and upgrade restarts are disabled to avoid a second activation attempt.
These maintainer-script changes activate during package configuration (`none`);
they introduce no boot integration or saved-data migration.

## Maintaining classifications

Removal changes PAM and login-manager integration too. `postrm remove` records
the Ubuntu reboot requirement. The packaged
`/etc/apt/apt.conf.d/99zz-oh-no-parent-control-reboot-notice` uses APT's
[documented `DPkg::Post-Invoke` hook](https://manpages.debian.org/unstable/apt/apt.conf.5.en.html)
to print a removal-specific terminal notice after dpkg and its triggers.
It activates on the next APT invocation (`none`), is excluded from activation
digests, requires no data migration,
and is shared by ordinary APT removal and `make uninstalldeb`.
The command is inline so removal of the executable payload cannot break it.
The conffile remains after ordinary remove, reminding on later transactions
until reboot clears the request or purge removes the hook. Direct dpkg
removal uses Ubuntu's reboot markers without this APT terminal notice.
`postrm` uses the update-notifier hook if present, with a direct marker fallback when
the dependency is missing, fails, or defers notification. Retry does not duplicate
the package entry. A later `postrm purge` does not invent another reboot request;
APT purge of an installed package already runs the removal phase first.

The GDM hook template at `usr/share/oh-no-parent-control/gdm-presession` remains
`reboot`. The generated fallback rule's template at
`usr/share/oh-no-parent-control/99-oh-no-parent-control-allow.rules` remains
`process-restart`. The Polkit rule moved to `usr/share/polkit-1/rules.d` remains
`none`. Ownership records, PAM baseline capture, cleanup guards, and the removal
notice activate in the package lifecycle (`none`). They do not change any saved
preference schema and need no data migration. These packaging changes target
clean installations; they do not adopt untracked installations or accounts.

`activation_for()` in `tools/package_activation.py` is the complete, reviewed mapping from installed path to activation level. `ACTIVATION_MANIFEST_PATHS` in the `Makefile` selects the corresponding installed files for hashing. When adding, moving, or removing a packaged integration file, update both and add a focused unit test in `tests/unit/test_package_activation.py`. Classify by the installed path, not its source directory.

For a normal UI or broker update, do not assign `reboot` merely for caution: the manifest comparison must be able to avoid a reboot prompt. Conversely, any new PAM, GDM, or pre-session file must be classified as `reboot` before it ships.

Saved-data migration happens before this activation comparison and has its own retry and failure contract. The migration runner is therefore classified `none`: `postinst` invokes it unconditionally rather than as a later activation action. See [Data migration](SystemDesign/Data-Migration.md#package-lifecycle).
