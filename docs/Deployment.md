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
The kiosk inherits the invoking administrator's desktop language, and GNOME's
first-login setup is completed during installation so the kiosk app opens
directly without language or diagnostics questions.
The required reboot also preserves the invoking administrator's GNOME extension
switch. Ubuntu can classify a slow Shell shutdown as a crash and disable all
extensions; the installer restores the exact pre-reboot switch value once,
before the login screen starts.

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
and kiosk accounts are never offered. The PAM session-limit check likewise
excludes members of Ubuntu's `sudo` administrator group, so administrators
remain unlimited at login and when using `sudo`.

Enabling an account in the Parent App applies its configured daily Malcontent
limit. The limit is an integer from 0 through 1440 minutes; zero uses the
product's grant-only model. An approved request preserves that daily allowance,
applies application filtering, and grants the requested extension after the
same single administrator authentication dialog. Disabling the account makes
it unrestricted and clears the active grant and applied filter while retaining
the selected daily limit for a later re-enable.
