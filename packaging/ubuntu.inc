# @pre_helpers@
require_supported_os() (
    # Use the system's release identity, never inherited environment values or
    # ID_LIKE: Ubuntu derivatives are not supported. Keep sourced values local.
    ID=
    VERSION_ID=
    if [ -e /etc/os-release ]; then
        release_file=/etc/os-release
    else
        release_file=/usr/lib/os-release
    fi
    if [ ! -r "$release_file" ]; then
        echo 'Oh No! Parent Control requires Ubuntu 26.04 or newer. Installation stopped because the operating system could not be identified.' >&2
        exit 1
    fi
    # os-release is the system-provided, shell-compatible release definition.
    # shellcheck disable=SC1090
    . "$release_file"
    if [ "$ID" != ubuntu ]; then
        echo 'Oh No! Parent Control requires Ubuntu 26.04 or newer. This system is not Ubuntu; other distributions, including Ubuntu derivatives, are not supported.' >&2
        exit 1
    fi
    case "$VERSION_ID" in
        [0-9][0-9].[0-9][0-9]) ;;
        *)
            echo 'Oh No! Parent Control requires Ubuntu 26.04 or newer. Installation stopped because the Ubuntu release version could not be verified.' >&2
            exit 1
            ;;
    esac
    if ! dpkg --compare-versions "$VERSION_ID" ge 26.04; then
        printf 'Oh No! Parent Control requires Ubuntu 26.04 or newer. This system runs Ubuntu %s. Please upgrade Ubuntu before installing.\n' "$VERSION_ID" >&2
        exit 1
    fi
)

prepare_package_notice() {
    # A new APT hook is too late for the APT process already running. dpkg
    # reads its own hooks again when APT starts the configuration pass.
    # Generate this owned configuration before unpack, rather than shipping
    # a conffile which would only become available during configuration.
    notice_path=/etc/dpkg/dpkg.cfg.d/99-oh-no-parent-control-notice
    notice_hook='post-invoke=if [ -x /usr/libexec/oh-no-parent-control-package-notice ]; then /usr/libexec/oh-no-parent-control-package-notice --after-dpkg; fi'
    if [ -L /etc/dpkg ] || [ -L /etc/dpkg/dpkg.cfg.d ] ||
       [ -L "$notice_path" ]; then
        echo 'oh-no-parent-control: refusing substituted package notice configuration' >&2
        exit 1
    fi
    if [ -e "$notice_path" ]; then
        if [ ! -f "$notice_path" ] || [ "$(cat "$notice_path")" != "$notice_hook" ]; then
            echo 'oh-no-parent-control: preserving modified package notice configuration' >&2
            exit 1
        fi
    else
        install -d -o root -g root -m 0755 /etc/dpkg/dpkg.cfg.d
        printf '%s\n' "$notice_hook" > "$notice_path"
        chmod 0644 "$notice_path"
    fi
    rm -f /run/oh-no-parent-control-package-configuration-complete
}

# @pam_restore@
    pam-auth-update --package \
        --disable malcontent \
        --enable oh-no-parent-control-session-limits \
        --enable oh-no-parent-control-kiosk-only </dev/null

# @broker_policy@
    broker_policy_status=0
    broker_policy_helper="${DPKG_ROOT:-}/usr/sbin/policy-rc.d"
    if [ -x "$broker_policy_helper" ]; then
        "$broker_policy_helper" oh-no-parent-control-broker.service "$1" || broker_policy_status=$?
    fi
    case "$broker_policy_status" in
        0|104) ;;
        101)
            echo 'oh-no-parent-control: broker activation deferred by policy-rc.d' >&2
            return
            ;;
        *)
            echo "oh-no-parent-control: broker activation policy failed (status $broker_policy_status)" >&2
            return 1
            ;;
    esac

# @create_account@
        adduser --disabled-password --gecos "Oh No! Parent Control" \
            --home "/home/$kiosk_user" --shell /bin/bash "$kiosk_user"

