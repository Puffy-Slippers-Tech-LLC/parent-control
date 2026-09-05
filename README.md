# Oh No! Parent Control

Oh No! Parent Control has three cooperating applications: an administrator
Parent App, a child-session GNOME Shell extension, and a GNOME Kiosk request
station for requesting additional time. Eligible child accounts are discovered
at runtime, including accounts created after installation.

The Parent App lists interactive non-admin users and controls whether the
packaged child extension is activated for each one. App-filter states and the last
request-menu selection/custom value live in one root-owned per-child record.
The Parent App, extension, and kiosk all access that record through the broker;
there are no separate user-home preference files.

## License, source, and Malcontent disclosure

Copyright (C) 2026 Puffy Slippers Tech LLC. Oh No! Parent Control is free
software under the GNU General Public License, version 3.0 only. The complete
license is in [LICENSE](LICENSE), and the corresponding source (including the
package build and installation scripts) is this repository:
<https://github.com/Puffy-Slippers-Tech-LLC/parent-control>.

The product interoperates with the separately installed Malcontent service via
documented public D-Bus and AccountsService APIs; it does not include, modify,
or redistribute Malcontent. Malcontent is an LGPL-2.1-or-later operating-system
dependency, with its own notices and source supplied by the distribution. This
product is not affiliated with or endorsed by the Malcontent authors or GNOME.
Read [NOTICE](NOTICE) and
[the integration note](docs/malcontent014-integration.md) before deploying
restrictions: Malcontent is one enforcement component, not a guarantee that
every possible method of use is blocked.
Maintainers should follow [the compliance guide](docs/Compliance.md) for every
release.

Install the Debian package with:

```sh
sudo apt install oh-no-parent-control
```

See [docs/Publishing.md](docs/Publishing.md) for the complete package build and
Launchpad PPA release workflow.

Removing the Debian package disables and verifies all product-derived child
restrictions, removes a dedicated kiosk account created by the package and all
generated system integration, and leaves a pre-existing kiosk account,
canonical child preferences, and redacted product logs available for a later
reinstall or administrator-directed archival.

## Development

On a clean Ubuntu Desktop development machine, install the dependencies for
checks and all three previews:

```sh
./setup.sh
```

This does not install the product or configure accounts, services, or Polkit.
Build and install the Debian package to deploy the product to a machine.

### Restore the publisher OpenPGP key

The release-signing backup is stored outside this repository in
`[GNU-Private-Key-Backup-Folder]` and contains:

- `oh-no-parent-control-private-key.asc`, the passphrase-protected private-key
  export;
- `4449F02C3E57F8215261A57958109B593907EFDE.rev`, the revocation certificate;
- `dot-gnupg.7z`, an encrypted backup of the complete original GnuPG directory.

Keep this folder and its passphrase in protected storage. Never copy any of
these files into the repository. On a clean development machine, run
`./setup.sh` first, then restore the signing key from the portable armored
export:

```sh
GNU_PRIVATE_KEY_BACKUP_FOLDER='[GNU-Private-Key-Backup-Folder]'
SIGNING_KEY_FINGERPRINT='4449F02C3E57F8215261A57958109B593907EFDE'

gpg --import \
    "$GNU_PRIVATE_KEY_BACKUP_FOLDER/oh-no-parent-control-private-key.asc"
install -d -m 700 "$HOME/.gnupg/openpgp-revocs.d"
install -m 600 \
    "$GNU_PRIVATE_KEY_BACKUP_FOLDER/$SIGNING_KEY_FINGERPRINT.rev" \
    "$HOME/.gnupg/openpgp-revocs.d/$SIGNING_KEY_FINGERPRINT.rev"
gpg --list-secret-keys --keyid-format LONG "$SIGNING_KEY_FINGERPRINT"
gpg --fingerprint "$SIGNING_KEY_FINGERPRINT"
```

Verify that the final two commands show the exact fingerprint above and a
`sec` entry. The imported private key retains its existing passphrase. Follow
[docs/Publishing.md](docs/Publishing.md) to configure Git and register the
public key with Launchpad.

`dot-gnupg.7z` is a disaster-recovery alternative to the portable import. It
contains the entire original keyring, so restore it only on a clean machine
where `$HOME/.gnupg` does not exist. Inspect the archive before extraction and
confirm that it contains one top-level `.gnupg/` directory:

```sh
GNU_PRIVATE_KEY_BACKUP_FOLDER='[GNU-Private-Key-Backup-Folder]'

test ! -e "$HOME/.gnupg"
7z l "$GNU_PRIVATE_KEY_BACKUP_FOLDER/dot-gnupg.7z"
7z x "$GNU_PRIVATE_KEY_BACKUP_FOLDER/dot-gnupg.7z" -o"$HOME"
chmod -R go-rwx "$HOME/.gnupg"
gpg --list-secret-keys --keyid-format LONG \
    '4449F02C3E57F8215261A57958109B593907EFDE'
```

Do not use the archive path after importing into an existing keyring: archive
extraction is a whole-directory recovery and can replace newer GnuPG state.

The repository is organized by runtime component:

