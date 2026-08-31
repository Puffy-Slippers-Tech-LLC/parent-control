# Deploy Oh No! Parent Control

Use a clean Ubuntu 26.04 Desktop computer with GNOME 50 and Wayland. Extract
the release, open a terminal in its directory, and run the installer as root:

```bash
sudo ./install.sh
```

That is the entire setup. The installer installs the operating-system
dependencies and product files, creates and confines the dedicated **Oh No!
Parent Control** kiosk account, provisions its UID-bound policy, validates the
installation, and marks the system as requiring a reboot. It does not reboot
automatically and is safe to run again on an already installed computer.

No managed account is needed before or during installation. After the reboot,
select **Oh No! Parent Control** at the GDM login screen; it signs in without a
password and starts the kiosk app. The kiosk account is restricted to this
session, and automatic and timed login remain disabled.

When convenient, reboot with `sudo systemctl reboot`. The kiosk session must
not be used until after that reboot.

## Runtime account discovery

The kiosk app lists every eligible local standard account. Accounts created
after installation are supported without rerunning setup; select **Refresh
accounts** if the kiosk app was already open. Administrative, system, remote,
and kiosk accounts are never offered.

The first approved request for an unrestricted standard account enables a
zero-second daily Malcontent limit and grants the requested extension. For the
product's grant-only model, an existing daily allowance is also changed to
zero on its first approved request. Limit initialization, application
filtering, and the time grant all happen after the same single administrator
authentication dialog.
