"""Local builds clean only their private packaging source copy."""
import os
import subprocess

import pytest

from tools import build_package, deb_builder
from tests.support.paths import ROOT


@pytest.mark.parametrize('distribution', ['ubuntu', 'fedora', '"fedora"', "'fedora'"])
@pytest.mark.parametrize('override', [None, 'deb', 'rpm', 'both'])
def test_default_builds_both_formats_on_every_host_and_can_be_overridden(tmp_path, distribution, override):
    release = tmp_path / 'os-release'
    release.write_text(f'ID={distribution}\n')
    result = subprocess.run(['make', '--no-print-directory', '-n', '-f', str(ROOT / 'Makefile'),
                             'build', f'OS_RELEASE={release}',
                             *([f'PACKAGE_FORMAT={override}'] if override else [])],
                            cwd=ROOT, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert f'--format "{override or "both"}"' in result.stdout
    assert '--disk-queue never' in result.stdout
    assert len(result.stdout.splitlines()) == 1


@pytest.mark.parametrize('status', [0, 7])
def test_updateversion_prepares_before_building_selected_format_and_stops_on_failure(tmp_path, status):
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
        ['prepare --latest', 'build --no-print-directory build PACKAGE_FORMAT=deb'])


@pytest.mark.parametrize('fail', [False, True])
def test_build_isolates_cleanup_and_preserves_checkout(tmp_path, monkeypatch, fail):
    monkeypatch.setattr(deb_builder, 'native_debian', lambda: True)
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
            assert not (checkout / 'output/deb/ubuntu26.04/x86_64/example.deb').exists()
        else:
            build_package.build(checkout, 'amd64')
            assert (checkout / 'output/deb/ubuntu26.04/x86_64/example.deb').read_text() == 'package'
            assert (checkout / 'output/deb/ubuntu26.04/x86_64/example.changes').read_text() == 'metadata'
        assert bytecode.read_bytes() == b'preserved'
        assert list(scratch.iterdir()) == []
    finally:
        protected.chmod(0o700)
        cache.chmod(0o755)
    assert evidence.read_text() == 'preserved'


@pytest.mark.parametrize('failure', [None, 'ubuntu26.04', 'fedora45'])
def test_both_formats_overlap_and_share_one_frozen_generation(tmp_path, monkeypatch, failure):
    from threading import Barrier
    from tools import build_rpm, build_targets

    checkout = tmp_path / 'checkout'
    checkout.mkdir()
    (checkout / 'Makefile').write_text('package-source-files:\n\t@printf "%s\\n" Makefile product\n')
    (checkout / 'product').write_text('one source generation')
    scratch = tmp_path / 'scratch'
    scratch.mkdir()
    monkeypatch.setattr(build_package, 'scratch_directory', lambda: scratch)
    targets = tuple(build_targets.TARGETS.values())
    monkeypatch.setattr(build_targets, 'configured', lambda _: targets)
    overlap = Barrier(3, timeout=5)
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
                        lambda root, architecture, destination, target, **_cancel: backend(target, root, destination))
    monkeypatch.setattr(build_rpm, 'build',
                        lambda root, output, release, target, **_lifetime: backend(target, root, output))
    if failure:
        with pytest.raises(ValueError, match=f'{failure}/x86_64: injected backend failure'):
            build_package.build_both(checkout, 'amd64', '0.1.dev', disk_queue=False)
    else:
        build_package.build_both(checkout, 'amd64', '0.1.dev', disk_queue=False)
    assert seen == {
        target.name: ('one source generation', target.output(checkout))
        for target in targets
    }
    for target in targets:
        assert (target.output(checkout) / f'package.{target.name}').exists() == (target.name != failure)
    assert list(scratch.iterdir()) == []


def test_deb_builder_fingerprint_tracks_build_requirements_and_recipe(tmp_path):
    (tmp_path / 'debian').mkdir()
    recipe = tmp_path / 'debian/Containerfile'
    recipe.write_bytes((ROOT / 'debian/Containerfile').read_bytes())
    control = tmp_path / 'debian/control'
    original = (ROOT / 'debian/control').read_text()
    control.write_text(original)
    first = deb_builder.inputs(tmp_path)[2]
    control.write_text(original.replace('accountsservice', 'accountsservice (>= 1)'))
    assert deb_builder.inputs(tmp_path)[2] == first
    control.write_text(original.replace('Build-Depends:\n', 'Build-Depends:\n extra-tool,\n'))
    assert deb_builder.inputs(tmp_path)[2] != first
    control.write_text(original)
    recipe.write_text(recipe.read_text() + '\n# new recipe\n')
    assert deb_builder.inputs(tmp_path)[2] != first


