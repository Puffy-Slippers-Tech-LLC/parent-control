"""Package identity: private archives and bounded read-only dpkg children only."""

import hashlib
import json
import tarfile
import time
from types import SimpleNamespace
from unittest.mock import Mock
import xml.etree.ElementTree as ET

import pytest

import package_content
from owned_commands import Commands
from tests.support.deb_archive import tar_bytes, write_package


def test_rpm_reuse_requires_exact_archive_bytes(tmp_path):
    package = tmp_path / 'product.rpm'
    package.write_bytes(b'RPM header and payload')
    commands = Mock()
    original = package_content.digest(package, commands)
    assert original == hashlib.sha256(package.read_bytes()).hexdigest()
    package.write_bytes(b'changed RPM header and payload')
    assert package_content.digest(package, commands) != original
    commands.run.assert_not_called()


def test_rebuilt_archives_ignore_container_timestamp_compression_and_order(tmp_path):
    first = write_package(tmp_path / 'first.deb', mtime=1)
    second = write_package(tmp_path / 'second.deb', mtime=1000, compression='xz', reverse=True)
    assert first.read_bytes() != second.read_bytes()
    assert package_content.digest(first, Commands()) == package_content.digest(second, Commands())


@pytest.mark.parametrize('change', [
    {'data': b'changed'}, {'name': 'other'}, {'mode': 0o600},
    {'uid': 42}, {'gid': 42}, {'uname': 'other'}, {'gname': 'other'},
    {'pax_headers': {'SCHILY.xattr.security.capability': 'different'}},
])
def test_payload_bytes_names_permissions_ownership_and_extended_metadata_matter(change):
    entry = {'name': 'product', 'data': b'original'}
    first = package_content.archive_digest(tar_bytes([entry]))
    second = package_content.archive_digest(tar_bytes([entry | change]))
    assert first != second


@pytest.mark.parametrize('entry', [
    {'name': 'directory', 'type': tarfile.DIRTYPE, 'mode': 0o755},
    {'name': 'symlink', 'type': tarfile.SYMTYPE, 'linkname': 'file'},
    {'name': 'hardlink', 'type': tarfile.LNKTYPE, 'linkname': 'file'},
])
def test_directory_permissions_and_link_targets_matter(entry):
    entries = [{'name': 'file', 'data': b'same'}, {'name': 'other', 'data': b'same'}, entry]
    first = package_content.archive_digest(tar_bytes(entries))
    change = {'mode': 0o700} if entry['type'] == tarfile.DIRTYPE else {'linkname': 'other'}
    assert first != package_content.archive_digest(tar_bytes(entries[:-1] + [entry | change]))


def test_tar_and_pax_timestamps_are_ignored_but_additions_and_removals_are_not():
    entry = {'name': 'file', 'data': b'bytes'}
    first = package_content.archive_digest(tar_bytes([entry], mtime=1))
    changed = entry | {'pax_headers': {'mtime': '2000.1', 'atime': '2001', 'ctime': '2002'}}
    assert first == package_content.archive_digest(tar_bytes([changed], mtime=2000))
    assert first != package_content.archive_digest(tar_bytes([entry, {'name': 'extra'}]))


@pytest.mark.parametrize('name', ['control', 'postinst', 'preinst', 'postrm', 'prerm',
                                 'conffiles', 'triggers', 'md5sums'])
def test_every_control_file_is_significant_even_with_identical_payload(tmp_path, name):
    original = [{'name': 'control', 'data': b'Package: example\nVersion: 1.1\nArchitecture: all\n'}]
    control = original if name == 'control' else original + [{'name': name, 'data': b'original'}]
    modified = [entry | {'data': entry['data'] + b'changed\n'} if entry['name'] == name
                else entry for entry in control]
    first = write_package(tmp_path / 'first.deb', control=control)
    second = write_package(tmp_path / 'second.deb', control=modified)
    assert package_content.digest(first, Commands()) != package_content.digest(second, Commands())


@pytest.mark.parametrize('field', ['Version', 'Architecture', 'Depends'])
def test_package_identity_and_dependencies_are_significant(tmp_path, field):
    control = b'Package: example\nVersion: 1.1\nArchitecture: all\nDepends: libc6\n'
    first = write_package(tmp_path / 'first.deb', control=[{'name': 'control', 'data': control}])
    lines = control.decode().splitlines()
    modified = '\n'.join(line + '-changed' if line.startswith(field + ':') else line
                         for line in lines).encode() + b'\n'
    second = write_package(tmp_path / 'second.deb', control=[{'name': 'control', 'data': modified}])
    assert package_content.digest(first, Commands()) != package_content.digest(second, Commands())


