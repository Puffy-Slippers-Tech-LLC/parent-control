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

# @trust_label@
    restorecon -R /etc/fapolicyd/trust.d

# @trust_complete@

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

# @readiness_start@
    # Fedora checks the canary in a separate unit so its setup does not touch
    # fapolicyd's SELinux-labelled runtime files. Configuration must fail if the
    # same readiness gate used by the display manager cannot complete.
    echo 'oh-no-parent-control: checking execution-policy readiness' >&2
    # start is a no-op for an already-running daemon. Load the newly installed
    # canary before waiting for it; broker reconciliation happens afterward.
    /usr/sbin/fagenrules
    /usr/sbin/fapolicyd-cli --reload-rules
    systemctl start oh-no-parent-control-execution-policy-ready.service

# @readiness_preflight@
    if { [ -e /etc/fapolicyd/rules.d/02-oh-no-parent-control-original-allow.rules ] ||
         [ -L /etc/fapolicyd/rules.d/02-oh-no-parent-control-original-allow.rules ]; } &&
       [ ! -f "$state/installed-fapolicyd-original-policy" ]; then
        echo 'oh-no-parent-control: original execution-policy path already exists; preserving it' >&2
        exit 1
    fi
    if { [ -e /etc/fapolicyd/rules.d/00-oh-no-parent-control-canary.rules ] ||
         [ -L /etc/fapolicyd/rules.d/00-oh-no-parent-control-canary.rules ]; } &&
       [ ! -f "$state/installed-fapolicyd-canary" ]; then
        echo 'oh-no-parent-control: execution-policy canary path already exists; preserving it' >&2
        exit 1
    fi

# @readiness_install@
    install_integration /usr/share/oh-no-parent-control/00-oh-no-parent-control-canary.rules \
        /etc/fapolicyd/rules.d/00-oh-no-parent-control-canary.rules \
        /var/lib/oh-no-parent-control/installed-fapolicyd-canary 0644

# @execution_policy_install@
    original_policy_eligible=$(/usr/libexec/oh-no-parent-control-fedora-execution-policy eligible)
    if [ "$original_policy_eligible" = yes ]; then
        install_integration /usr/share/oh-no-parent-control/99-oh-no-parent-control-allow.rules \
            /etc/fapolicyd/rules.d/02-oh-no-parent-control-original-allow.rules \
            /var/lib/oh-no-parent-control/installed-fapolicyd-original-policy 0644
        /usr/libexec/oh-no-parent-control-fedora-execution-policy commit
    fi

# @execution_policy_check_remove@
    check_integration /etc/fapolicyd/rules.d/02-oh-no-parent-control-original-allow.rules \
        /var/lib/oh-no-parent-control/installed-fapolicyd-original-policy

# @execution_policy_remove_rule@
    remove_integration /etc/fapolicyd/rules.d/02-oh-no-parent-control-original-allow.rules \
        /var/lib/oh-no-parent-control/installed-fapolicyd-original-policy

# @readiness_check_remove@
    check_integration /etc/fapolicyd/rules.d/00-oh-no-parent-control-canary.rules \
        /var/lib/oh-no-parent-control/installed-fapolicyd-canary

# @readiness_remove_rule@
    remove_integration /etc/fapolicyd/rules.d/00-oh-no-parent-control-canary.rules \
        /var/lib/oh-no-parent-control/installed-fapolicyd-canary

# @readiness_remove@
        # RemainAfterExit survives payload deletion and daemon-reload. Clear
        # the cached success only after GDM's dependency has been removed.
        readiness_state=$(systemctl show --property=ActiveState --value \
            oh-no-parent-control-execution-policy-ready.service)
        case "$readiness_state" in
            inactive) ;;
            failed)
                systemctl reset-failed oh-no-parent-control-execution-policy-ready.service
                ;;
            *)
                systemctl stop oh-no-parent-control-execution-policy-ready.service
                ;;
        esac

# @pam_remove@
    /usr/libexec/oh-no-parent-control-fedora-pam remove

# @notice_cleanup@
# Distribution has no Debian package-service/notice hook.

# @reboot_remove@
    printf '%s\n' reboot > /run/oh-no-parent-control-reboot-required
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
