# Oh No! Parent Control

GNOME Shell 50 extension which adds requested-duration choices to GNOME's
native parental-controls screen-time shield. It delegates approval and the
temporary grant to Malcontent and Polkit.

Run `make install` to install the extension for the current user, then enable
it with `gnome-extensions enable oh-no-parent-control@tech.puffyslippers.com`. A Shell
restart/log-out is normally required on Wayland. Installation uses only the
files in this folder and does not require it to be a Git repository.

Install Ubuntu's supported PAM account integration as a system prerequisite:

    sudo apt install libpam-malcontent

Without that package, GDM does not ask Malcontent whether a login is allowed,
so login-session extensions and enforcement can become inconsistent when a
restricted session is entered through the greeter.

The extension also uses one system-level Polkit policy for its single combined
screen-time/app-approval prompt. Install (or reinstall) it after updating the
extension with:

    sudo make install-policy

The policy file is installed to `/usr/share/polkit-1/actions/` and must be
present before a combined time-and-app request can be approved. Open the
app-access page from the extension manager's standard gear button to configure
Always Allowed, Hard Blocked, and Soft Blocked choices.

Run `make check` for static JavaScript/patch checks and `make pack` to create a
complete installable extension archive.

See [the GNOME integration note](docs/gnome50-integration.md) and
[the Malcontent integration note](docs/malcontent014-integration.md) for the
locally verified interfaces and limitations. End-to-end approval must be
tested in a booted Ubuntu 26.04 GNOME/GDM VM with a working system bus.
