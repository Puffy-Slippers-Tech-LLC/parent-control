#!/bin/bash
set -euo pipefail

readonly KIOSK_USER="oh-no-parent-control"
readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly APT_LOCK_TIMEOUT_SECONDS=300
INSTALLER_USER="${SUDO_USER-}"

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

# sudo is the documented entry point and identifies the desktop account whose
# language should be used by the kiosk. A direct root invocation leaves the
# kiosk on the machine-wide default locale.
if [[ "$INSTALLER_USER" == root ]]; then
    INSTALLER_USER=""
elif [[ -n "$INSTALLER_USER" ]] && ! id -u "$INSTALLER_USER" >/dev/null 2>&1; then
    INSTALLER_USER=""
fi

if [[ ! -f "$SCRIPT_DIR/Makefile" || ! -f "$SCRIPT_DIR/tools/provision.py" ]]; then
    echo "install: run the installer from a complete release directory" >&2
    exit 1
fi

export DEBIAN_FRONTEND=noninteractive

# A previous package operation may have left dpkg's update state incomplete.
# APT refuses to run in that state and explicitly requires pending package
# configuration to finish first. If configuration exposes a missing dependency,
# continue to APT's supported repair operation, which retries configuration
# after installing the dependency.
if ! dpkg --configure --pending; then
    echo "install: pending package configuration failed; asking APT to repair dependencies" >&2
fi

# Do not bypass DPKG locking: another package operation must finish first.
apt_get=(apt-get -o "DPkg::Lock::Timeout=$APT_LOCK_TIMEOUT_SECONDS")
"${apt_get[@]}" --fix-broken install -y

"${apt_get[@]}" update
"${apt_get[@]}" install -y software-properties-common
add-apt-repository -y universe
"${apt_get[@]}" update
"${apt_get[@]}" install -y \
    accountsservice \
    dbus-user-session \
    gdm3 \
    gir1.2-adw-1 \
    gir1.2-gtk-4.0 \
    gnome-kiosk \
    libpam-malcontent \
    lxqt-policykit \
    make \
    malcontent \
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
# Malcontent only to accounts which can be managed children: the dedicated
# request-station account and members of Ubuntu's administrator group are
# intentionally unlimited.
install -o root -g root -m 0644 \
    "$SCRIPT_DIR/data/pam-configs/oh-no-parent-control-session-limits" \
    /usr/share/pam-configs/oh-no-parent-control-session-limits

install -o root -g root -m 0644 \
    "$SCRIPT_DIR/data/polkit-1/rules.d/00-oh-no-parent-control-session.rules" \
    /etc/polkit-1/rules.d/00-oh-no-parent-control-session.rules

install -d -o root -g root -m 0755 /etc/gdm3/PreSession
install -o root -g root -m 0755 \
    "$SCRIPT_DIR/data/gdm3/PreSession/Default" \
    /etc/gdm3/PreSession/Default

install -o root -g root -m 0755 \
    "$SCRIPT_DIR/tools/oh-no-parent-control-login-check" \
    /usr/local/sbin/oh-no-parent-control-login-check

install -o root -g root -m 0644 \
    "$SCRIPT_DIR/data/pam-configs/oh-no-parent-control-kiosk-only" \
    /usr/share/pam-configs/oh-no-parent-control-kiosk-only

pam-auth-update --enable oh-no-parent-control-session-limits
pam-auth-update --enable oh-no-parent-control-kiosk-only

passwd --delete "$KIOSK_USER"
sed -i -E \
    '/^[[:space:]]*(AutomaticLogin|TimedLogin|TimedLoginDelay|AutomaticLoginEnable|TimedLoginEnable)[[:space:]]*=/d' \
    /etc/gdm3/custom.conf
sed -i \
    '/^[[:space:]]*\[daemon\][[:space:]]*$/a AutomaticLoginEnable=false\nTimedLoginEnable=false' \
    /etc/gdm3/custom.conf

provision_args=(--kiosk-user "$KIOSK_USER")
if [[ -n "$INSTALLER_USER" ]]; then
    provision_args+=(--language-source-user "$INSTALLER_USER")
fi
/usr/libexec/oh-no-parent-control-provision "${provision_args[@]}"

# GNOME Initial Setup otherwise runs on the account's first session and asks
# for language and diagnostics choices. Ubuntu 26.04 also starts its upgrade
# flow unless the release-specific completion marker exists. The kiosk is
# fully provisioned here, so record both as complete before it can log in.
kiosk_gid="$(id -g "$KIOSK_USER")"
install -d -o "$KIOSK_USER" -g "$kiosk_gid" -m 0700 \
    "/home/$KIOSK_USER/.config" \
    "/home/$KIOSK_USER/.config/gnome-initial-setup"
