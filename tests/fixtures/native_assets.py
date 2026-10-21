"""Finite native fixture identities shared by builder and guarded preparation.

A/H/S/N are later policy roles. Preparation leaves all four Allowed.
"""
PREFIX = '/opt/onpc-test-fixtures/Applications'
ASSETS = (
    ('A', 'Exact Fixture.AppImage', 'ONPC Allowed Fixture', 'Exact native catalogue fixture', 'precise'),
    ('H', 'Path With Spaces.AppImage', 'ONPC Hard Fixture', 'Whitespace native catalogue fixture', 'precise'),
    ('S', 'Versioned/Lunar Client-3.7.17.AppImage', 'ONPC Soft Fixture', 'Versioned native catalogue fixture', 'pattern'),
    ('N', 'PrismLauncher.AppImage', 'ONPC Nonmatching Fixture', 'Unrelated native catalogue fixture', 'precise'),
)
GUI_FILES = ('onpc-test-gui.py', 'gtk_automation.py')
# Keep the earlier generated/baseline S file as an untrusted compatibility
# control. The active launcher and policy pattern use only Versioned.
LEGACY_S = 'Lunar Client-3.7.17.AppImage'
TRUSTED_NATIVE = {
    'trusted-hard': ('/opt/onpc-test-fixtures-trusted-hard/native-fixture', 'TrustedHard'),
    'trusted-soft': ('/opt/onpc-test-fixtures-trusted-soft/native-fixture', 'TrustedSoft'),
}
ACTIVITY_PREFIX = '/opt/onpc-test-fixtures-activity'
ACTIVITY_EXECUTABLE = ACTIVITY_PREFIX + '/native-fixture'


def trusted_file_modes():
    """Exact root-owned admitted inputs; existing policy controls stay untrusted."""
    return {path: 0o755 for path, _ in TRUSTED_NATIVE.values()} | {
        ACTIVITY_EXECUTABLE: 0o755,
        **{ACTIVITY_PREFIX + '/' + name: 0o644 for name in GUI_FILES}}


def activity_sources():
    return ('fixtures/native/identity-trusted-activity',
            'fixtures/native/onpc-test-gui.py', 'fixtures/native/gtk_automation.py')


def desktop_id(role):
    assert role in ('A', 'H', 'S', 'N')
    return 'com.puffyslippers.ONPCTest.' + role + '.desktop'


def desktop_entry(asset):
    role, filename, name, description, match = asset
    return ('[Desktop Entry]\nType=Application\n' + f'Name={name}\nComment={description}\n'
            'Icon=applications-system\n' + f'Exec="{PREFIX}/{filename}"\nTerminal=false\n')


def executable_path(role, *, prefix=None):
    """Active absolute executable, independent of catalogue/order indexing."""
    filename, = (asset[1] for asset in ASSETS if asset[0] == role)
    return (PREFIX if prefix is None else prefix) + '/' + filename


def version_pattern(*, prefix=None):
    return (PREFIX if prefix is None else prefix) + '/Versioned/Lunar Client-*.AppImage'


def legacy_executable_paths(*, prefix=None):
    return ((PREFIX if prefix is None else prefix) + '/' + LEGACY_S,)


def executable_sources():
    return tuple('fixtures/image-root' + executable_path(asset[0]) for asset in ASSETS)


def gui_sources():
    """Both adjacent runtimes are exact source keys, including duplicate bytes."""
    return tuple('fixtures/image-root' + PREFIX + '/' + directory + filename
                 for directory in ('', 'Versioned/') for filename in GUI_FILES)


def launcher_sources():
    return tuple('fixtures/native-launchers/' + desktop_id(asset[0]) for asset in ASSETS)


def runtime_sources():
    return executable_sources() + gui_sources()


def sources():
    """Active source keys relative to verified artifact root; never image-root/home."""
    return runtime_sources() + launcher_sources()


def source_destinations(home, *, prefix=None):
    """Exact source-key -> (guest path, mode), preserving nested runtime paths."""
    prefix = PREFIX if prefix is None else prefix
    image_prefix = 'fixtures/image-root' + PREFIX + '/'
    return {source: (prefix + '/' + source.removeprefix(image_prefix),
                     0o755 if source in executable_sources() else 0o644)
            for source in runtime_sources()} | {
        source: (home + '/.local/share/applications/' + source.rsplit('/', 1)[1], 0o644)
        for source in launcher_sources()}


def riley_grid_sources():
    """Same shared executables/GUI and only Riley's declared A launcher."""
    return (*runtime_sources(), launcher_sources()[0])
