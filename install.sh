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

require() {
    if ! "$@"; then
        echo "install: required check failed: $*" >&2
        exit 1
    fi
}

require_active() {
    local unit="$1"
    if ! systemctl is-active --quiet "$unit"; then
        echo "install: $unit is not active" >&2
        systemctl status --no-pager --full "$unit" >&2 || true
        journalctl -u "$unit" -n 80 --no-pager >&2 || true
        exit 1
    fi
}

# malcontent-timerd and its extension agent are Type=dbus units that exit
# after 30s of inactivity. Enable them, prove they can start, then allow
# them to idle. Requiring them to stay active at the end of install is a
# false failure on a machine with no live child session.
require_startable() {
    local unit="$1"
    echo "install: verifying $unit can start"
    if ! systemctl start "$unit"; then
        echo "install: $unit failed to start" >&2
        systemctl status --no-pager --full "$unit" >&2 || true
        journalctl -u "$unit" -n 80 --no-pager >&2 || true
        exit 1
    fi
    if ! systemctl is-active --quiet "$unit"; then
        echo "install: $unit did not become active" >&2
        systemctl status --no-pager --full "$unit" >&2 || true
        journalctl -u "$unit" -n 80 --no-pager >&2 || true
        exit 1
    fi
}

start_unit() {
    local unit="$1"
    echo "install: starting $unit"
    if ! systemctl restart "$unit"; then
        echo "install: $unit failed to start" >&2
        systemctl status --no-pager --full "$unit" >&2 || true
        journalctl -u "$unit" -n 80 --no-pager >&2 || true
        exit 1
    fi
}

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

# Compare the payload being installed with the last installed payload. A
# missing baseline is a first installation and deliberately requires reboot.
previous_activation_manifest="$(mktemp)"
first_installation=0
if [[ -f /usr/share/oh-no-parent-control/package-activation.json ]]; then
    cp /usr/share/oh-no-parent-control/package-activation.json \
        "$previous_activation_manifest"
else
    # mktemp creates the path, while changed-impacts deliberately recognizes a
    # first installation by an absent old manifest. Do not pass it an empty
    # file, which is neither a valid manifest nor a missing baseline.
    first_installation=1
    rm -f "$previous_activation_manifest"
fi
trap 'rm -f "$previous_activation_manifest"' EXIT

export DEBIAN_FRONTEND=noninteractive

# A previous package operation may have left dpkg's update state incomplete.
# APT refuses to run in that state and explicitly requires pending package
# configuration to finish first. If configuration exposes a missing dependency,
# continue to APT's supported repair operation, which retries configuration
# after installing the dependency.
if ! dpkg --configure --pending </dev/null; then
    echo "install: pending package configuration failed; asking APT to repair dependencies" >&2
fi

# Do not bypass DPKG locking: another package operation must finish first.
# Keep stdin attached to the invoking terminal; APT otherwise consumes it and
# the later reboot prompt sees EOF instead of an answer.
apt_get=(apt-get -o "DPkg::Lock::Timeout=$APT_LOCK_TIMEOUT_SECONDS")
"${apt_get[@]}" --fix-broken install -y </dev/null

"${apt_get[@]}" update </dev/null
"${apt_get[@]}" install -y software-properties-common </dev/null
add-apt-repository -y universe </dev/null
"${apt_get[@]}" update </dev/null
"${apt_get[@]}" install -y \
    accountsservice \
    dbus-user-session \
    fapolicyd \
    gdm3 \
    gir1.2-adw-1 \
    gir1.2-gstreamer-1.0 \
    gir1.2-gtk-4.0 \
    gnome-kiosk \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-ugly \
    gtk-update-icon-cache \
    libpam-malcontent \
    mate-polkit-bin \
    make \
    malcontent \
    python3 \
    python3-gi \
    python3-gi-cairo \
    </dev/null

if ! id -u "$KIOSK_USER" >/dev/null 2>&1; then
    adduser \
        --disabled-password \
        --comment "Oh No! Parent Control" \
        --home "/home/$KIOSK_USER" \
        --shell /bin/bash \
        "$KIOSK_USER"
fi

