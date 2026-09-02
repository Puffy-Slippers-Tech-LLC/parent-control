# Package update activation

Each Debian package contains
`/usr/share/oh-no-parent-control/package-activation.json`. The file lists each
activation-relevant installed file, its SHA-256 digest, and the action needed
when that file changes. It is generated from the staged package by
`tools/package_activation.py`; it must never be edited by hand.

During an APT install or upgrade, `debian/preinst` records that an activation
comparison is pending and, for upgrades, saves the manifest from the currently
installed package. After unpacking, `debian/postinst` compares that saved
manifest with the new one. Added, changed, and removed files all count. The
pending marker prevents a later `dpkg --configure` retry from inventing a reboot
requirement. A package without a prior manifest is treated as a first
installation and requires a reboot, which is conservative for migrations from
releases that predate this mechanism.

## Activation levels

| Level | Package action | Reboot marker |
| --- | --- | --- |
| `none` | Nothing | No |
| `process-restart` | Reload systemd and D-Bus, then restart the broker | No |
| `session-renewal` | The next child or kiosk GNOME session uses the update | No |
| `reboot` | Normal Ubuntu reboot-required marker is created | Yes |

`reboot` is reserved for changes to PAM or GDM/pre-session integration. These
must activate at a clean login-manager boundary. Extension payloads, kiosk
session units, and GNOME session descriptors are `session-renewal`, because an
existing graphical session cannot load their replacement safely but the machine
does not need to reboot. Broker code, its systemd unit, and its D-Bus contract
are `process-restart`.
The packaged fapolicyd fallback rule is also `process-restart`: broker startup
regenerates the UID-scoped deny rules and asks fapolicyd to load the resulting
aggregate before the broker begins serving requests.

The package never clears `/run/reboot-required` or removes package names from
`/run/reboot-required.pkgs`: either may have been created by Ubuntu or another
package. It only adds its own package name when this package's comparison finds
the `reboot` level.

## Maintaining classifications

`activation_for()` in `tools/package_activation.py` is the complete, reviewed
mapping from installed path to activation level. `ACTIVATION_MANIFEST_PATHS` in
the `Makefile` selects the corresponding installed files for hashing. When
adding, moving, or removing a packaged integration file, update both and add a
focused unit test in `tests/unit/test_package_activation.py`. Classify by the
installed path, not its source directory.

For a normal UI or broker update, do not assign `reboot` merely for caution:
the manifest comparison must be able to avoid a reboot prompt. Conversely, any
new PAM, GDM, or pre-session file must be classified as `reboot` before it ships.

The full-machine `install.sh` uses the same manifest comparison. It therefore
marks a clean installation for reboot, but does not unconditionally mark an
ordinary later deployment.

Saved-data migration happens before this activation comparison and has its own
retry and failure contract. The migration runner is therefore classified
`none`: `postinst` and `install.sh` invoke it unconditionally rather than as a
later activation action. See `Data-Migration.md`.
