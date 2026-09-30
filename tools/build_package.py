"""Build a local package without cleaning or traversing the working checkout."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import shutil
import subprocess
import tempfile

if __package__:
    from . import package_inputs
    from .test_storage import scratch_directory, scratch_descriptors
else:
    import package_inputs
    from test_storage import scratch_directory, scratch_descriptors


def build(root: Path, architecture: str, *, destination: Path | None = None) -> None:
    with tempfile.TemporaryDirectory(prefix='onpc-package-', dir=scratch_directory()) as temporary:
        source = Path(temporary) / 'source'
        source.mkdir()
        package_inputs.copy(root, source)
        subprocess.run(
            ['make', '--no-print-directory', '_build-package',
             f'DEB_HOST_ARCH={architecture}'], cwd=source, check=True,
            pass_fds=scratch_descriptors())
        output = destination or root / 'output/deb'
        output.mkdir(parents=True, exist_ok=True)
        for artifact in (source / 'output/deb').iterdir():
            shutil.move(str(artifact), output / artifact.name)
    print(f'SUCCESS: build artifacts are in {output}', flush=True)


def build_both(root: Path, architecture: str, release: str) -> None:
    if __package__:
        from .build_rpm import build as build_rpm
    else:
        from build_rpm import build as build_rpm
    # One snapshot gives both packages the same checkout generation. Each
    # backend receives its own copy and output tree; dpkg cleanup cannot race
    # RPM staging. Initialize the scratch lease before starting worker threads.
    with tempfile.TemporaryDirectory(prefix='onpc-build-', dir=scratch_directory()) as temporary:
        frozen = Path(temporary) / 'source'
        frozen.mkdir()
        package_inputs.copy(root, frozen)
        failures = []
        with ThreadPoolExecutor(max_workers=2) as pool:
            jobs = {
                'deb': pool.submit(build, frozen, architecture, destination=root / 'output/deb'),
                'rpm': pool.submit(build_rpm, frozen, root / 'output/rpm', release=release),
            }
            for name, job in jobs.items():
                try:
                    job.result()
                except (OSError, ValueError, subprocess.CalledProcessError) as error:
                    failures.append(f'{name}: {error}')
        if failures:
            raise ValueError('; '.join(failures))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--architecture', required=True)
    parser.add_argument('--format', choices=('both', 'deb', 'rpm', 'srpm', 'rpm-source'), default='both')
    parser.add_argument('--rpm-release', default='0.1.dev')
    arguments = parser.parse_args()
    try:
        root = Path(__file__).resolve().parents[1]
        if arguments.format == 'both':
            build_both(root, arguments.architecture, arguments.rpm_release)
        elif arguments.format == 'deb':
            build(root, arguments.architecture)
        else:
            from build_rpm import build as build_rpm
            build_rpm(root, root / 'output/rpm', release=arguments.rpm_release,
                      mode=arguments.format)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'FAIL: build: {error}\n')