@pytest.mark.parametrize('status', [0, 7])
def test_deb_setup_uses_only_metadata_and_stops_on_failure(tmp_path, monkeypatch, status):
    from pathlib import Path

    monkeypatch.setattr(deb_builder, 'scratch_directory', lambda: tmp_path)
    monkeypatch.setattr(deb_builder, 'scratch_descriptors', lambda: ())
    monkeypatch.setattr(deb_builder.shutil, 'which', lambda _: '/fixture/podman')
    commands = []

    def run(arguments, **kwargs):
        commands.append(arguments)
        if arguments[1] == 'build':
            context = Path(arguments[-1])
            assert {path.name for path in context.iterdir()} == {'Containerfile', 'control'}
            assert 'Build-Depends:' in (context / 'control').read_text()
            assert 'Package:' not in (context / 'control').read_text()
            if status:
                raise subprocess.CalledProcessError(status, arguments)
        return subprocess.CompletedProcess(arguments, 0)

    monkeypatch.setattr(deb_builder.subprocess, 'run', run)
    if status:
        with pytest.raises(subprocess.CalledProcessError):
            deb_builder.setup(ROOT)
        assert len(commands) == 1
    else:
        deb_builder.setup(ROOT)
        assert commands[1][:3] == ['podman', 'image', 'exists']
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('failure', [None, 'missing', 'outdated', 'build'])
def test_deb_on_fedora_uses_prepared_ubuntu_image_and_exports_artifacts(tmp_path, monkeypatch, failure):
    from pathlib import Path

    # Released product sources need not contain today's container tooling.
    checkout = tmp_path / 'checkout'
    (checkout / 'debian').mkdir(parents=True)
    for name in ('control', 'rules'):
        (checkout / 'debian' / name).write_bytes((ROOT / 'debian' / name).read_bytes())
    (checkout / 'Makefile').write_text(
        'package-source-files:\n\t@printf "%s\\n" Makefile debian/control debian/rules\n')
    package_command = ['dpkg-buildpackage', '--build=binary', '--no-sign', '-aamd64']
    environment = {'HOME': str(tmp_path / 'build-home'), 'DEB_BUILD_OPTIONS': 'parallel=2',
                   'SOURCE_DATE_EPOCH': '123'}
    monkeypatch.setattr(build_package, 'scratch_directory', lambda: tmp_path)
    monkeypatch.setattr(deb_builder, 'scratch_descriptors', lambda: ())
    monkeypatch.setattr(deb_builder, 'native_debian', lambda: False)
    monkeypatch.setattr(deb_builder.shutil, 'which', lambda _: None if failure == 'missing' else '/fixture/podman')
    original_run = subprocess.run
    commands = []

    def run(arguments, **kwargs):
        if arguments[0] != 'podman':
            return original_run(arguments, **kwargs)
        commands.append(arguments)
        if arguments[1:3] == ['image', 'exists']:
            assert arguments[-1] == deb_builder.inputs(ROOT)[2]
            return subprocess.CompletedProcess(arguments, 1 if failure == 'outdated' else 0)
        assert '--network=none' in arguments and '--pull=never' in arguments
        assert '--userns=keep-id' in arguments and '--cap-drop=all' in arguments
        assert 'DEB_BUILD_OPTIONS=parallel=2' in arguments
        assert 'SOURCE_DATE_EPOCH=123' in arguments
        assert kwargs['env']['HOME'] == os.environ['HOME'] != environment['HOME']
        assert arguments[-4:] == package_command
        volume = arguments[arguments.index('--volume') + 1]
        assert volume.endswith(':/build:rw,Z')  # Private SELinux label on Fedora.
        workspace = Path(volume.removesuffix(':/build:rw,Z'))
        assert workspace / 'source' == kwargs['cwd']
        assert (workspace / 'source/debian/rules').is_file()
        assert not (workspace / 'source/debian/Containerfile').exists()
        if failure == 'build':
            raise subprocess.CalledProcessError(7, arguments)
        (workspace / 'product.deb').write_bytes(b'Ubuntu package')
        return subprocess.CompletedProcess(arguments, 0)

    monkeypatch.setattr(deb_builder.subprocess, 'run', run)
    destination = tmp_path / 'exported'
    if failure:
        with pytest.raises((ValueError, subprocess.CalledProcessError)) as error:
            build_package.build(checkout, 'amd64', destination=destination,
                                builder_root=ROOT, package_command=package_command, environment=environment)
        if failure != 'build':
            assert './setup.sh --dependencies-only' in str(error.value)
        assert not destination.exists()
    else:
        build_package.build(checkout, 'amd64', destination=destination,
                            builder_root=ROOT, package_command=package_command, environment=environment)
        assert (destination / 'product.deb').read_bytes() == b'Ubuntu package'
    assert not any(path.name.startswith('onpc-package-') for path in tmp_path.iterdir())
    assert not any('build' in arguments[1:2] or 'pull' in arguments[1:2] for arguments in commands)
