"""Maintainer-script fixture paths remain confined under any temporary root."""

from pathlib import Path

import pytest

from tests.support.shell import SYSTEM_PREFIXES, relocate_system_paths


@pytest.mark.parametrize('root', ['/tmp/machine', '/var/tmp/machine',
                                 '/home/test/machine', '/var/tmp/usr/nested'])
def test_relocation_never_rewrites_inserted_root(root):
    paths = [prefix + 'fixture' for prefix in SYSTEM_PREFIXES]
    source = '\n'.join(f'test -f "{path}"' for path in paths)
    expected = '\n'.join(f'test -f "{root}{path}"' for path in paths)
    assert relocate_system_paths(source, Path(root)) == expected


def test_selected_prefixes_leave_other_source_paths_unchanged():
    source = '"/etc/fixture" "/var/fixture" "/usr/lib/fixture"'
    assert relocate_system_paths(source, '/var/tmp/machine', ('/etc/', '/usr/lib/')) == (
        '"/var/tmp/machine/etc/fixture" "/var/fixture" "/var/tmp/machine/usr/lib/fixture"')
    assert relocate_system_paths(source, '/var/tmp/machine', ()) == source
