"""Caller-owned Fedora build image; setup installs dependencies, builds do not."""
from __future__ import annotations

import hashlib
from pathlib import Path
import shutil
import subprocess
import tempfile

if __package__:
    from .test_storage import scratch_directory, scratch_descriptors
else:
    from test_storage import scratch_directory, scratch_descriptors


def inputs(root: Path):
    recipe = (root / 'rpm/Containerfile').read_bytes()
    spec = (root / 'rpm/oh-no-parent-control.spec.in').read_text()
    spec = spec.replace('@VERSION@', '0.0').replace('@RELEASE@', '0.1.dev')
    requirements = '\n'.join(line for line in spec.splitlines() if line.startswith('BuildRequires:'))
    fingerprint = hashlib.sha256(recipe + b'\0' + requirements.encode()).hexdigest()
    return recipe, spec, f'localhost/onpc-rpm-builder:fc44-{fingerprint[:20]}'


def require_image(root: Path) -> str:
    image = inputs(root)[2]
    if shutil.which('podman') is None:
        raise ValueError('Fedora 44 RPM builder is missing; run ./setup.sh --rpm-build-tools')
    result = subprocess.run(['podman', 'image', 'exists', image], check=False,
                            pass_fds=scratch_descriptors())
    if result.returncode != 0:
        raise ValueError('Fedora 44 RPM builder is unavailable or outdated; run ./setup.sh --rpm-build-tools')
    return image


def setup(root: Path) -> None:
    if shutil.which('podman') is None:
        raise ValueError('podman is missing; run ./setup.sh --rpm-build-tools')
    recipe, spec, image = inputs(root)
    with tempfile.TemporaryDirectory(prefix='onpc-rpm-builder-', dir=scratch_directory()) as temporary:
        context = Path(temporary)
        (context / 'Containerfile').write_bytes(recipe)
        (context / 'oh-no-parent-control.spec').write_text(spec)
        subprocess.run(['podman', 'build', '--pull=missing', '--tag', image, str(context)],
                       check=True, pass_fds=scratch_descriptors())
    require_image(root)
    print('setup: Fedora 44 RPM builder is ready', flush=True)


def command(root: Path, top: Path, mode: str) -> list[str]:
    return ['podman', 'run', '--rm', '--pull=never', '--network=none',
            '--userns=keep-id', '--cap-drop=all',
            '--volume', f'{top}:/build:rw', require_image(root),
            'rpmbuild', '--define', '_topdir /build', '--define', 'dist .fc44',
            '-ba' if mode == 'rpm' else '-bs', '/build/SPECS/oh-no-parent-control.spec']


if __name__ == '__main__':
    import sys
    if len(sys.argv) != 1:
        sys.exit('setup-rpm-builder: invoke through ./setup.sh')
    try:
        setup(Path(__file__).resolve().parents[1])
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        sys.exit(f'setup-rpm-builder: {error}')
