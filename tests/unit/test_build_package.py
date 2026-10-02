"""Local builds clean only their private packaging source copy."""
import subprocess

import pytest

from tools import build_package
from tests.support.paths import ROOT


@pytest.mark.parametrize('status', [0, 7])
def test_updateversion_prepares_before_building_both_and_stops_on_failure(tmp_path, status):
    (tmp_path / 'tools').mkdir()
    (tmp_path / 'tools/bump_version.py').write_text(
        f'import sys\nprint("prepare", *sys.argv[1:], flush=True)\nsys.exit({status})\n')
    stub_make = tmp_path / 'make-stub'
    stub_make.write_text('#!/bin/sh\nprintf "build %s\\n" "$*"\n')
    stub_make.chmod(0o755)
    result = subprocess.run(['make', '--no-print-directory', '-f', str(ROOT / 'Makefile'),
                             'updateversion', 'PACKAGE_FORMAT=deb', f'MAKE={stub_make}'],
                            cwd=tmp_path, capture_output=True, text=True)
    assert bool(result.returncode) == bool(status), result.stderr
    assert result.stdout.splitlines() == (['prepare --latest'] if status else
        ['prepare --latest', 'build --no-print-directory build PACKAGE_FORMAT=both'])


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
           '\tmkdir -p output/deb\n'
           '\tprintf package > output/deb/example.deb\n'
           '\tprintf metadata > output/deb/example.changes\n'))
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
            assert not (checkout / 'output/deb/example.deb').exists()
        else:
            build_package.build(checkout, 'amd64')
            assert (checkout / 'output/deb/example.deb').read_text() == 'package'
            assert (checkout / 'output/deb/example.changes').read_text() == 'metadata'
        assert bytecode.read_bytes() == b'preserved'
        assert list(scratch.iterdir()) == []
    finally:
        protected.chmod(0o700)
        cache.chmod(0o755)
    assert evidence.read_text() == 'preserved'


@pytest.mark.parametrize('failure', [None, 'deb', 'rpm'])
def test_both_formats_overlap_and_share_one_frozen_generation(tmp_path, monkeypatch, failure):
    from threading import Barrier
    from tools import build_rpm

    checkout = tmp_path / 'checkout'
    checkout.mkdir()
    (checkout / 'Makefile').write_text('package-source-files:\n\t@printf "%s\\n" Makefile product\n')
    (checkout / 'product').write_text('one source generation')
    scratch = tmp_path / 'scratch'
    scratch.mkdir()
    monkeypatch.setattr(build_package, 'scratch_directory', lambda: scratch)
    overlap = Barrier(2, timeout=5)
    seen = {}

    def backend(name, root, output):
        overlap.wait()
        # A checkout edit during the build must not alter either input copy.
        (checkout / 'product').write_text('later checkout edit')
        seen[name] = ((root / 'product').read_text(), output)
        if failure == name:
            raise ValueError('injected backend failure')
        output.mkdir(parents=True, exist_ok=True)
        (output / f'package.{name}').write_text(name)

    monkeypatch.setattr(build_package, 'build',
                        lambda root, architecture, destination: backend('deb', root, destination))
    monkeypatch.setattr(build_rpm, 'build',
                        lambda root, output, release: backend('rpm', root, output))
    if failure:
        with pytest.raises(ValueError, match=f'{failure}: injected backend failure'):
            build_package.build_both(checkout, 'amd64', '0.1.dev')
    else:
        build_package.build_both(checkout, 'amd64', '0.1.dev')
    assert seen == {
        name: ('one source generation', checkout / 'output' / name)
        for name in ('deb', 'rpm')
    }
    for name in ('deb', 'rpm'):
        assert (checkout / 'output' / name / f'package.{name}').exists() == (name != failure)
    assert list(scratch.iterdir()) == []
