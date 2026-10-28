"""Contract tests for the package and fixture artifact boundary."""

from tests.support.modules import load_module
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock
import pytest


from tests.support.paths import ROOT
MODULE_PATH = ROOT / "tools/build_test_artifacts.py"
artifacts = load_module('onpc_test_build_artifacts', MODULE_PATH)


@pytest.mark.parametrize('fault', [None, 'package', 'installed-files', 'schema', 'extra-field',
                                  'full-manifest', 'alternate-package', 'symlink', 'hardlink'])
def test_package_only_input_binds_package_and_installation_metadata_without_fixture_claims(
        tmp_path, fault):
    import os
    package = tmp_path / 'package.deb'
    package.write_bytes(b'exact package')
    installed = tmp_path / 'installed-files.json'
    installed.write_text('[]\n')
    manifest = {'schema': artifacts.PACKAGE_INPUT_SCHEMA,
        'source': {'scope': 'package', 'digest_sha256': 'a' * 64},
        'artifacts': {'package': {'path': package.name, 'sha256': artifacts._sha256(package)}},
        'installed_files_sha256': artifacts._sha256(installed)}
    if fault == 'package': package.write_bytes(b'changed package')
    if fault == 'installed-files': installed.write_text('[{}]\n')
    if fault == 'schema': manifest['schema'] = 'artifact-manifest-v1'
    if fault == 'extra-field': manifest['fixtures'] = {'claim': 'complete'}
    if fault == 'full-manifest': (tmp_path / artifacts.MANIFEST_NAME).write_text('{}')
    if fault == 'alternate-package': (tmp_path / 'package.rpm').write_bytes(b'ambiguous')
    if fault in ('symlink', 'hardlink'):
        target = tmp_path / 'other'
        package.rename(target)
        if fault == 'symlink': package.symlink_to(target)
        else: os.link(target, package)
    (tmp_path / artifacts.PACKAGE_INPUT_NAME).write_text(json.dumps(manifest))
    if fault:
        with pytest.raises(artifacts.ArtifactError, match='package input verification failed'):
            artifacts.verify(tmp_path, package_only=True)
    else:
        assert artifacts.verify(tmp_path, package_only=True) == manifest
        with pytest.raises(artifacts.ArtifactError, match='artifact manifest is invalid'):
            artifacts.verify(tmp_path)
    assert not (tmp_path / 'fixtures').exists()


@pytest.mark.parametrize('flags', [[], ['--reuse'], ['--upgrade-inputs']])
def test_build_cli_requires_explicit_format_before_writing(tmp_path, monkeypatch, capsys, flags):
    output = tmp_path / 'must-not-exist'
    monkeypatch.setattr(artifacts.sys, 'argv', [str(MODULE_PATH), '--output', str(output), *flags])
    with pytest.raises(SystemExit) as failure:
        artifacts.main()
    assert failure.value.code == 2
    assert '--package-format deb|rpm is required' in capsys.readouterr().err
    assert not output.exists()


@pytest.mark.parametrize('fault', [None, 'extra', 'missing', 'empty'])
def test_rpm_public_identity_retains_epoch_release_architecture_and_digest(tmp_path, monkeypatch, fault):
    package = tmp_path / 'package.rpm'
    package.write_bytes(b'RPM payload')
    output = 'oh-no-parent-control\n2:1.3-0.1.dev.fc44\nx86_64\n'
    if fault == 'extra': output += 'extra\n'
    if fault == 'missing': output = 'oh-no-parent-control\n2:1.3\n'
    if fault == 'empty': output = 'oh-no-parent-control\n\nx86_64\n'
    run = mock.Mock(return_value=mock.Mock(stdout=output))
    monkeypatch.setattr(artifacts, '_run', run)
    if fault:
        with pytest.raises(artifacts.ArtifactError, match='package identity unavailable'):
            artifacts.package_identity(package)
    else:
        assert artifacts.package_identity(package) == {
            'name': 'oh-no-parent-control', 'version': '2:1.3-0.1.dev.fc44',
            'architecture': 'x86_64', 'sha256': artifacts._sha256(package)}
    run.assert_called_once_with(['rpm', '-qp', '--queryformat',
        '%{NAME}\n%{EPOCHNUM}:%{VERSION}-%{RELEASE}\n%{ARCH}\n', str(package)])


@pytest.mark.parametrize('new,old,newer', [
    ('0:1.10-0.1.dev.fc44', '0:1.9-0.1.dev.fc44', True),
    ('1:1.2-1.fc44', '0:9.9-1.fc44', True),
    ('0:1.3-10.fc44', '0:1.3-9.fc44', True),
    ('0:1.3~rc1-1.fc44', '0:1.3-1.fc44', False),
    ('0:1.3-1.fc44', '0:1.3-1.fc44', False),
    ('0:1.2-1.fc44', '0:1.3-1.fc44', False),
])
def test_rpm_upgrade_order_uses_native_epoch_version_release(new, old, newer):
    if newer:
        artifacts._require_newer_version(new, old, package_format='rpm')
    else:
        with pytest.raises(artifacts.ArtifactError, match='not newer'):
            artifacts._require_newer_version(new, old, package_format='rpm')


