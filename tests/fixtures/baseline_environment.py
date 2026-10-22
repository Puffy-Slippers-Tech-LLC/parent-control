"""Persistent baseline settings, independent of movable fixture payloads."""


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