# @initial_setup@
    # User-controlled home paths must never be traversed with root's write
    # privileges. runuser also keeps these files owned by the kiosk naturally.
    runuser -u "$kiosk_user" -- /bin/sh -c '
        umask 077
        mkdir -p /home/oh-no-parent-control/.config/gnome-initial-setup &&
        touch /home/oh-no-parent-control/.config/gnome-initial-setup-done \
            /home/oh-no-parent-control/.config/gnome-initial-setup/upgrade-26.04-done
    '

# @trust_label@
# No SELinux integration on Ubuntu.

# @pam_enable@
    # Query debconf through its supported protocol before changing the one
    # dependency profile we replace. Restore only that choice on removal.
    pam_baseline=/var/lib/oh-no-parent-control/malcontent-pam-before-install
    if [ -L "$pam_baseline" ]; then
        echo 'oh-no-parent-control: unsafe original PAM selection' >&2
        exit 1
    fi
    if [ ! -f "$pam_baseline" ]; then
        pam_profiles=$(printf 'GET libpam-runtime/profiles\n' | debconf-communicate libpam-runtime)
        case "$pam_profiles" in
            '0 '*) ;;
            *) echo 'oh-no-parent-control: cannot capture original PAM selection' >&2; exit 1 ;;
        esac
        pam_choice=disabled
        case ", ${pam_profiles#0 }, " in
            *', malcontent, '*) pam_choice=enabled ;;
        esac
        printf '%s\n' "$pam_choice" > "$pam_baseline"
        chmod 0600 "$pam_baseline"
    fi
    pam-auth-update --package \
        --disable malcontent \
        --enable oh-no-parent-control-session-limits \
        --enable oh-no-parent-control-kiosk-only </dev/null
    if ! grep -Eq '^[[:space:]]*[^#[:space:]].*pam_oh_no_parent_control\.so' /etc/pam.d/common-auth ||
       ! grep -Eq '^[[:space:]]*[^#[:space:]].*/usr/libexec/oh-no-parent-control-login-check' /etc/pam.d/common-account; then
        echo 'oh-no-parent-control: PAM integration was not activated; preserving local PAM configuration' >&2
        exit 1
    fi

# @reboot_install@
                echo 'oh-no-parent-control: reboot required; notifying Ubuntu update-notifier' >&2
                # Use Ubuntu's package notification hook. Avoid duplicate
                # package entries when configuration is retried before reboot.
                if [ ! -e /run/reboot-required ] || \
                        ! grep -Fxq 'oh-no-parent-control' /run/reboot-required.pkgs 2>/dev/null; then
                    DPKG_MAINTSCRIPT_PACKAGE=oh-no-parent-control \
                        /usr/share/update-notifier/notify-reboot-required
                fi
                # The Ubuntu helper can defer its marker for Livepatch. Our
                # PAM/display-manager changes still require a reboot, so ensure
                # the shared markers exist without clearing other requests.
                if [ ! -e /run/reboot-required ]; then
                    printf '%s\n' '*** System restart required ***' > /run/reboot-required
                fi
                touch /run/reboot-required.pkgs
                if ! grep -Fxq 'oh-no-parent-control' /run/reboot-required.pkgs; then
                    printf '%s\n' 'oh-no-parent-control' >> /run/reboot-required.pkgs
                fi
                chmod 0644 /run/reboot-required /run/reboot-required.pkgs

# @configuration_notice@
    /usr/libexec/oh-no-parent-control-package-notice --configured

# @readiness_start@

# @readiness_remove@

# @readiness_preflight@

# @readiness_install@

# @readiness_check_remove@

# @readiness_remove_rule@

