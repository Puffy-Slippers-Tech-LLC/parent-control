# Oh No! Parent Control

Oh No! Parent Control has three cooperating applications: an administrator
Parent App, a child-session GNOME Shell extension, and a GNOME Kiosk request
station for requesting additional time. Eligible child accounts are discovered
at runtime, including accounts created after installation.

The Parent App lists interactive non-admin users and controls whether the child
extension is installed and enabled for each one. App-filter states and the last
request-menu selection/custom value live in one root-owned per-child record.
The Parent App, extension, and kiosk all access that record through the broker;
there are no separate user-home preference files.

Install the Debian package with:

```sh
sudo apt install oh-no-parent-control
```

## Development

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

Exercise packaging in a disposable directory:

```sh
stage="$(mktemp -d)"
make _install-product-files DESTDIR="$stage"
find "$stage" -type f -print
make uninstall DESTDIR="$stage"
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

On a clean Ubuntu 26.04 Desktop computer, extract the release and run its one
root installer:

```sh
sudo ./install.sh
```

It installs dependencies and product files, creates and confines the kiosk
account, provisions the broker, and validates the installation. It marks the
system as requiring a reboot but does not reboot automatically. No managed
account is required.
