"""Caller-owned Ubuntu build image; setup installs dependencies, builds do not."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

if __package__:
    from .test_storage import scratch_directory, scratch_descriptors
else:
    from test_storage import scratch_directory, scratch_descriptors


def native_debian() -> bool:
    release = {}
    for line in Path('/etc/os-release').read_text().splitlines():
        key, separator, value = line.partition('=')
        if separator:
            release[key] = value.strip('\"\'')
    return bool({'ubuntu', 'debian'} & set(
        (release.get('ID', '') + ' ' + release.get('ID_LIKE', '')).split()))


def inputs(root: Path):
    recipe = (root / 'debian/Containerfile').read_bytes()
    # Binary Depends changes do not invalidate the build environment.
    control = (root / 'debian/control').read_text().split('\n\n', 1)[0] + '\n'
    requirements = []
    collecting = False
    for line in control.splitlines():
        if not line.startswith((' ', '\t')):
            collecting = line.startswith(('Build-Depends:', 'Build-Depends-Arch:', 'Build-Depends-Indep:'))
        if collecting:
            requirements.append(line)
    fingerprint = hashlib.sha256(recipe + b'\0' + '\n'.join(requirements).encode()).hexdigest()
    return recipe, control, f'localhost/onpc-deb-builder:ubuntu26.04-{fingerprint[:20]}'


def require_image(root: Path) -> str:
    image = inputs(root)[2]
    guidance = 'run ./setup.sh --dependencies-only'
    if shutil.which('podman') is None:
        raise ValueError(f'Ubuntu 26.04 DEB builder is missing; {guidance}')
    result = subprocess.run(['podman', 'image', 'exists', image], check=False,
                            pass_fds=scratch_descriptors())
    if result.returncode != 0:
        raise ValueError(f'Ubuntu 26.04 DEB builder is unavailable or outdated; {guidance}')
    return image


def setup(root: Path) -> None:
    if shutil.which('podman') is None:
        raise ValueError('podman is missing; run ./setup.sh --dependencies-only')
    recipe, control, image = inputs(root)
    with tempfile.TemporaryDirectory(prefix='onpc-deb-builder-', dir=scratch_directory()) as temporary:
        context = Path(temporary)
        (context / 'Containerfile').write_bytes(recipe)
        (context / 'control').write_text(control)
        subprocess.run(['podman', 'build', '--pull=missing', '--tag', image, str(context)],
                       check=True, pass_fds=scratch_descriptors())
    require_image(root)
    print('setup: Ubuntu 26.04 DEB builder is ready', flush=True)


def command(root: Path, workspace: Path, architecture: str) -> list[str]:
    return ['podman', 'run', '--rm', '--pull=never', '--network=none',
            '--userns=keep-id', '--cap-drop=all',
            '--env', f'DEB_BUILD_OPTIONS={os.environ.get("DEB_BUILD_OPTIONS", "")}',
            '--volume', f'{workspace}:/build:rw,Z', require_image(root),
            'make', '--no-print-directory', '_build-package', f'DEB_HOST_ARCH={architecture}']


if __name__ == '__main__':
    import sys
    if len(sys.argv) != 1:
        sys.exit('setup-deb-builder: invoke through ./setup.sh')
    try:
        setup(Path(__file__).resolve().parents[1])
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        sys.exit(f'setup-deb-builder: {error}')
