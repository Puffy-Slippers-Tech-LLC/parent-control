"""Persistent baseline settings, independent of movable fixture payloads."""

NATIVE_POLICY_FILES = (
    '/etc/systemd/system/display-manager.service.d/onpc-test-native-policy.conf',
    '/usr/local/libexec/onpc-test-native-policy-ready',
)


def native_policy_files(os_id):
    """Complete native monitoring startup before any prepared GDM session."""
    cli = {'ubuntu': '/usr/sbin/fapolicyd-cli', 'fedora': '/usr/bin/fapolicyd-cli'}[os_id]
    # A Type=forking native service can report started before trust loading.
    # Retry only its exact report-wait timeout; systemd bounds the complete
    # pre-start/session startup sequence and terminates its owned processes.
    ready = b'''#!/bin/sh
set -eu
while :; do
    if output=$("$1" --check-status 2>&1); then
        exit 0
    else
        status=$?
    fi
    if [ "$status" -ne 1 ] || [ "$output" != "Can't find fapolicyd: timed out waiting for report" ]; then
        printf '%s\\n' "$output" >&2
        exit "$status"
    fi
done
'''
    unit = ('[Unit]\nWants=fapolicyd.service\nAfter=fapolicyd.service\n'
            '[Service]\nTimeoutStartSec=180\n'
            'ExecStartPre=' + NATIVE_POLICY_FILES[1] + ' ' + cli + '\n')
    return {NATIVE_POLICY_FILES[0]: (unit.encode(), 0o644, 'system'),
            NATIVE_POLICY_FILES[1]: (ready, 0o755, 'system')}


def desktop_settings_files(accounts):
    """Disable only the fixed optional user-folder renamer entry points."""
    files = {}
    for role in ('child', 'other', 'parent'):
        config = accounts[role].pw_dir + '/.config/'
        files[config + 'autostart/user-dirs-update-gtk.desktop'] = (
            b'[Desktop Entry]\nType=Application\nName=User folders update\nHidden=true\n',
            0o644, role)
        files[config + 'systemd/user/user-dirs-update-gtk.service'] = (b'', 0o644, role)
    return files


def automatic_update_files(os_id):
    """Keep Ubuntu's automatic package transactions under preparation ownership."""
    if os_id != 'ubuntu':
        return {}
    return {'/etc/systemd/system/' + unit: (b'', 0o644, 'system') for unit in (
        'apt-daily.timer', 'apt-daily.service',
        'apt-daily-upgrade.timer', 'apt-daily-upgrade.service')}
