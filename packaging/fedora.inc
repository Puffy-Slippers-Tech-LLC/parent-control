# @pre_helpers@
require_supported_os() (
    ID=
    VERSION_ID=
    VARIANT_ID=
    release_file=/etc/os-release
    [ -e "$release_file" ] || release_file=/usr/lib/os-release
    if [ ! -r "$release_file" ]; then
        echo 'Oh No! Parent Control requires Fedora Workstation 44; operating system could not be identified.' >&2
        exit 1
    fi
    # shellcheck disable=SC1090
    . "$release_file"
    if [ "$ID" != fedora ] || [ "$VERSION_ID" != 44 ] || [ "$VARIANT_ID" != workstation ]; then
        echo 'Oh No! Parent Control requires Fedora Workstation 44 for this development RPM.' >&2
        exit 1
    fi
    authselect check
    authselect current --raw >/dev/null
    current_profile=$(authselect current --raw)
    case " $current_profile " in
        *' without-nullok '*)
            echo 'oh-no-parent-control: current PAM profile disallows the passwordless kiosk; preserving it' >&2
            exit 1 ;;
    esac
    if { [ -e /etc/authselect/custom/oh-no-parent-control ] ||
         [ -L /etc/authselect/custom/oh-no-parent-control ]; } &&
       [ ! -f /var/lib/oh-no-parent-control/fedora-authselect.json ]; then
        echo 'oh-no-parent-control: reserved authselect profile exists; preserving it' >&2
        exit 1
    fi
)
prepare_package_notice() { :; }

# @pam_restore@
    /usr/libexec/oh-no-parent-control-fedora-pam install

# @broker_policy@
# Distribution has no Debian package-service/notice hook.

# @create_account@
        useradd --create-home --comment "Oh No! Parent Control" \
            --home-dir "/home/$kiosk_user" --shell /bin/bash "$kiosk_user"

# @initial_setup@
    # Write home-local initial-setup markers as their owner.
    runuser -u "$kiosk_user" -- /bin/sh -c '
        umask 077
        mkdir -p /home/oh-no-parent-control/.config &&
        touch /home/oh-no-parent-control/.config/gnome-initial-setup-done
    '

# @pam_enable@
    /usr/libexec/oh-no-parent-control-fedora-pam install

# @reboot_install@
                printf '%s\n' reboot > /run/oh-no-parent-control-reboot-required
                echo 'oh-no-parent-control: reboot required before using the kiosk session' >&2

# @configuration_notice@
    # Apply system-owned SELinux labels; keep SELinux enforcing.
    restorecon -R /etc/oh-no-parent-control /etc/gdm/PreSession \
        /etc/fapolicyd/rules.d /usr/share/dbus-1/system.d \
        /var/lib/oh-no-parent-control /home/oh-no-parent-control
    echo 'PASS: Oh No! Parent Control package configuration completed successfully.'
    if [ -f /run/oh-no-parent-control-reboot-required ]; then
        echo '*** REBOOT REQUIRED: reboot before using the kiosk session. ***' >&2
    fi

# @pam_remove@
    /usr/libexec/oh-no-parent-control-fedora-pam remove

# @notice_cleanup@
# Distribution has no Debian package-service/notice hook.

# @reboot_remove@
    rm -f /run/oh-no-parent-control-reboot-required
    echo '*** REBOOT REQUIRED: reboot to finish removing Oh No! Parent Control. ***' >&2

# @distribution_cleanup@
    rm -f /var/lib/oh-no-parent-control/fedora-authselect.json

# @gdm_presession_dir@
/etc/gdm/PreSession

# @service_command@
systemctl

# @bus_reload@
systemctl reload dbus.service

# @delete_account@
userdel "$kiosk_user"

# @admin_group@
wheel
