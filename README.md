# Request More Time

GNOME Shell 50 extension which adds requested-duration choices to GNOME's
native parental-controls screen-time shield. It delegates approval and the
temporary grant to Malcontent and Polkit.

Run `make install` to install the extension for the current user, then enable
it with `gnome-extensions enable request-more-time@example.com`. A Shell
restart/log-out is normally required on Wayland. Installation uses only the
files in this folder and does not require it to be a Git repository.

Run `make check` for static JavaScript/patch checks and `make pack` to create a
complete installable extension archive.

See [the GNOME integration note](docs/gnome50-integration.md) and
[the Malcontent integration note](docs/malcontent014-integration.md) for the
locally verified interfaces and limitations. End-to-end approval must be
tested in a booted Ubuntu 26.04 GNOME/GDM VM with a working system bus.