- `parent/` contains the administrator application.
- `child/` contains the GNOME Shell extension and its extension-specific policy.
- `kiosk/` contains the request-time kiosk application.
- `broker/` contains the privileged shared-preferences and access broker.
- `data/`, `config/`, and `tools/` contain system-wide integration and deployment files.

Run the complete host-safe test suite without installing anything:

```sh
make check
```

The unit and private-D-Bus component suites use pytest. On Ubuntu 26.04,
`setup.sh` installs the reviewed archive versions listed in
`tests/test-tools-ubuntu-26.04.txt`, including `python3-pytest=9.0.2-4` and
`python3-dbusmock=0.38.1-1`, and `flatpak=1.16.6-1`. Run `make check-unit` for unit and contract tests,
or `make check-component` for private-bus, JavaScript (Node and GJS), hermetic
GTK, and isolated GNOME Shell component tests. `make check-child-shell` runs
the GNOME Shell 50 child-extension lifecycle, indicator interaction, and
controlled-source reload component suite.
The latter creates a disposable Wayland compositor, private D-Bus, and private
AT-SPI bus for each test process; it never uses the developer's desktop session.
Each preview captures its complete nested-Shell logs and a PNG through GNOME
Shell's public Screenshot D-Bus interface. Per-run diagnostics stay in the
ignored `artifacts/ui/child-shell/` tree; the most recent successful evidence
is also copied to `artifacts/ui/child-shell/latest/` by scenario. These images
are of the private nested compositor, never the host desktop.
`make check-child-node` runs the platform-neutral child-extension tests with
Node's built-in runner. `make check-child-gjs` runs the GJS adapter tests and
writes LCOV coverage to `artifacts/coverage/gjs-child/coverage.lcov`.
`setup.sh` creates its isolated Dogtail 2.1.0 environment from the hash-pinned
wheel in `tests/ui/requirements.txt` and installs Ubuntu's maintained
`gnome-ponytail-daemon` package for real Wayland runs that need input injection.

`make check-test-fixtures` builds deterministic native and Flatpak enforcement
targets, launches them as the current unprivileged UID, and verifies their
digests. It gives Flatpak an isolated temporary `HOME` and XDG tree, never uses
the developer's user or system Flatpak installation, and removes the whole
temporary tree after the test. To retain a payload for a guarded disposable-VM
test, provide an explicit empty directory beneath `/tmp`:

```sh
make build-test-fixtures OUTPUT_DIR="$(mktemp -d /tmp/onpc-test-fixtures-XXXXXX)/payload"
```

This command only builds an image payload; it does not install an application,
create an account, alter application policy, or start a VM. Later system tests
may copy that payload only after their guest guard has verified a disposable VM.

Preview the kiosk UI from the checkout, with representative fixture data and
without a kiosk login, broker, D-Bus calls, Polkit, or account changes:

```sh
make preview-kiosk
```

The preview uses the production GTK window, CSS, artwork, animation, and looping
soundtrack. It is
resizable, draggable from its content, and intentionally does not enter the
production fullscreen session.
While it is open, saving the kiosk stylesheet or background artwork updates the
window in place; saving kiosk Python source automatically relaunches the preview.

Preview the same GUI as a child-session overlay, with the child selector locked
to the current account:

```sh
make preview-child-overlay
```

Preview the Parent App with in-memory fixture accounts and preferences. This
does not need the broker, system D-Bus, Polkit, an installed package, or any
account changes:

```sh
make preview-parent
```

The parent preview is resizable. Saving its stylesheet updates the window in
place; saving parent Python source automatically relaunches it.

Preview the child extension in a nested GNOME Shell. It loads the checkout
directly with fixture preferences and time remaining—without installation,
broker, system D-Bus writes, Polkit, or account changes:

```sh
make preview-child
```

Clicking the remaining-time notification launches the shared kiosk request GUI
as a fullscreen overlay. Selecting a duration and requesting it updates the
indicator locally; it never grants real time or changes an app filter. Saving
child JavaScript or CSS restarts only the nested preview session.

The interactive wrapper delegates its isolated runtime directories, environment,
Shell command, generation logs, readiness deadline, source-change reload, and
process-group cleanup to `child/preview-orchestration.sh`. Component automation
can source that boundary and provide an observable readiness probe; it must not
duplicate setup or cleanup logic or inspect the developer's desktop settings.
The reload component test changes only its copied extension payload, records the
two observed generations, and leaves the checkout and any developer extension
installation unchanged.

Inspect the built package payload without installing it:

```sh
make build
dpkg-deb --contents output/oh-no-parent-control_*.deb
```

Unit tests use mocked Polkit and AccountsService adapters and never modify real
users. Installation, account provisioning, confinement, and end-to-end tests
belong in a disposable Ubuntu 26.04 VM.

The child-session extension remains independently buildable for development:

```sh
make pack-extension
make install-extension
```

The system installation below installs the extension's Polkit policy.

## Deployment

On a clean Ubuntu 26.04 Desktop computer, build and install the package:

```sh
make build
make installdeb
```

APT installs runtime dependencies and the package creates and confines the
kiosk account, provisions the broker, and activates system integration. It
marks the system as requiring a reboot when needed; `make installdeb` offers an
interactive reboot on a terminal. No managed account is required.