# Exclude the broker while a newly installed payload examines and, when
# required, rewrites its application-owned saved data. Leave the marker behind
# on failure so D-Bus activation cannot start incompatible code.
install -d -o root -g root -m 0700 /var/lib/oh-no-parent-control
touch /var/lib/oh-no-parent-control/migration-in-progress
if systemctl is-active --quiet oh-no-parent-control-broker.service; then
    systemctl stop oh-no-parent-control-broker.service
fi

usermod \
    --comment "Oh No! Parent Control" \
    --home "/home/$KIOSK_USER" \
    --shell /bin/bash \
    "$KIOSK_USER"
# Refresh AccountsService before fapolicyd starts intercepting process
# restarts. Provision later updates the running daemon over D-Bus.
start_unit accounts-daemon.service

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
    PRODUCT_LIBDIR=/usr/lib/oh-no-parent-control \
    GENERATE_ACTIVATION_MANIFEST=0

# The full-machine installer writes directly into the hicolor theme rather
# than going through dpkg's icon-cache trigger.  Refresh the cache now so GNOME
# can resolve the newly installed desktop icon instead of showing its generic
# fallback icon.
gtk-update-icon-cache --force --quiet /usr/share/icons/hicolor

/usr/libexec/oh-no-parent-control-migrate-state
rm -f /var/lib/oh-no-parent-control/migration-in-progress

# Keep the management launcher out of standard users' GNOME application
# listings.  Ubuntu grants administrative accounts membership in `sudo`; the
# broker independently rechecks AccountsService's administrator role for every
# management operation.
chown root:sudo /usr/share/applications/com.puffyslippers.OhNoParentControl.Parent.desktop

systemd-sysusers
systemctl daemon-reload
systemctl reload dbus.service
systemctl enable --now \
    fapolicyd.service \
    malcontent-timerd.service \
    malcontent-timer-extension-agent.service

pam-auth-update --disable malcontent </dev/null

# Keep the per-user systemd manager outside the timed login session. Apply
# Malcontent only to accounts which can be managed children and whose public
# AccountsService state confirms that a session limit is enabled. The dedicated
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

pam-auth-update --enable oh-no-parent-control-session-limits </dev/null
pam-auth-update --enable oh-no-parent-control-kiosk-only </dev/null

passwd --delete "$KIOSK_USER"
sed -i -E \
    '/^[[:space:]]*(AutomaticLogin|TimedLogin|TimedLoginDelay|AutomaticLoginEnable|TimedLoginEnable)[[:space:]]*=/d' \
    /etc/gdm3/custom.conf
sed -i \
    '/^[[:space:]]*\[daemon\][[:space:]]*$/a AutomaticLoginEnable=false\nTimedLoginEnable=false' \
    /etc/gdm3/custom.conf

# PAM and GDM integration is installed above, after the general product files.
# Generate its manifest only now so direct-installer updates compare the final
# installed integration rather than the previous version of those files.
env -u MAKEFLAGS -u MFLAGS \
    make --no-print-directory -C "$SCRIPT_DIR" _generate-package-activation-manifest \
    DESTDIR= \
    PREFIX=/usr \
    SYSCONFDIR=/etc \
    LIBEXECDIR=/usr/libexec \
    DATADIR=/usr/share \
    SYSTEMD_SYSTEM_DIR=/usr/lib/systemd/system \
    SYSTEMD_USER_DIR=/usr/lib/systemd/user \
    PRODUCT_LIBDIR=/usr/lib/oh-no-parent-control

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
# Product files may have replaced an already running D-Bus broker. Restart it
# after provisioning has written its configuration so the parent, kiosk, and
# broker always use the same installed interface and preference schema. Broker
# startup also republishes the child payload for every enabled managed account.
# Do not restart accounts-daemon here: provision already applied kiosk
# properties on the live daemon, and a restart under fapolicyd can stall.
start_unit oh-no-parent-control-broker.service