install -o "$KIOSK_USER" -g "$kiosk_gid" -m 0644 /dev/null \
    "/home/$KIOSK_USER/.config/gnome-initial-setup-done"
install -o "$KIOSK_USER" -g "$kiosk_gid" -m 0644 /dev/null \
    "/home/$KIOSK_USER/.config/gnome-initial-setup/upgrade-26.04-done"
systemctl daemon-reload
systemctl reload dbus.service
systemctl enable oh-no-parent-control-restore-extension-state.service
systemctl restart accounts-daemon.service
# Product files may have replaced an already running D-Bus broker. Restart it
# after provisioning has written its configuration so the parent, kiosk, and
# broker always use the same installed interface and preference schema.
systemctl restart oh-no-parent-control-broker.service

# Fail before completing if any essential installation invariant is missing.
kiosk_uid="$(id -u "$KIOSK_USER")"
test "$kiosk_uid" -ne 0
test -x /usr/bin/oh-no-parent-control
test -x /usr/bin/oh-no-parent-control-parent
test -x /usr/bin/lxqt-policykit-agent
test -x /usr/libexec/oh-no-parent-control-broker
test -x /usr/libexec/oh-no-parent-control-provision
test -x /usr/libexec/oh-no-parent-control-preserve-extension-state
test -s /etc/oh-no-parent-control/config.json
test -s /usr/share/dbus-1/system.d/com.puffyslippers.OhNoParentControl1.conf
test -s /usr/share/polkit-1/actions/org.gnome.shell.extensions.oh-no-parent-control.policy
test -s /usr/share/polkit-1/actions/com.puffyslippers.OhNoParentControl1.policy
test -s /usr/lib/systemd/system/oh-no-parent-control-broker.service
test -s /usr/lib/systemd/system/oh-no-parent-control-restore-extension-state.service
test -s /usr/lib/systemd/user/oh-no-parent-control-app.service
test -s /usr/lib/systemd/user/oh-no-parent-control-polkit-agent.service
test -s /usr/lib/systemd/user/gnome-session@oh-no-parent-control.target.d/session.conf
test -s /usr/share/gnome-session/sessions/oh-no-parent-control.session
test -s /usr/share/wayland-sessions/oh-no-parent-control.desktop
test -f "/home/$KIOSK_USER/.config/gnome-initial-setup-done"
test "$(stat -c %U "/home/$KIOSK_USER/.config/gnome-initial-setup-done")" = \
    "$KIOSK_USER"
test -f "/home/$KIOSK_USER/.config/gnome-initial-setup/upgrade-26.04-done"
test "$(stat -c %U \
    "/home/$KIOSK_USER/.config/gnome-initial-setup/upgrade-26.04-done")" = \
    "$KIOSK_USER"
grep -Fq "\"kiosk_uid\": $kiosk_uid" /etc/oh-no-parent-control/config.json
grep -Fq '<allow send_destination="com.puffyslippers.OhNoParentControl1"' \
    /usr/share/dbus-1/system.d/com.puffyslippers.OhNoParentControl1.conf
grep -Fq "pam_exec.so quiet /usr/local/sbin/oh-no-parent-control-login-check" \
    /etc/pam.d/common-account
grep -Fq "pam_malcontent.so" /etc/pam.d/common-account
grep -Fq "pam_succeed_if.so quiet user ingroup sudo" \
    /etc/pam.d/common-account
grep -Fq "Group=sudo" /usr/lib/systemd/system/oh-no-parent-control-broker.service
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
if [[ -n "$INSTALLER_USER" ]]; then
    installer_uid="$(id -u "$INSTALLER_USER")"
    test "$(busctl --system get-property \
        org.freedesktop.Accounts \
        "/org/freedesktop/Accounts/User${kiosk_uid}" \
        org.freedesktop.Accounts.User Language)" = \
        "$(busctl --system get-property \
        org.freedesktop.Accounts \
        "/org/freedesktop/Accounts/User${installer_uid}" \
        org.freedesktop.Accounts.User Language)"
fi
systemctl is-enabled --quiet malcontent-timerd.service
systemctl is-enabled --quiet malcontent-timer-extension-agent.service
systemctl is-enabled --quiet oh-no-parent-control-restore-extension-state.service
systemctl is-active --quiet malcontent-timerd.service
systemctl is-active --quiet malcontent-timer-extension-agent.service
systemctl is-active --quiet oh-no-parent-control-broker.service

# Ubuntu treats a Shell stop timeout during reboot as an extension crash and
# persists disable-user-extensions=true. Preserve the invoking account's exact
# pre-reboot value and restore it once, before GDM starts after this required
# reboot. This never turns extensions on when the user had disabled them.
if [[ -n "$INSTALLER_USER" ]]; then
    /usr/libexec/oh-no-parent-control-preserve-extension-state \
        --schedule-uid "$(id -u "$INSTALLER_USER")"
fi

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
