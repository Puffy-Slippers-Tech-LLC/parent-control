"""Local builds clean only their private packaging source copy."""
import subprocess

import pytest

from tools import build_package
from tests.support.paths import ROOT


@pytest.mark.parametrize('fail', [False, True])
def test_build_isolates_cleanup_and_preserves_checkout(tmp_path, monkeypatch, fail):
    checkout = tmp_path / 'checkout'
    checkout.mkdir()
    debian = checkout / 'debian'
    debian.mkdir()
    for name in ('control', 'changelog'):
        (debian / name).write_bytes((ROOT / 'debian' / name).read_bytes())
    (checkout / 'Makefile').write_text(
        'package-source-files:\n'
        '\t@printf "%s\\n" Makefile debian/control debian/changelog\n'
        '_build-package:\n'
        '\tdh_clean\n'
        + ('\texit 7\n' if fail else
           '\tmkdir output\n'
           '\tprintf package > output/example.deb\n'
           '\tprintf metadata > output/example.changes\n'))
    protected = checkout / 'output' / 'private'
    protected.mkdir(parents=True)
    evidence = protected / 'evidence.bak'
    evidence.write_text('preserved')
    cache = checkout / 'tools' / '__pycache__'
    cache.mkdir(parents=True)
    bytecode = cache / 'test_storage.pyc'
    bytecode.write_bytes(b'preserved')
    scratch = tmp_path / 'scratch'
    scratch.mkdir()
    monkeypatch.setattr(build_package, 'scratch_directory', lambda: scratch)
    protected.chmod(0)
    cache.chmod(0o555)
    try:
        if fail:
            with pytest.raises(subprocess.CalledProcessError):
                build_package.build(checkout, 'amd64')
            assert not (checkout / 'output/example.deb').exists()
        else:
            build_package.build(checkout, 'amd64')
            assert (checkout / 'output/example.deb').read_text() == 'package'
            assert (checkout / 'output/example.changes').read_text() == 'metadata'
        assert bytecode.read_bytes() == b'preserved'
        assert list(scratch.iterdir()) == []
    finally:
        protected.chmod(0o700)
        cache.chmod(0o755)
    assert evidence.read_text() == 'preserved'
