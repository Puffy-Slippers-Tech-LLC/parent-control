"""Caller-owned Fedora build image; setup installs dependencies, builds do not."""
from __future__ import annotations

import hashlib
from pathlib import Path
import shutil
import subprocess
import tempfile

if __package__:
    from . import build_targets
    from .test_storage import scratch_directory, scratch_descriptors
else:
    import build_targets
    from test_storage import scratch_directory, scratch_descriptors


def inputs(root: Path, *, target='fedora44', architecture='x86_64'):
    target = build_targets.get(target, architecture, 'rpm')
    recipe = (root / 'rpm/Containerfile').read_bytes()
    if recipe.count(b'FROM registry.fedoraproject.org/fedora:44\n') != 1:
        raise ValueError('unexpected Fedora builder base image')
    recipe = recipe.replace(b'fedora:44', ('fedora:' + target.version).encode())
    spec = (root / 'rpm/oh-no-parent-control.spec.in').read_text()
    spec = spec.replace('@VERSION@', '0.0').replace('@RELEASE@', '0.1.dev')
    requirements = '\n'.join(line for line in spec.splitlines() if line.startswith('BuildRequires:'))
    fingerprint = hashlib.sha256(recipe + b'\0' + requirements.encode()).hexdigest()
    return recipe, spec, f'localhost/onpc-rpm-builder:fc{target.version}-{fingerprint[:20]}'


def require_image(root: Path, *, target='fedora44', architecture='x86_64') -> str:
    image = inputs(root, target=target, architecture=architecture)[2]
    if shutil.which('podman') is None:
        raise ValueError(f'{target} RPM builder is missing; run ./setup.sh --rpm-build-tools')
    result = subprocess.run(['podman', 'image', 'exists', image], check=False,
                            pass_fds=scratch_descriptors())
    if result.returncode != 0:
        raise ValueError(f'{target} RPM builder is unavailable or outdated; run ./setup.sh --rpm-build-tools')
    return image


def setup(root: Path, *, target='fedora44', architecture='x86_64') -> None:
    if shutil.which('podman') is None:
        raise ValueError('podman is missing; run ./setup.sh --rpm-build-tools')
    recipe, spec, image = inputs(root, target=target, architecture=architecture)
    with tempfile.TemporaryDirectory(prefix='onpc-rpm-builder-', dir=scratch_directory()) as temporary:
        context = Path(temporary)
        (context / 'Containerfile').write_bytes(recipe)
        (context / 'oh-no-parent-control.spec').write_text(spec)
        subprocess.run(['podman', 'build', '--pull=missing', '--tag', image, str(context)],
                       check=True, pass_fds=scratch_descriptors())
    require_image(root, target=target, architecture=architecture)
    print(f'setup: {target}/{architecture} RPM builder is ready', flush=True)


def command(root: Path, top: Path, mode: str, *, epoch: int, target='fedora44', architecture='x86_64') -> list[str]:
    selected = build_targets.get(target, architecture, 'rpm')
    if type(epoch) is not int or epoch < 0:
        raise ValueError('invalid RPM source timestamp')
    return ['podman', 'run', '--rm', '--pull=never', '--network=none',
            '--userns=keep-id', '--cap-drop=all',
            '--env', f'SOURCE_DATE_EPOCH={epoch}',
            '--volume', f'{top}:/build:rw,Z', require_image(root, target=target, architecture=architecture),
            'rpmbuild', '--define', '_topdir /build', '--define', 'dist ' + selected.dist,
            '-ba' if mode == 'rpm' else '-bs', '/build/SPECS/oh-no-parent-control.spec']


if __name__ == '__main__':
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    if len(sys.argv) != 1:
        sys.exit('setup-rpm-builder: invoke through ./setup.sh')
    try:
        root = Path(__file__).resolve().parents[1]
        for target in build_targets.configured(root):
            if target.package_format == 'rpm' and not target.native():
                setup(root, target=target.name, architecture=target.architecture)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        sys.exit(f'setup-rpm-builder: {error}')
