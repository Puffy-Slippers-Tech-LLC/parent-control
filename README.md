# Oh No! Parent Control

Oh No! Parent Control is a dedicated GNOME Kiosk request station for granting
additional session time to a selected local standard account. Eligible
accounts are discovered at runtime, including accounts created after installation. A
root-owned broker validates the shared duration and hard/soft app policy, performs one
interactive Polkit check for the real kiosk caller, and updates the supported
AccountsService parental-control properties.

The child’s in-session GNOME Shell extension remains a supported companion
path. The kiosk application is a normal GTK 4/libadwaita program and never
imports Shell APIs or handles passwords. The two paths intentionally keep their
authorization and policy stores separate.

## Development

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

The existing child-session extension remains independently buildable:

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
account is required. See [docs/Deployment.md](docs/Deployment.md) for the
deployment and runtime account-discovery details.
