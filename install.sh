#!/bin/bash
set -euo pipefail

readonly KIOSK_USER="oh-no-parent-control"
readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

usage() {
    echo "Usage: install.sh"
}

if (( $# > 1 )); then
    usage >&2
    exit 2
fi
case "${1-}" in
    "") ;;
    -h|--help)
        usage
        exit 0
        ;;
    *)
        usage >&2
        exit 2
        ;;
esac

if (( EUID != 0 )); then
    echo "install: run this script as root (for example: sudo ./install.sh)" >&2
    exit 1
fi

if [[ ! -f "$SCRIPT_DIR/Makefile" || ! -f "$SCRIPT_DIR/tools/provision.py" ]]; then
    echo "install: run the installer from a complete release directory" >&2
    exit 1
fi

export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get install -y software-properties-common
add-apt-repository -y universe
apt-get update
apt-get install -y \
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

if ! id -u "$KIOSK_USER" >/dev/null 2>&1; then
    adduser \
        --disabled-password \
        --comment "Oh No! Parent Control" \
        --home "/home/$KIOSK_USER" \
        --shell /bin/bash \
        "$KIOSK_USER"
fi

usermod \
    --comment "Oh No! Parent Control" \
    --home "/home/$KIOSK_USER" \
    --shell /bin/bash \
    "$KIOSK_USER"

# The full-machine installer always targets the canonical system paths. Clear
# inherited Make state so environment variables cannot split file installation
# from the fixed paths used by provisioning and validation below.
env -u MAKEFLAGS -u MFLAGS \
    make --no-print-directory -C "$SCRIPT_DIR" _install-product-files \
    DESTDIR= \
    PREFIX=/usr \
    SYSCONFDIR=/etc \
    LIBEXECDIR=/usr/libexec \
    DATADIR=/usr/share \
    SYSTEMD_SYSTEM_DIR=/usr/lib/systemd/system \
    SYSTEMD_USER_DIR=/usr/lib/systemd/user \
    PRODUCT_LIBDIR=/usr/lib/oh-no-parent-control

systemd-sysusers
systemctl daemon-reload
systemctl reload dbus.service
systemctl enable --now \
    malcontent-timerd.service \
    malcontent-timer-extension-agent.service

pam-auth-update --disable malcontent

# Keep the per-user systemd manager outside the timed login session. Apply
# Malcontent to all present and future interactive users except the unlimited
# request-station account.
install -o root -g root -m 0644 /dev/stdin \
    /usr/share/pam-configs/oh-no-parent-control-session-limits <<'LIMITS_PAM'
Name: Oh No Parent Control managed session limits
Default: yes
Priority: 1000
Account-Type: Additional
Account:
 [success=2 default=ignore] pam_succeed_if.so quiet service = systemd-user
 [success=1 default=ignore] pam_succeed_if.so quiet user = oh-no-parent-control
 required pam_malcontent.so
LIMITS_PAM

install -o root -g root -m 0644 /dev/stdin \
    /etc/polkit-1/rules.d/00-oh-no-parent-control-session.rules <<'POLKIT_RULE'
polkit.addRule(function(action, subject) {
    if (action.id == "org.freedesktop.accounts.change-own-user-data" &&
        subject.user == "oh-no-parent-control")
        return polkit.Result.NO;
});
POLKIT_RULE

install -d -o root -g root -m 0755 /etc/gdm3/PreSession
install -o root -g root -m 0755 /dev/stdin \
    /etc/gdm3/PreSession/Default <<'GDM_GATE'
#!/bin/sh
if [ "${USER-}" = "oh-no-parent-control" ] || [ \
   "${LOGNAME-}" = "oh-no-parent-control" ]; then
    [ "${GDMSESSION-}" = "oh-no-parent-control" ] || exit 1
fi
exit 0
GDM_GATE

install -o root -g root -m 0755 /dev/stdin \
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

install -o root -g root -m 0644 /dev/stdin \
    /usr/share/pam-configs/oh-no-parent-control-kiosk-only <<'KIOSK_PAM'
Name: Oh No Parent Control kiosk-only account
Default: yes
Priority: 1000
Account-Type: Additional
Account:
 required pam_exec.so quiet /usr/local/sbin/oh-no-parent-control-login-check
KIOSK_PAM