@pytest.mark.parametrize('version', ['1.3', '0:1.3-', '0:1.3-1"));os.exit(0)--'])
def test_invalid_rpm_evr_refuses_before_native_tool(monkeypatch, version):
    run = mock.Mock(side_effect=AssertionError('invalid header reached native comparator'))
    monkeypatch.setattr(artifacts, '_run', run)
    with pytest.raises(artifacts.ArtifactError, match='invalid RPM upgrade version'):
        artifacts._require_newer_version(version, '0:1.3-1.fc44', package_format='rpm')
    run.assert_not_called()


@pytest.mark.parametrize('package_format', ['deb', 'rpm'])
def test_upgrade_builder_uses_exact_format_release_without_rewriting(tmp_path, monkeypatch, package_format):
    from contextlib import contextmanager
    root = tmp_path / 'released'
    root.mkdir()
    release_calls = []
    @contextmanager
    def released_source(**kwargs):
        release_calls.append(kwargs)
        yield root
    release = artifacts.PREVIOUS_RELEASES[package_format]
    monkeypatch.setattr(artifacts, 'released_source', released_source)
    monkeypatch.setattr(artifacts.package_inputs, 'paths', lambda _: [Path('Makefile')])
    monkeypatch.setattr(artifacts.package_inputs, 'digest', lambda *_: 'digest')
    monkeypatch.setattr(artifacts, '_metadata', lambda *_: {'source': {}, 'build_inputs': {}})
    run = mock.Mock(return_value=mock.Mock(stdout='123'))
    monkeypatch.setattr(artifacts, '_run', run)
    current, previous, verify = mock.Mock(), mock.Mock(), mock.Mock()
    monkeypatch.setattr(artifacts, 'build', current)
    monkeypatch.setattr(artifacts, '_build', previous)
    monkeypatch.setattr(artifacts, 'verify_upgrade', verify)
    output = tmp_path / 'output'
    artifacts.build_upgrade(output, package_format=package_format)
    current.assert_called_once_with(output / 'current', package_format=package_format)
    assert release_calls == [{'package_format': package_format}]
    args, kwargs = previous.call_args
    assert args[1] == root
    assert args[4]['source']['revision'] == release['commit']
    assert args[4]['source']['release_tag'] == release['tag']
    assert kwargs == {'package_format': package_format}
    run.assert_called_once_with(['git', 'show', '-s', '--format=%ct', release['commit']], cwd=ROOT)
    verify.assert_called_once_with(output)


