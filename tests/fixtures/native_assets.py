"""Finite native fixture identities shared by builder and guarded preparation.

A/H/S/N are later policy roles. Preparation leaves all four Allowed.
"""
PREFIX = '/opt/onpc-test-fixtures/Applications'
ASSETS = (
    ('A', 'Exact Fixture.AppImage', 'ONPC Allowed Fixture', 'Exact native catalogue fixture', 'precise'),
    ('H', 'Path With Spaces.AppImage', 'ONPC Hard Fixture', 'Whitespace native catalogue fixture', 'precise'),
    ('S', 'Lunar Client-3.7.17.AppImage', 'ONPC Soft Fixture', 'Versioned native catalogue fixture', 'pattern'),
    ('N', 'PrismLauncher.AppImage', 'ONPC Nonmatching Fixture', 'Unrelated native catalogue fixture', 'precise'),
)
GUI_FILES = ('onpc-test-gui.py', 'gtk_automation.py')


def desktop_id(role):
    assert role in ('A', 'H', 'S', 'N')
    return 'com.puffyslippers.ONPCTest.' + role + '.desktop'


def desktop_entry(asset):
    role, filename, name, description, match = asset
    return ('[Desktop Entry]\nType=Application\n' + f'Name={name}\nComment={description}\n'
            'Icon=applications-system\n' + f'Exec="{PREFIX}/{filename}"\nTerminal=false\n')


def sources():
    """Source paths relative to the verified artifact root; never image-root/home."""
    return tuple('fixtures/image-root' + PREFIX + '/' + item
                 for item in (*[asset[1] for asset in ASSETS], *GUI_FILES)) + tuple(
                     'fixtures/native-launchers/' + desktop_id(asset[0]) for asset in ASSETS)
