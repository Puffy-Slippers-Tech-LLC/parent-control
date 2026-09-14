"""Strict unattended source verification rejects omissions, changed modes and paths."""
import hashlib
import io
from pathlib import Path
import subprocess
import tarfile
from types import SimpleNamespace

import pytest

from tools.publishing import source as release


def test_package_version_maps_to_valid_git_tag():
    tag = release.source_tag('1.0+ppa1~ubuntu26.04.1')
    assert tag == 'v1.0+ppa1_ubuntu26.04.1'
    subprocess.run(['git', 'check-ref-format', f'refs/tags/{tag}'], check=True)


def test_revision_skips_used_versions_and_ignores_other_series():
    assert release.next_version('1.0', [
        '1.0+ppa2~ubuntu26.04.1', '1.0+ppa9~ubuntu24.04.1',
        '2.0+ppa8~ubuntu26.04.1']) == '1.0+ppa3~ubuntu26.04.1'
    with pytest.raises(ValueError):
        release.next_version('1.0; command', [])


def test_wrong_source_signer_is_rejected(monkeypatch):
    monkeypatch.setattr(release, 'run', lambda *args, **kwargs:
                        '[GNUPG:] VALIDSIG WRONG 2026 0 0 4 0 1 10 00 WRONG')
    with pytest.raises(ValueError, match='publisher'):
        release.verify_signature(Path('source.dsc'), Path('/tmp'))


@pytest.mark.parametrize('case,reason', [
    ('valid', None), ('mode', 'executable mode'), ('omission', 'excludes tracked'),
    ('bytes', 'differs from signed'), ('path', 'unsafe source archive'),
    ('development', 'unexpected/duplicate archive member'),
    ('signer', 'signature does not belong'), ('duplicate-field', 'changes Source'),
    ('duplicate-manifest', 'SHA-256 manifest'), ('checksum', 'checksum mismatch'),
])
def test_strict_archive_and_tag_checks(tmp_path, monkeypatch, case, reason):
    root = tmp_path / 'source'
    root.mkdir()
    version = '1.1+ppa1~ubuntu26.04.1'
    prefix = f'{release.PACKAGE}_{version}'
    archive = tmp_path / f'{prefix}.tar.xz'
    with tarfile.open(archive, 'w:xz') as stream:
        info = tarfile.TarInfo('root/tool')
        info.mode = 0o644 if case == 'mode' else 0o755
        payload = b'changed' if case == 'bytes' else b'executable source\n'
        info.size = len(payload)
        stream.addfile(info, io.BytesIO(payload))
        if case == 'development':
            info = tarfile.TarInfo('root/docs/internal.md')
            stream.addfile(info, io.BytesIO(b''))
        if case == 'path':
            info = tarfile.TarInfo('root/../escape')
            info.type = tarfile.DIRTYPE
            stream.addfile(info)
    dsc = tmp_path / f'{prefix}.dsc'
    dsc.write_bytes(b'signed DSC fixture')
    manifest = ''.join(f' {hashlib.sha256(path.read_bytes()).hexdigest()} {path.stat().st_size} {path.name}\n'
                       for path in (dsc, archive))
    content = (f'Source: {release.PACKAGE}\nVersion: {version}\nArchitecture: source\n'
               f'Distribution: resolute\nChecksums-Sha256:\n{manifest}')
    if case == 'duplicate-field':
        content += f'Source: {release.PACKAGE}\n'
    if case == 'duplicate-manifest':
        content += f'Checksums-Sha256:\n{manifest}'
    (tmp_path / f'{prefix}_source.changes').write_text(content)
    if case == 'checksum':
        dsc.write_bytes(b'tampered DSC')

    def run(*args, **kwargs):
        if args[:2] == ('dpkg-parsechangelog', '-S'):
            return version if args[2] == 'Version' else 'resolute'
        if args[:3] == ('git', 'ls-files', '--stage'):
            return '100755 blob 0\ttool\n100644 blob 0\t.codex/config'
        if args[:2] == ('git', 'ls-files'):
            return 'tool\n.codex/config' + ('\nmissing-source' if case == 'omission' else '')
        return ''

    def external(args, **kwargs):
        if 'verify-tag' in args:
            key = 'wrong' if case == 'signer' else release.KEY
            return SimpleNamespace(stderr=f'[GNUPG:] VALIDSIG {key} 2026 0 0 4 0 1 10 00 {key}')
        pytest.fail('source integrity verification must not run local test commands')

    monkeypatch.setattr(release, 'run', run)
    monkeypatch.setattr(release.package_inputs, 'paths', lambda root:
                        [Path('tool')] + ([Path('missing-source')] if case == 'omission' else []))
    monkeypatch.setattr(release, 'verify_signature', lambda *args: None)
    monkeypatch.setattr(release.subprocess, 'run', external)
    monkeypatch.setattr(release.subprocess, 'check_output', lambda *args, **kwargs: b'executable source\n')
    if reason:
        with pytest.raises(ValueError, match=reason):
            release.inspect(root)
    else:
        release.inspect(root)
        assert (tmp_path / 'source-review.json').exists()


def test_publisher_builds_source_from_only_declared_inputs(tmp_path):
    root = tmp_path / 'source'
    root.mkdir()
    (root / 'Makefile').write_text('package-source-files:\n\t@printf "%s\\n" Makefile product\n')
    (root / 'product').write_text('product bytes\n')
    for category in ('docs', 'tests', 'tools'):
        (root / category).mkdir()
        (root / category / 'unused').write_text('internal\n\n')
    calls = []

    def command(*args, cwd, **kwargs):
        calls.append(args)
        assert cwd != root and cwd.parent == root.parent
        assert {p.name for p in cwd.iterdir()} == {'Makefile', 'product'}
        assert (cwd / 'product').read_bytes() == (root / 'product').read_bytes()

    release.build_archive(root, command, tmp_path / 'log')
    assert len(calls) == 1 and calls[0][0] == 'dpkg-buildpackage'
    assert (root / 'docs/unused').exists()