pam-auth-update --enable oh-no-parent-control-session-limits
pam-auth-update --enable oh-no-parent-control-kiosk-only

passwd --delete "$KIOSK_USER"
sed -i -E \
    '/^[[:space:]]*(AutomaticLogin|TimedLogin|TimedLoginDelay|AutomaticLoginEnable|TimedLoginEnable)[[:space:]]*=/d' \
    /etc/gdm3/custom.conf
sed -i \
    '/^[[:space:]]*\[daemon\][[:space:]]*$/a AutomaticLoginEnable=false\nTimedLoginEnable=false' \
    /etc/gdm3/custom.conf

/usr/libexec/oh-no-parent-control-provision --kiosk-user "$KIOSK_USER"
systemctl daemon-reload
systemctl reload dbus.service
systemctl restart accounts-daemon.service

# Fail before completing if any essential installation invariant is missing.
kiosk_uid="$(id -u "$KIOSK_USER")"
test "$kiosk_uid" -ne 0
test -x /usr/bin/oh-no-parent-control
test -x /usr/libexec/oh-no-parent-control-broker
test -x /usr/libexec/oh-no-parent-control-provision
test -s /etc/oh-no-parent-control/config.json
test -s /usr/share/dbus-1/system.d/com.puffyslippers.OhNoParentControl1.conf
test -s /usr/share/polkit-1/actions/org.gnome.shell.extensions.oh-no-parent-control.policy
test -s /usr/share/polkit-1/actions/com.puffyslippers.OhNoParentControl1.policy
test -s /usr/lib/systemd/system/oh-no-parent-control-broker.service
test -s /usr/lib/systemd/user/oh-no-parent-control-app.service
test -s /usr/lib/systemd/user/oh-no-parent-control-polkit-agent.service
test -s /usr/lib/systemd/user/gnome-session@oh-no-parent-control.target.d/session.conf
test -s /usr/share/gnome-session/sessions/oh-no-parent-control.session
test -s /usr/share/wayland-sessions/oh-no-parent-control.desktop
grep -Fq "\"kiosk_uid\": $kiosk_uid" /etc/oh-no-parent-control/config.json
grep -Fq "<policy user=\"$KIOSK_USER\">" \
    /usr/share/dbus-1/system.d/com.puffyslippers.OhNoParentControl1.conf
grep -Fq "pam_exec.so quiet /usr/local/sbin/oh-no-parent-control-login-check" \
    /etc/pam.d/common-account
grep -Fq "pam_malcontent.so" /etc/pam.d/common-account
grep -Fq "AutomaticLoginEnable=false" /etc/gdm3/custom.conf
grep -Fq "TimedLoginEnable=false" /etc/gdm3/custom.conf
test "$(busctl --system get-property \
    org.freedesktop.Accounts \
    "/org/freedesktop/Accounts/User${kiosk_uid}" \
    com.endlessm.ParentalControls.SessionLimits LimitType)" = "u 0"
test "$(busctl --system get-property \
    org.freedesktop.Accounts \
    "/org/freedesktop/Accounts/User${kiosk_uid}" \
    org.freedesktop.Accounts.User Session)" = 's "oh-no-parent-control"'
systemctl is-enabled --quiet malcontent-timerd.service
systemctl is-enabled --quiet malcontent-timer-extension-agent.service
systemctl is-active --quiet malcontent-timerd.service
systemctl is-active --quiet malcontent-timer-extension-agent.service

# Integrate with Ubuntu's standard pending-reboot indicator. Preserve package
# names recorded by apt while adding this product only once across reruns.
printf '%s\n' '*** System restart required ***' > /run/reboot-required
touch /run/reboot-required.pkgs
if ! grep -Fxq 'oh-no-parent-control' /run/reboot-required.pkgs; then
    printf '%s\n' 'oh-no-parent-control' >> /run/reboot-required.pkgs
fi
chmod 0644 /run/reboot-required /run/reboot-required.pkgs

echo "Oh No! Parent Control installation completed successfully."
reboot_warning='*** REBOOT REQUIRED: run "sudo systemctl reboot" before using the kiosk session. ***'
if [[ -t 1 ]]; then
    printf '\n\033[1;33m%s\033[0m\n' "$reboot_warning"
else
    printf '\n%s\n' "$reboot_warning"
fi
