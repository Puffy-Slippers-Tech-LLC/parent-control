"""Finite reusable guest assets. No product state or attempt credentials."""
from pathlib import Path

try:
    from native_assets import ASSETS, GUI_FILES, PREFIX, desktop_entry, desktop_id
except ImportError:
    from tests.fixtures.native_assets import ASSETS, GUI_FILES, PREFIX, desktop_entry, desktop_id

MECHANICAL = '/opt/onpc-baseline-assets/onpc-test-application'
NATIVE = {
    'command': ('/opt/onpc-test-fixtures-command/native-fixture', 'Command'),
    'whitespace': ('/opt/onpc-test-fixtures-whitespace/native fixture', 'Whitespace'),
    'pattern': ('/opt/onpc-test-fixtures-pattern/Versioned-1.AppImage', 'Pattern'),
    'retention': ('/opt/onpc-test-fixtures-retention/native-fixture', 'Retention'),
}
CATALOG_PREFIX = 'com.puffyslippers.ONPCTest.Catalog.'
CATALOG_ENTRIES = (
    ('system', 'Shared', False), ('child', 'Shared', False),
    ('parent', 'Shared', False), ('child', 'ChildOnly', False),
    ('other', 'OtherOnly', False), ('parent', 'ParentOnly', False),
    ('system', 'Masked', False), ('child', 'Masked', True),
)


def native_files(accounts):
    """Map destination to (source key or bytes, mode, owner role)."""
    files = {MECHANICAL: ('mechanical', 0o755, 'system')}
    for role, filename, *rest in ASSETS:
        files[PREFIX + '/' + filename] = (role, 0o755, 'other')
    for filename in GUI_FILES:
        files[PREFIX + '/' + filename] = (filename, 0o644, 'other')
    for asset in ASSETS:
        path = accounts['other'].pw_dir + '/.local/share/applications/' + desktop_id(asset[0])
        files[path] = (desktop_entry(asset).encode(), 0o644, 'other')
    for target, suffix in NATIVE.values():
        files[target] = ('mechanical', 0o755, 'system')
        path = '/usr/share/applications/com.puffyslippers.ONPCTest.' + suffix + '.desktop'
        files[path] = (('[Desktop Entry]\nType=Application\nName=ONPC Native Fixture\n'
                        f'Exec="{target}"\nTerminal=false\n').encode(), 0o644, 'system')
    files[str(Path(NATIVE['pattern'][0]).with_name('Unrelated.AppImage'))] = (
        'mechanical', 0o755, 'system')
    return files


def catalogue_files(accounts, *, root=None, system_dir='/usr/share/applications',
                    local_bin='/usr/local/bin', system_bin='/usr/bin'):
    root = str(root or Path(NATIVE['command'][0]).parent / 'catalog')
    files = {}
    launchers = [(role, name, hidden, root + '/' + role + '-' + name, None)
                 for role, name, hidden in CATALOG_ENTRIES]
    for role, name, hidden in CATALOG_ENTRIES:
        files[root + '/' + role + '-' + name] = ('mechanical', 0o755, 'system')
    relative = 'onpc-test-catalog-relative'
    parent_only = 'onpc-test-catalog-parent-only'
    system = 'onpc-test-catalog-system'
    fallback = 'onpc-test-catalog-fallback'
    for role, directory, command in (
            ('child', '.local/bin', relative), ('child', 'bin', relative),
            ('other', 'bin', relative), ('parent', '.local/bin', relative),
            ('parent', '.local/bin', parent_only), ('parent', '.local/bin', system),
            ('parent', '.local/bin', fallback)):
        files[accounts[role].pw_dir + '/' + directory + '/' + command] = ('mechanical', 0o755, role)
    desktop_path = root + '/desktop path'
    for target in (desktop_path + '/' + relative, str(local_bin) + '/' + relative,
                   str(local_bin) + '/' + system, str(system_bin) + '/' + system,
                   str(system_bin) + '/' + fallback):
        files[target] = ('mechanical', 0o755, 'system')
    launchers.extend((('system', 'Relative', False, relative, None),
                      ('system', 'RelativeUnavailable', False, parent_only, None),
                      ('system', 'DesktopPath', False, relative, desktop_path),
                      ('system', 'SystemPreferred', False, system, None),
                      ('system', 'SystemFallback', False, fallback, None)))
    for role, name, hidden, command, working_directory in launchers:
        directory = (str(system_dir) if role == 'system' else
                     accounts[role].pw_dir + '/.local/share/applications')
        content = ('[Desktop Entry]\nType=Application\n' + f'Name=ONPC {role} {name}\n'
                   + f'Exec="{command}"\nTerminal=false\n'
                   + (f'Path={working_directory}\n' if working_directory else '')
                   + ('Hidden=true\n' if hidden else ''))
        files[directory + '/' + CATALOG_PREFIX + name + '.desktop'] = (content.encode(), 0o644, role)
    return files


def files(accounts):
    return native_files(accounts) | catalogue_files(accounts)
