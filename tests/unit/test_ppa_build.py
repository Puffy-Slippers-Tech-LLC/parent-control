"""Exact source input authentication and retained clean-build failure evidence."""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools.publishing import build as ppa_build


@pytest.fixture
def release(tmp_path, monkeypatch):
    root = tmp_path / 'source'
    root.mkdir()
    version = '1.0+ppa6~ubuntu26.04.1'
    prefix = f'oh-no-parent-control_{version}'
    content = b'archive bytes'
    (tmp_path / f'{prefix}.tar.xz').write_bytes(content)
    (tmp_path / f'{prefix}.dsc').write_text(
        'Format: 3.0 (native)\nSource: oh-no-parent-control\n'
        f'Version: {version}\nChecksums-Sha256:\n '
        f'{hashlib.sha256(content).hexdigest()} {len(content)} {prefix}.tar.xz\n')
    monkeypatch.setattr(ppa_build.subprocess, 'check_output',
                        lambda argv, **kw: 'amd64' if '--print-architecture' in argv else version)
    return root, prefix


def test_source_archive_tampering_is_refused(release):
    root, prefix = release
    ppa_build.source_inputs(root)
    (root.parent / f'{prefix}.tar.xz').write_bytes(b'changed bytes')
    with pytest.raises(ValueError, match='checksum mismatch'):
        ppa_build.source_inputs(root)


@pytest.mark.parametrize('replacement', ['../../etc/shadow', 'other.tar.xz'])
def test_manifest_cannot_select_other_files(release, replacement):
    root, prefix = release
    dsc = root.parent / f'{prefix}.dsc'
    dsc.write_text(dsc.read_text().replace(f'{prefix}.tar.xz', replacement))
    with pytest.raises(ValueError, match='manifest'):
        ppa_build.source_inputs(root)


def test_missing_tools_stop_before_creating_attempt(release, monkeypatch):
    root, _ = release
    monkeypatch.setattr(ppa_build.shutil, 'which', lambda *a, **kw: None)
    monkeypatch.setattr(ppa_build.tempfile, 'mkdtemp', lambda **kw: pytest.fail('attempt created'))
    with pytest.raises(ValueError, match='setup.sh --ppa-build-tools'):
        ppa_build.check_build(root)


@pytest.mark.parametrize('exit_code,artifacts', [(1, False), (0, False), (0, True)])
def test_result_requires_binary_output_and_host_options_do_not_disable_tests(release, tmp_path, monkeypatch, exit_code, artifacts):
    root, prefix = release
    attempt = tmp_path / 'attempt'
    attempt.mkdir()
    monkeypatch.setattr(ppa_build.shutil, 'which', lambda *a, **kw: '/usr/bin/tool')
    monkeypatch.setattr(ppa_build.tempfile, 'mkdtemp', lambda **kw: str(attempt))
    original_exists = Path.exists
    original_read = Path.read_text
    monkeypatch.setattr(Path, 'exists', lambda path: True if str(path) == '/etc/sbuild/sbuild.conf' else original_exists(path))
    monkeypatch.setattr(Path, 'read_text', lambda path, *a, **kw:
                        '# packaged default\n1;\n' if str(path) == '/etc/sbuild/sbuild.conf' else original_read(path, *a, **kw))
    monkeypatch.setenv('DEB_BUILD_OPTIONS', 'nocheck')
    monkeypatch.setenv('SBUILD_CONFIG', '/tmp/arbitrary-hook')
    monkeypatch.setenv('APT_PACKAGE_PRIVATE_KEY_PASSPHRASE', 'test-secret')

    def fail(argv, **kwargs):
        assert argv[0] == '/usr/bin/sbuild'
        assert '--chroot-mode=unshare' in argv and '--no-enable-network' in argv
        assert '--no-clean-source' in argv
        assert kwargs['env']['DEB_BUILD_OPTIONS'] == 'parallel=2'
        assert 'APT_PACKAGE_PRIVATE_KEY_PASSPHRASE' not in kwargs['env']
        assert kwargs['env']['SBUILD_CONFIG'] == str(attempt / 'config/sbuild/config.pl')
        assert Path(argv[-1]).read_bytes() == (root.parent / f'{prefix}.dsc').read_bytes()
        kwargs['stdout'].write('missing build dependency\n')
        if artifacts:
            for extension in ('deb', 'changes'):
                (attempt / 'output' / f'{prefix}_amd64.{extension}').write_bytes(b'binary evidence')
        return SimpleNamespace(returncode=exit_code)

    monkeypatch.setattr(ppa_build.subprocess, 'run', fail)
    if artifacts:
        ppa_build.check_build(root)
    else:
        with pytest.raises(ValueError, match='build'):
            ppa_build.check_build(root)
    report = json.loads((attempt / 'result.json').read_text())
    assert report['status'] == ('passed' if artifacts else 'failed')
    assert report['exit_code'] == exit_code
    if artifacts:
        assert report['output_sha256'][f'{prefix}_amd64.deb'] == hashlib.sha256(b'binary evidence').hexdigest()
    assert (attempt / 'build.log').read_text() == 'missing build dependency\n'
    assert (attempt / 'input' / f'{prefix}.dsc').is_file()
