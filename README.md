# Oh No! Parent Control

Oh No! Parent Control is a dedicated GNOME Kiosk request station for granting
additional session time to a separate, Malcontent-restricted child account. A
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
make install DESTDIR="$stage"
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
sudo make install-extension-policy
```

## Deployment

Follow [docs/Deployment.md](docs/Deployment.md). Deployment is intentionally
fail-closed: provisioning requires the operator to complete the mandatory GDM
session-confinement gate first, then explicitly pass:

```sh
sudo make provision KIOSK_USER=oh-no-request CHILD_USER=child \
  KIOSK_CONFINEMENT_VERIFIED=1
```

The flag records an operator assertion; it does not turn the GDM default
session into an access-control mechanism. If the target distribution cannot
prevent the kiosk UID from choosing a normal desktop, deployment remains
blocked as required by [docs/System-Design.md](docs/System-Design.md).
