# Deploy Oh No! Parent Control

Use a clean Ubuntu 26.04 Desktop VM with GNOME 50 and Wayland. Sign in with the
administrator account, open a terminal in the extracted release directory, and
run each step in order.

## 1. Install the software

Install the required packages:

```bash
(
  set -euo pipefail
  sudo apt-get update
  sudo apt-get install -y software-properties-common
  sudo add-apt-repository -y universe
  sudo apt-get update
  sudo apt-get install -y \
    accountsservice \
    dbus-user-session \
    gdm3 \
    gir1.2-adw-1 \
    gir1.2-gtk-4.0 \
    gnome-kiosk \
    libpam-malcontent \
    make \
    malcontent \
    malcontent-gui \
    policykit-1-gnome \
    python3 \
    python3-gi
)
```

Create the accounts. Set the child password when prompted:

```bash
(
  set -euo pipefail

  if ! id -u child >/dev/null 2>&1; then
    sudo adduser --comment "" child
  fi

  if ! id -u oh-no-parent-control >/dev/null 2>&1; then
    sudo adduser \
      --disabled-password \
      --comment "Oh No! Parent Control" \
      --home /home/oh-no-parent-control \
      --shell /bin/bash \
      oh-no-parent-control
  fi

  sudo usermod \
    --comment "Oh No! Parent Control" \
    --home /home/oh-no-parent-control \
    --shell /bin/bash \
    oh-no-parent-control
)
```

Install and configure the application:

```bash
(
  set -euo pipefail

  sudo make install

  sudo systemd-sysusers
  sudo systemctl daemon-reload
  sudo systemctl reload dbus.service
  sudo systemctl enable --now \
    malcontent-timerd.service \
    malcontent-timer-extension-agent.service

  sudo env DEBIAN_FRONTEND=noninteractive pam-auth-update --disable malcontent
  sudo malcontent-client set-session-limits child daily-limit --daily-limit 14400

  sudo install -o root -g root -m 0644 /dev/stdin \
    /usr/share/pam-configs/oh-no-parent-control-child-limits <<'CHILD_PAM'
Name: Oh No Parent Control child session limits
Default: yes
Priority: 1000
Account-Type: Additional
Account:
 [success=1 default=ignore] pam_succeed_if.so quiet user != child
 required pam_malcontent.so
CHILD_PAM

  kiosk_uid="$(id -u oh-no-parent-control)"
  sudo busctl --system call \
    org.freedesktop.Accounts \
    "/org/freedesktop/Accounts/User${kiosk_uid}" \
    org.freedesktop.Accounts.User SetSession s oh-no-parent-control

  sudo install -o root -g root -m 0644 /dev/stdin \
    /etc/polkit-1/rules.d/00-oh-no-parent-control-session.rules <<'POLKIT_RULE'
polkit.addRule(function(action, subject) {
    if (action.id == "org.freedesktop.accounts.change-own-user-data" &&
        subject.user == "oh-no-parent-control")
        return polkit.Result.NO;
});
POLKIT_RULE

  sudo install -d -o root -g root -m 0755 /etc/gdm3/PreSession
  sudo install -o root -g root -m 0755 /dev/stdin \
    /etc/gdm3/PreSession/Default <<'GDM_GATE'
#!/bin/sh
if [ "${USER-}" = "oh-no-parent-control" ] || [ \
   "${LOGNAME-}" = "oh-no-parent-control" ]; then
    [ "${GDMSESSION-}" = "oh-no-parent-control" ] || exit 1
fi
exit 0
GDM_GATE

  sudo install -o root -g root -m 0755 /dev/stdin \
    /usr/local/sbin/oh-no-parent-control-login-check <<'LOGIN_GATE'
#!/bin/sh
if [ "${PAM_USER-}" != "oh-no-parent-control" ]; then
    exit 0
fi

case "${PAM_SERVICE-}" in
    gdm-password|systemd-user) exit 0 ;;
    *) exit 1 ;;
esac
LOGIN_GATE

  sudo install -o root -g root -m 0644 /dev/stdin \
    /usr/share/pam-configs/oh-no-parent-control-kiosk-only <<'KIOSK_PAM'
Name: Oh No Parent Control kiosk-only account
Default: yes
Priority: 1000
Account-Type: Additional
Account:
 required pam_exec.so quiet /usr/local/sbin/oh-no-parent-control-login-check
KIOSK_PAM

  sudo env DEBIAN_FRONTEND=noninteractive \
    pam-auth-update --enable oh-no-parent-control-child-limits
  sudo env DEBIAN_FRONTEND=noninteractive \
    pam-auth-update --enable oh-no-parent-control-kiosk-only

  sudo passwd --delete oh-no-parent-control
  sudo sed -i -E \
    '/^[[:space:]]*(AutomaticLogin|TimedLogin|TimedLoginDelay|AutomaticLoginEnable|TimedLoginEnable)[[:space:]]*=/d' \
    /etc/gdm3/custom.conf
  sudo sed -i \
    '/^[[:space:]]*\[daemon\][[:space:]]*$/a AutomaticLoginEnable=false\nTimedLoginEnable=false' \
    /etc/gdm3/custom.conf
)
```

Reboot:

```bash
sudo reboot
```

## 2. Verify the kiosk login

At the login screen:

1. Select the **Oh No! Parent Control** account.
2. Select **Oh No! Parent Control** from the session menu.
3. Sign in without a password.
4. Select **Return to Login**.
5. Select the **Oh No! Parent Control** account again and try every other
   session in the session menu. Each attempt must return to the login screen.

Sign in to the administrator account and open a terminal in the release
directory.

## 3. Provision the accounts

```bash
(
  set -euo pipefail
  sudo make provision \
    KIOSK_USER=oh-no-parent-control \
    CHILD_USER=child \
    KIOSK_CONFINEMENT_VERIFIED=1
  sudo systemctl daemon-reload
  sudo systemctl reload dbus.service
  sudo systemctl restart accounts-daemon.service
  sudo reboot
)
```

## 4. Complete the deployment check

1. Sign in to the **Oh No! Parent Control** account without a password.
2. Submit a time-only request and approve it with an administrator account.
3. Sign in to `child` and confirm that the additional time is available.
4. Sign out, return to the **Oh No! Parent Control** account, and approve a
   request containing both time and an application profile.
5. Sign in to `child` and confirm that the time and application restrictions
   are active.
6. Sign out, sign in to the **Oh No! Parent Control** account, and select
   **Return to Login**.

Deployment is complete.
