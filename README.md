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

Preview the kiosk UI from the checkout, with representative fixture data and
without a kiosk login, broker, D-Bus calls, Polkit, or account changes:

```sh
make preview-kiosk
```

The preview uses the production GTK window, CSS, artwork, and animation. It is
resizable, draggable from its content, and intentionally does not enter the
production fullscreen session.
While it is open, saving the kiosk stylesheet or background artwork updates the
window in place; saving kiosk Python source automatically relaunches the preview.

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

The request dialog opens automatically. Selecting a duration and requesting it
updates the indicator locally; it never grants real time or changes an app
filter. Saving child JavaScript, CSS, or request-option data restarts only the
nested preview session.

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
