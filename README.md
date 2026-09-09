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
[the threat model](docs/Threat-Model.md) before deploying
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

On a clean Ubuntu Desktop development machine (also the VM host), use the
single setup entry point for dependencies, checks, previews and host tooling:

```sh
./setup.sh
```

Setup is idempotent: rerun it to refresh dependencies, the UI environment,
checkout Git settings, test helpers, graphical AppArmor policies and Codex rules.
It includes the libvirt/QEMU host packages and Debian build prerequisites.
Build and test commands report missing dependencies; setup installs them.

Use `./setup.sh --help` for focused refreshes: `--dependencies-only`,
`--test-tools-only`, or `--codex-rules-only`. The latter installs machine-wide
`pwd` and `git status` approvals, independent of directory/repository, and the
checkout's validated test rules. The same machine-wide file allows ordinary
`rg -n` and `sed -n` reads across any file paths. Restart Codex after rule changes.

Routine setup refreshes, including host dependencies, use a dedicated,
noninteractive Polkit helper. Install its authorization once with
`./setup.sh --bootstrap-tools`; the first installation requires root authority
and may request an administrator password. Repeating bootstrap reuses the
installed grant. Subsequent operations either use that grant or fail with setup
guidance, without opening authentication dialogs. Full setup bootstraps a
missing helper before installing dependencies on a clean machine. Git settings
and the UI virtual environment are configured as the invoking user. Repair of
an existing denied installation requires running `./setup.sh --bootstrap-tools`
from an administrator-authorized root session; denial never triggers an
automatic authentication fallback.

Explicit baseline preparation uses `./setup.sh --prepare-host` on the host,
after `./setup.sh --prepare-vm` inside the source VM; see
[VM prerequisites and recovery](tests/integration/Environment.md). Ordinary
host setup preserves the VM. Scoped modules implement each step; Makefile
preparation aliases delegate to the master. Build and install the Debian
package to deploy the product.

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

See the [test automation guide](docs/Test-Automation.md) for current commands,
the planned four-command interface, and complete-run acceptance criteria.
Today, `make check` runs the non-graphical baseline; `make check-component`
adds GTK, child JavaScript/GJS and nested-Shell components, and
`make check-static` runs the maintained static tools. Run the applicable
[cleanup-safety prerequisites](tests/README.md#cleanup-safety-prerequisites)
before host-integrated tests that terminate processes.

The [test contributor guide](tests/README.md) documents focused selection,
property/contract coverage, private UI environments and artifact locations.
The [installed-system runner guide](tests/integration/README.md) documents
verified package inputs, the existing guarded VM, real reboot and cleanup.
Local previews/component doubles are not customer E2E evidence. The graphical
E2E suite and `make test-*` aliases are still planned, not implemented.

Preview the kiosk UI from the checkout, with representative fixture data and
without a kiosk login, broker, D-Bus calls, Polkit, or account changes:

```sh
make preview-kiosk
```

The preview uses the production GTK window, CSS, artwork, animation, and
flash-synchronized thunder effects. There is no background music. It is
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

Unit tests may isolate Polkit and AccountsService adapters without modifying
real users. Installed-system and customer E2E tests use the guarded existing
Ubuntu VM and the documented outer-only baseline reset contract.

The child-session extension remains independently buildable for development:

```sh
make pack-extension
./setup.sh --install-extension
```

The system installation below installs the extension's Polkit policy.

## Deployment

On a clean Ubuntu 26.04 Desktop computer, build and install the package:

```sh
./setup.sh
make build
make installdeb
```

APT installs runtime dependencies and the package creates and confines the
kiosk account, provisions the broker, and activates system integration. It
marks the system as requiring a reboot when needed, and the Debian package
prints a reboot notice before APT exits. No managed account is required.

To uninstall through the same APT removal flow as the published package:

```sh
make uninstalldeb
```

This runs `sudo apt remove oh-no-parent-control` (`apt remove` when already
root), preserving APT's normal confirmation prompt and the installed package's
removal scripts. Log out of the kiosk session before removal. Saved application
data and logs are retained by this removal flow.

Removal prints a reboot notice; reboot to finish removing the login integration.
For deliberate removal of saved preferences and product logs, use
`sudo apt purge oh-no-parent-control`. Shared dependencies remain managed by APT.
See [the package removal lifecycle](docs/System-Design.md#package-removal-lifecycle)
for ownership and cleanup rules.