# Fail before completing if any essential installation invariant is missing.
kiosk_uid="$(id -u "$KIOSK_USER")"
require test "$kiosk_uid" -ne 0
require test -x /usr/bin/oh-no-parent-control
require test -x /usr/bin/oh-no-parent-control-parent
require test -x /usr/bin/mate-polkit
require test -x /usr/libexec/oh-no-parent-control-broker
require test -x /usr/libexec/oh-no-parent-control-migrate-state
require test -x /usr/libexec/oh-no-parent-control-query-usage
require test -x /usr/libexec/oh-no-parent-control-provision
require test -x /usr/libexec/oh-no-parent-control-package-activation
require test -x /usr/libexec/oh-no-parent-control-preserve-extension-state
require test -x /usr/libexec/oh-no-parent-control-session-limit-check
require test -x /usr/libexec/oh-no-parent-control-execution-policy-ready
require test -x /usr/libexec/oh-no-parent-control-execution-policy-probe
require test -s /usr/lib/oh-no-parent-control/kiosk/oh_no_parent_control_kiosk/Gearbox_Waltz.mp3
require test -s /etc/oh-no-parent-control/config.json
require test -s /etc/fapolicyd/rules.d/99-oh-no-parent-control-allow.rules
require test -s /usr/share/dbus-1/system.d/com.puffyslippers.OhNoParentControl1.conf
require test -s /usr/share/polkit-1/actions/tech.puffyslippers.com.ohnoparentcontrol.kiosk.request-access.policy
require test -s /usr/share/polkit-1/actions/tech.puffyslippers.com.ohnoparentcontrol.child.request-own-access.policy
require test ! -e /usr/share/polkit-1/actions/org.gnome.shell.extensions.oh-no-parent-control.policy
require test -s /usr/lib/systemd/system/oh-no-parent-control-broker.service
require test -s /usr/lib/systemd/system/oh-no-parent-control-restore-extension-state.service
require test -s /usr/lib/systemd/system/fapolicyd.service.d/oh-no-parent-control-readiness.conf
require test -s /usr/lib/systemd/system/display-manager.service.d/oh-no-parent-control.conf
require test -s /usr/lib/systemd/user/oh-no-parent-control-app.service
require test -s /usr/lib/systemd/user/oh-no-parent-control-polkit-agent.service
require test -s /usr/lib/systemd/user/gnome-session@oh-no-parent-control.target.d/session.conf
require test -s /usr/share/gnome-session/sessions/oh-no-parent-control.session
require test -s /usr/share/wayland-sessions/oh-no-parent-control.desktop
require test "$(stat -c %U:%G /usr/share/applications/com.puffyslippers.OhNoParentControl.Parent.desktop)" = "root:sudo"
require test "$(stat -c %a /usr/share/applications/com.puffyslippers.OhNoParentControl.Parent.desktop)" = "640"
require test -f "/home/$KIOSK_USER/.config/gnome-initial-setup-done"
require test "$(stat -c %U "/home/$KIOSK_USER/.config/gnome-initial-setup-done")" = \
    "$KIOSK_USER"
require test -f "/home/$KIOSK_USER/.config/gnome-initial-setup/upgrade-26.04-done"
require test "$(stat -c %U \
    "/home/$KIOSK_USER/.config/gnome-initial-setup/upgrade-26.04-done")" = \
    "$KIOSK_USER"
require grep -Fq "\"kiosk_uid\": $kiosk_uid" /etc/oh-no-parent-control/config.json
require grep -Fq '<allow send_destination="com.puffyslippers.OhNoParentControl1"' \
    /usr/share/dbus-1/system.d/com.puffyslippers.OhNoParentControl1.conf
require grep -Fq "pam_exec.so quiet /usr/local/sbin/oh-no-parent-control-login-check" \
    /etc/pam.d/common-account
require grep -Fq "pam_malcontent.so" /etc/pam.d/common-account
require grep -Fq "pam_exec.so quiet quiet_log /usr/libexec/oh-no-parent-control-session-limit-check" \
    /etc/pam.d/common-account
require grep -Fq "pam_succeed_if.so quiet user ingroup sudo" \
    /etc/pam.d/common-account
require grep -Fq "Group=sudo" /usr/lib/systemd/system/oh-no-parent-control-broker.service
require grep -Fq "Wants=fapolicyd.service" /usr/lib/systemd/system/oh-no-parent-control-broker.service
require grep -Fq "AutomaticLoginEnable=false" /etc/gdm3/custom.conf
require grep -Fq "TimedLoginEnable=false" /etc/gdm3/custom.conf
require test "$(busctl --system get-property \
    org.freedesktop.Accounts \
    "/org/freedesktop/Accounts/User${kiosk_uid}" \
    com.endlessm.ParentalControls.SessionLimits LimitType)" = "u 0"
