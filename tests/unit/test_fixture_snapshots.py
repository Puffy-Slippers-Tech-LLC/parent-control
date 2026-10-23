"""Fault injection mutates private package copies without following links."""

import json
from unittest.mock import Mock

import pytest

import fixture_snapshot_qualification as qualification


@pytest.mark.parametrize('link', [False, True])
def test_product_byte_probe_repacks_private_copy_and_refuses_links(tmp_path, link):
    assets = tmp_path / 'original'
    assets.mkdir()
    (assets / 'package.deb').write_bytes(b'original archive')
    target = '/usr/lib/oh-no-parent-control/common/oh_no_parent_control_ui/duration.py'
    (assets / 'installed-files.json').write_text(json.dumps([
        {'path': target, 'kind': 'file'}]))
    external = tmp_path / 'untouched'
    external.write_bytes(b'original product bytes')
    def package_command(argv, **kwargs):
        if argv[1] == '--raw-extract':
            destination = qualification.Path(argv[3]) / target.removeprefix('/')
            destination.parent.mkdir(parents=True)
            if link:
                destination.symlink_to(external)
            else:
                destination.write_bytes(external.read_bytes())
        else:
            assert argv[1] == '--build'
            root = qualification.Path(argv[2])
            qualification.Path(argv[3]).write_bytes(
                (root / target.removeprefix('/')).read_bytes())
        return b''
    commands = Mock()
    commands.run.side_effect = package_command
    if link:
        with pytest.raises(Exception, match='unsafe-product-copy'):
            qualification.changed_product(tmp_path, assets, commands)
        assert commands.run.call_count == 1
    else:
        changed = qualification.changed_product(tmp_path, assets, commands)
        assert (changed / 'package.deb').read_bytes() != external.read_bytes()
        assert commands.run.call_args.args[0][1] == '--build'
        assert commands.run.call_count == 2
    assert external.read_bytes() == b'original product bytes'
    assert (assets / 'package.deb').read_bytes() == b'original archive'


def test_product_probe_refuses_non_regular_manifest_before_package_commands(tmp_path):
    (tmp_path / 'installed-files.json').write_text(json.dumps([{
        'path': '/usr/lib/oh-no-parent-control/common/oh_no_parent_control_ui/duration.py',
        'kind': 'symlink'}]))
    commands = Mock()
    with pytest.raises(Exception, match='product-mutation-target'):
        qualification.changed_product(tmp_path, tmp_path, commands)
    commands.run.assert_not_called()


def test_rpm_identity_probe_changes_only_private_archive_bytes(tmp_path):
    import package_content
    assets = tmp_path / 'original'
    assets.mkdir()
    package = assets / 'package.rpm'
    original = b'actual frozen package bytes\x12'
    package.write_bytes(original)
    before = package.stat()
    commands = Mock()
    changed = qualification.changed_product(tmp_path, assets, commands, 'fedora')
    assert (changed / 'package.rpm').read_bytes() == original[:-1] + b'\x13'
    assert package.read_bytes() == original
    after = package.stat()
    assert (before.st_ino, before.st_size, before.st_mtime_ns) == (after.st_ino, after.st_size, after.st_mtime_ns)
    assert package_content.digest(package, commands) != package_content.digest(changed / 'package.rpm', commands)
    commands.run.assert_not_called()
