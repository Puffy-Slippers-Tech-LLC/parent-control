"""The finite, system-wide Snap fixtures. A/H/S name later policy roles.

All three start Allowed; preparation never seeds product policy.
"""
BASE = 'core26'
VERSION = '1'
ASSETS = (
    ('A', 'onpc-fixture-allowed', 'ONPC Snap Allowed Fixture'),
    ('H', 'onpc-fixture-hard', 'ONPC Snap Hard Fixture'),
    ('S', 'onpc-fixture-soft', 'ONPC Snap Soft Fixture'),
)


def packages():
    return tuple(name + '.snap' for _, name, _ in ASSETS)


def desktop_id(name):
    assert name in {item[1] for item in ASSETS}
    return name + '_' + name + '.desktop'


def metadata(name, architecture):
    assert name in {item[1] for item in ASSETS} | {'onpc-test-application'}
    assert architecture in ('amd64', 'arm64')
    return (f'name: {name}\nversion: "{VERSION}"\nsummary: Deterministic ONPC GUI fixture\n'
        'description: Offline public accessibility application and game fixture.\n'
        f'architectures: [{architecture}]\nbase: {BASE}\ngrade: devel\nconfinement: strict\n'
        f'apps:\n  {name}:\n    command: bin/gui\n'
        '    plugs: [desktop, desktop-legacy, wayland, x11]\n')