# @pam_remove@
    pam_choice=--disable
    pam_baseline=/var/lib/oh-no-parent-control/malcontent-pam-before-install
    if [ -L "$pam_baseline" ]; then
        echo 'oh-no-parent-control: unsafe original PAM selection' >&2
        exit 1
    fi
    if [ -f "$pam_baseline" ]; then
        case "$(cat "$pam_baseline")" in
            enabled) pam_choice=--enable ;;
            disabled) ;;
            *) echo 'oh-no-parent-control: invalid original PAM selection' >&2; exit 1 ;;
        esac
    else
        # A failed configuration may never have changed PAM. Do not invent a
        # choice for the dependency in that case.
        pam_choice=
    fi
    pam-auth-update --package \
        --remove oh-no-parent-control-session-limits \
        --remove oh-no-parent-control-kiosk-only ${pam_choice:+$pam_choice malcontent} </dev/null
    # pam-auth-update preserves locally edited stacks and can return success
    # without removing references. Do not delete modules still used by PAM.
    pam_reference_status=0
    grep -Eq '^[[:space:]]*[^#[:space:]].*(pam_oh_no_parent_control|/usr/libexec/oh-no-parent-control-)' \
        /etc/pam.d/common-auth /etc/pam.d/common-account \
        /etc/pam.d/common-password /etc/pam.d/common-session \
        /etc/pam.d/common-session-noninteractive || pam_reference_status=$?
    case "$pam_reference_status" in
        1) ;;
        *) echo 'oh-no-parent-control: PAM references remain or could not be checked; resolve local PAM changes before removal' >&2; exit 1 ;;
    esac

# @notice_cleanup@
case "$1" in
    remove|purge|abort-install)
        notice_path=/etc/dpkg/dpkg.cfg.d/99-oh-no-parent-control-notice
        notice_hook='post-invoke=if [ -x /usr/libexec/oh-no-parent-control-package-notice ]; then /usr/libexec/oh-no-parent-control-package-notice --after-dpkg; fi'
        # Never remove an administrator's replacement. The guard in an
        # unchanged hook also makes a removed executable harmless.
        if [ ! -L /etc/dpkg ] && [ ! -L /etc/dpkg/dpkg.cfg.d ] &&
           [ ! -L "$notice_path" ] && [ -f "$notice_path" ] &&
           [ "$(cat "$notice_path")" = "$notice_hook" ]; then
            rm -f "$notice_path"
        fi
        rm -f /run/oh-no-parent-control-package-configuration-complete
        ;;
esac

# @reboot_remove@
    # postrm cannot depend on update-notifier still being installed. Use its
    # public hook when available, and always retain the shared Ubuntu markers.
    if [ -x /usr/share/update-notifier/notify-reboot-required ] &&
       { [ ! -e /run/reboot-required ] ||
         ! grep -Fxq oh-no-parent-control /run/reboot-required.pkgs 2>/dev/null; }; then
        if ! DPKG_MAINTSCRIPT_PACKAGE=oh-no-parent-control \
                /usr/share/update-notifier/notify-reboot-required; then
            echo 'oh-no-parent-control: reboot notifier unavailable; recording reboot request directly' >&2
        fi
    fi
    if [ ! -e /run/reboot-required ]; then
        printf '%s\n' '*** System restart required ***' > /run/reboot-required
    fi
    touch /run/reboot-required.pkgs
    if ! grep -Fxq oh-no-parent-control /run/reboot-required.pkgs; then
        printf '%s\n' oh-no-parent-control >> /run/reboot-required.pkgs
    fi
    chmod 0644 /run/reboot-required /run/reboot-required.pkgs
    # The packaged APT Post-Invoke hook prints the terminal reminder after
    # triggers finish. Direct dpkg removal retains Ubuntu's reboot markers.

# @gdm_presession_dir@
/etc/gdm3/PreSession

# @service_command@
deb-systemd-invoke

# @bus_reload@
invoke-rc.d dbus reload

# @delete_account@
deluser "$kiosk_user"

# @admin_group@
sudo

# @distribution_cleanup@
    # No additional distro-owned state.