@pytest.mark.parametrize('entries,category', [
    ([{'name': '../escape'}], 'invalid-path'),
    ([{'name': '/absolute'}], 'invalid-path'),
    ([{'name': 'same'}, {'name': './same'}], 'duplicate-path'),
    ([{'name': 'fifo', 'type': tarfile.FIFOTYPE}], 'unsupported-member'),
    ([{'name': '.'}], 'invalid-root'),
    ([{'name': 'parent', 'type': tarfile.SYMTYPE, 'linkname': 'other'},
      {'name': 'parent/child'}], 'non-directory-ancestor'),
    ([{'name': 'link', 'type': tarfile.LNKTYPE, 'linkname': 'missing'}], 'invalid-hardlink'),
    ([], 'empty-archive'),
])
def test_ambiguous_or_unsupported_members_cannot_authorize_reuse(entries, category):
    with pytest.raises(ValueError, match='package-content:' + category):
        package_content.archive_digest(tar_bytes(entries))


def test_invalid_or_truncated_archive_is_refused():
    for raw in (b'not a tar', tar_bytes([{'name': 'large', 'data': b'x' * 1024}])[:700]):
        with pytest.raises(ValueError, match='package-content:invalid-archive'):
            package_content.archive_digest(raw)


def test_installed_compressed_asset_bytes_are_not_normalized():
    # Only Debian container metadata may differ. A packaged zip/gzip itself is
    # installed bytes and must keep the same fingerprint as its exact content.
    first = tar_bytes([{'name': 'asset.gz', 'data': b'first compressed asset'}])
    second = tar_bytes([{'name': 'asset.gz', 'data': b'second compressed asset'}])
    assert package_content.archive_digest(first) != package_content.archive_digest(second)


def test_package_sized_comparison_reports_elapsed_time(tmp_path):
    # A few MiB of incompressible data spread across the current package's scale
    # of files. No compiler, shared build cache, VM or installed product.
    payload = hashlib.shake_256(b'package-content benchmark').digest(32768)
    entries = [{'name': f'usr/share/example/{index}', 'data': payload} for index in range(160)]
    first = write_package(tmp_path / 'first.deb', data=entries, mtime=1)
    second = write_package(tmp_path / 'second.deb', data=entries, mtime=100, reverse=True)
    started = time.monotonic()
    assert package_content.digest(first, Commands()) == package_content.digest(second, Commands())
    print(f'Normalized comparison of two 5 MiB packages: {time.monotonic() - started:.3f}s')


def snapshot_xml(identity):
    tree = ET.Element('domainsnapshot')
    ET.SubElement(tree, 'description').text = identity
    return ET.tostring(tree, encoding='unicode')


def test_snapshot_identity_refuses_crossed_preparation_and_changed_upgrade_inputs(tmp_path, monkeypatch):
    import app_snapshot
    import build_test_artifacts
    package = write_package(tmp_path / 'package.deb')
    lease = SimpleNamespace(capture=SimpleNamespace(state={'guest': {'ubuntu_version': '26.04'}}),
                            state={'baseline_sha256': 'a' * 64})
    bundle = SimpleNamespace(root=tmp_path, digest=lambda _: 'b' * 64)
    pair = {'packages': {'previous': {'sha256': 'c' * 64}}}
    monkeypatch.setattr(build_test_artifacts, 'verify_upgrade', Mock(return_value=pair))
    fresh = app_snapshot.input_identity(lease, tmp_path, bundle, Commands())
    upgraded = app_snapshot.input_identity(lease, tmp_path, bundle, Commands(),
                                           release_notes_upgrade=True)
    assert app_snapshot.mismatch(snapshot_xml(fresh), fresh) is None
    assert app_snapshot.mismatch(snapshot_xml(upgraded), upgraded) is None
    assert app_snapshot.mismatch(snapshot_xml(fresh), upgraded) == 'snapshot preparation changed'
    assert app_snapshot.mismatch(snapshot_xml(upgraded), fresh) == 'snapshot preparation changed'
    for key in ('previous_package_sha256', 'package_sha256'):
        changed = json.loads(upgraded)
        changed[key] = 'd' * 64
        assert app_snapshot.mismatch(snapshot_xml(json.dumps(changed)), upgraded) == 'upgrade package inputs changed'
    # Ordinary captures keep their established installed-content equivalence.
    changed = json.loads(fresh)
    changed['package_sha256'] = 'd' * 64
    assert app_snapshot.mismatch(snapshot_xml(json.dumps(changed)), fresh) is None
    assert package.is_file()


def test_suite_prepares_fresh_state_when_an_ordinary_case_follows_upgrade():
    from suite_lease import Suite
    suite = Suite(Mock())
    suite.lease = Mock()
    suite.lease.capture.state = {'proof': {'name': 'onpc_baseline'}}
    suite.lease._restored_name = 'onpc_baseline'
    suite.lease.installed_online = True
    suite.prepared = True
    suite.prepared_release_notes_upgrade = True
    suite.prepare_installed = Mock(return_value=True)
    suite.prepare_case({'preconditions': ['installed-digest-verified-product']},
                       Mock(), Mock(), {}, root=Mock())
    assert suite.prepare_installed.call_args.kwargs['release_notes_upgrade'] is False
    assert suite.prepared_release_notes_upgrade is False
    assert suite.lease.online_pending is True