def write_artifact(directory: Path, *, package_bytes: bytes = b"package", fixture_digest: str = "fixture") -> None:
    package = directory / "package/oh-no-parent-control_1_amd64.deb"
    package.parent.mkdir(parents=True)
    package.write_bytes(package_bytes)
    fixtures = directory / "fixtures"
    fixtures.mkdir()
    (fixtures / "SHA256SUMS.json").write_text(
        json.dumps({"algorithm": "sha256", "files": {"payload": fixture_digest}}, sort_keys=True),
        encoding="utf-8",
    )
    (directory / artifacts.MANIFEST_NAME).write_text(
        json.dumps(
            {
                "schema_version": artifacts.SCHEMA_VERSION,
                "source": {"revision": "a" * 40, "digest_sha256": "b" * 64, "file_count": 1},
                "build_inputs": {"source_date_epoch": 1, "architecture": "amd64", "deb_build_options": "nocheck", "package_command": ["dpkg-buildpackage"]},
                "tools": {},
                "artifacts": {
                    "package": {"path": "package/oh-no-parent-control_1_amd64.deb", "sha256": artifacts._sha256(package)},
                    "fixtures": {"path": "fixtures", "digest_manifest": "fixtures/SHA256SUMS.json", "sha256": artifacts._fixture_digest(fixtures)},
                },
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )


class TestBuildTestArtifacts(unittest.TestCase):
    def test_output_must_be_empty_and_outside_checkout(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "output"
            self.assertEqual(artifacts._require_empty_output(output), output)
            (output / "occupied").write_text("x", encoding="utf-8")
            with self.assertRaises(artifacts.ArtifactError):
                artifacts._require_empty_output(output)
        with self.assertRaises(artifacts.ArtifactError):
            artifacts._require_empty_output(ROOT / "artifacts/test-package")

    def test_build_copies_the_recorded_source_to_a_private_tree_and_writes_manifest(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "output"
            metadata = {
                "source": {"revision": "a" * 40, "digest_sha256": "b" * 64, "file_count": 1},
                "build_inputs": {"source_date_epoch": 1, "architecture": "amd64", "deb_build_options": "nocheck", "package_command": ["dpkg-buildpackage"]},
                "tools": {"flatpak": "Flatpak 1"},
            }

            def fake_run(command, *, cwd=None, environment=None):
                if command == ["dpkg-buildpackage"]:
                    self.assertNotEqual(cwd, ROOT)
                    self.assertTrue((cwd / "README.md").is_file())
                    (cwd.parent / "oh-no-parent-control_1_amd64.deb").write_bytes(b"package")
                elif str(artifacts.FIXTURE_BUILDER) in command:
                    fixture_output = Path(command[-1])
                    fixture_output.mkdir()
                    (fixture_output / "SHA256SUMS.json").write_text(
                        json.dumps({"algorithm": "sha256", "files": {"payload": "fixture"}}), encoding="utf-8"
                    )
                return subprocess.CompletedProcess(command, 0, "", "")

            with mock.patch.object(artifacts.package_inputs, "paths", return_value=[Path("README.md")]), \
                 mock.patch.object(artifacts.package_inputs, "digest", return_value="b" * 64), \
                 mock.patch.object(artifacts, "_metadata", return_value=metadata), \
                 mock.patch.object(artifacts, "_run", side_effect=fake_run):
                manifest_path = artifacts.build(output, package_format='deb')

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["source"], metadata["source"])
            self.assertEqual(manifest["artifacts"]["package"]["path"], "package/oh-no-parent-control_1_amd64.deb")
            self.assertEqual(manifest["artifacts"]["fixtures"]["digest_manifest"], "fixtures/SHA256SUMS.json")

    def test_verify_rejects_tampered_package_and_compare_requires_equal_builds(self):
        with tempfile.TemporaryDirectory() as temporary:
            first = Path(temporary) / "first"
            second = Path(temporary) / "second"
            first.mkdir()
            second.mkdir()
            write_artifact(first)
            write_artifact(second)
            with mock.patch.object(artifacts, "_run", return_value=subprocess.CompletedProcess([], 0, "", "")):
                artifacts.compare(first, second)
            package = first / "package/oh-no-parent-control_1_amd64.deb"
            package.write_bytes(b"changed")
            with self.assertRaises(artifacts.ArtifactError):
                artifacts.verify(first)


if __name__ == "__main__":
    unittest.main()


def test_development_only_commit_preserves_package_metadata(tmp_path, monkeypatch):
    def git(*args):
        return subprocess.run(['git', '-c', 'user.name=Tests', '-c',
                               'user.email=tests@invalid', '-c', 'commit.gpgsign=false', *args],
                              cwd=tmp_path, check=True, capture_output=True)

    git('init', '-q')
    (tmp_path / 'product').write_text('product input\n')
    git('add', 'product')
    git('commit', '-qm', 'Product')
    monkeypatch.setattr(artifacts, 'REPOSITORY', tmp_path)
    monkeypatch.setattr(artifacts, '_command_version', lambda command: 'tool-version')
    before = artifacts._metadata([Path('product')], 'digest')
    (tmp_path / 'docs').mkdir()
    (tmp_path / 'docs/internal.md').write_text('development-only\n')
    git('add', 'docs/internal.md')
    git('commit', '-qm', 'Documentation')
    assert artifacts._metadata([Path('product')], 'digest') == before


def test_rpm_build_uses_frozen_source_and_records_exact_artifact(tmp_path, monkeypatch):
    from tools import build_rpm
    metadata = {'source': {'revision': 'a' * 40},
                'build_inputs': {'source_date_epoch': 1, 'deb_build_options': 'nocheck'}, 'tools': {}}
    monkeypatch.setattr(artifacts.package_inputs, 'paths', lambda _: [Path('README.md')])
    monkeypatch.setattr(artifacts.package_inputs, 'digest', lambda *_: 'digest')
    monkeypatch.setattr(artifacts, '_metadata', lambda *_: metadata)
    calls = []
    def rpm(source, output):
        assert source != ROOT and (source / 'README.md').read_bytes() == (ROOT / 'README.md').read_bytes()
        calls.append(source)
        output.mkdir()
        (output / 'oh-no-parent-control-1.2-0.1.dev.fc44.x86_64.rpm').write_bytes(b'rpm package')
        (output / 'oh-no-parent-control-debuginfo-1.2-0.1.dev.fc44.x86_64.rpm').write_bytes(b'debug')
    def fixture(command, **kwargs):
        assert str(artifacts.FIXTURE_BUILDER) in command
        output = Path(command[-1])
        output.mkdir()
        (output / 'SHA256SUMS.json').write_text(json.dumps({'algorithm': 'sha256', 'files': {}}))
    monkeypatch.setattr(build_rpm, 'build', rpm)
    monkeypatch.setattr(artifacts, '_run', fixture)
    output = tmp_path / 'output'
    artifacts.build(output, package_format='rpm')
    record = artifacts.verify(output)
    assert len(calls) == 1
    assert record['build_inputs']['package_format'] == 'rpm'
    package = output / record['artifacts']['package']['path']
    assert package.read_bytes() == b'rpm package'
    package.write_bytes(b'tampered rpm')
    with pytest.raises(artifacts.ArtifactError, match='package artifact digest'):
        artifacts.verify(output)