require test "$(busctl --system get-property \
    org.freedesktop.Accounts \
    "/org/freedesktop/Accounts/User${kiosk_uid}" \
    org.freedesktop.Accounts.User Session)" = 's "oh-no-parent-control"'
if [[ -n "$INSTALLER_USER" ]]; then
    installer_uid="$(id -u "$INSTALLER_USER")"
    require test "$(busctl --system get-property \
        org.freedesktop.Accounts \
        "/org/freedesktop/Accounts/User${kiosk_uid}" \
        org.freedesktop.Accounts.User Language)" = \
        "$(busctl --system get-property \
        org.freedesktop.Accounts \
        "/org/freedesktop/Accounts/User${installer_uid}" \
        org.freedesktop.Accounts.User Language)"
fi
require systemctl is-enabled --quiet malcontent-timerd.service
require systemctl is-enabled --quiet fapolicyd.service
require systemctl is-enabled --quiet malcontent-timer-extension-agent.service
require systemctl is-enabled --quiet oh-no-parent-control-restore-extension-state.service
require_startable malcontent-timerd.service
require_active fapolicyd.service
require_startable malcontent-timer-extension-agent.service
require_active oh-no-parent-control-broker.service

activation_impacts="$(/usr/libexec/oh-no-parent-control-package-activation \
    changed-impacts --old "$previous_activation_manifest" \
    --new /usr/share/oh-no-parent-control/package-activation.json)"
if [[ "$activation_impacts" == *process-restart* ]]; then
    systemctl restart oh-no-parent-control-broker.service
fi

echo "Oh No! Parent Control installation completed successfully."
if [[ "$first_installation" -eq 1 || "$activation_impacts" == *reboot* ]]; then
    # Preserve reboot requirements written by Ubuntu or another package.
    # Write the OS reboot marker before any optional GNOME state snapshot so a
    # failed snapshot cannot skip the login-stack reboot requirement.
    if [[ ! -e /run/reboot-required ]]; then
        printf '%s\n' '*** System restart required ***' > /run/reboot-required
    fi
    touch /run/reboot-required.pkgs
    if ! grep -Fxq 'oh-no-parent-control' /run/reboot-required.pkgs; then
        printf '%s\n' 'oh-no-parent-control' >> /run/reboot-required.pkgs
    fi
    chmod 0644 /run/reboot-required /run/reboot-required.pkgs

    # Ubuntu treats a Shell stop timeout during reboot as an extension crash and
    # persists disable-user-extensions=true. Preserve the invoking account's
    # exact pre-reboot value and restore it before GDM starts after this reboot.
    if [[ -n "$INSTALLER_USER" ]]; then
        /usr/libexec/oh-no-parent-control-preserve-extension-state \
            --schedule-uid "$(id -u "$INSTALLER_USER")" \
            || echo "install: warning: could not preserve GNOME extension state for reboot" >&2
    fi

    reboot_warning='*** REBOOT REQUIRED: run "sudo systemctl reboot" before using the kiosk session. ***'
    if [[ -t 1 ]]; then
        printf '\n\033[1;33m%s\033[0m\n' "$reboot_warning"
    else
        printf '\n%s\n' "$reboot_warning"
    fi

    # A person running the installer from a terminal can activate the required
    # login-stack boundary immediately.  Keep unattended installs
    # non-interactive; the standard Ubuntu marker above remains authoritative
    # until an administrator reboots by another means.  Prefer stdin when it is
    # a terminal; otherwise open the controlling TTY (permission bits on
    # /dev/tty are not enough to prove it can be opened).
    printf '\nReboot now? [y/N] '
    reboot_answer=""
    if [[ -t 0 ]]; then
        read -r reboot_answer || reboot_answer=""
    elif { exec 3<>/dev/tty; } 2>/dev/null; then
        read -r reboot_answer <&3 || reboot_answer=""
        exec 3>&-
    fi
    case "$reboot_answer" in
        y|Y|yes|YES|Yes)
            systemctl reboot
            ;;
    esac
else
    printf 'No reboot is required for this update.\n'
fi
