#!/usr/bin/python3 -B
"""Build local packages with host disk admission by default (automation entry point)."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from contextvars import copy_context
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading

if __package__:
    from . import bump_version, deb_builder, package_inputs, host_disk
    from .test_storage import scratch_directory, scratch_descriptors
else:
    import deb_builder
    import bump_version
    import package_inputs
    import host_disk
    from test_storage import scratch_directory, scratch_descriptors


def build(root: Path, architecture: str, *, destination: Path | None = None, stopped=None,
          disk_queue=True) -> None:
    with (host_disk.operation('Building the DEB package', stopped=stopped)
          if disk_queue else nullcontext()):
        return _build(root, architecture, destination=destination)


def _build(root: Path, architecture: str, *, destination: Path | None = None) -> None:
    with tempfile.TemporaryDirectory(prefix='onpc-package-', dir=scratch_directory()) as temporary:
        source = Path(temporary) / 'source'
        source.mkdir()
        package_inputs.copy(root, source)
        arguments = (['make', '--no-print-directory', '_build-package',
                      f'DEB_HOST_ARCH={architecture}'] if deb_builder.native_debian()
                     else deb_builder.command(source, Path(temporary), architecture))
        subprocess.run(
            arguments, cwd=source, check=True,
            env=host_disk.environment(),
            pass_fds=(*scratch_descriptors(), *host_disk.descriptors()))
        output = destination or root / 'output/deb'
        output.mkdir(parents=True, exist_ok=True)
        for artifact in (source / 'output/deb').iterdir():
            shutil.move(str(artifact), output / artifact.name)
    print(f'SUCCESS: build artifacts are in {output}', flush=True)


def build_rpm(root: Path, output: Path, *, release='0.1.dev', mode='rpm', stopped=None,
              disk_queue=True):
    if __package__:
        from .build_rpm import build as backend
    else:
        from build_rpm import build as backend
    with (host_disk.operation('Building the RPM package', stopped=stopped)
          if disk_queue else nullcontext()):
        return backend(root, output, release=release, mode=mode,
                       inherited_fds=host_disk.descriptors(),
                       inherited_environment=host_disk.environment())


def build_both(root: Path, architecture: str, release: str, *, disk_queue=True) -> None:
    # One snapshot gives both packages the same checkout generation. Each
    # backend receives its own copy and output tree; dpkg cleanup cannot race
    # RPM staging. Initialize the scratch lease before starting worker threads.
    with tempfile.TemporaryDirectory(prefix='onpc-build-', dir=scratch_directory()) as temporary:
        frozen = Path(temporary) / 'source'
        frozen.mkdir()
        package_inputs.copy(root, frozen)
        failures = []
        stopped = threading.Event()
        # A wrapped caller may already own the disk slot. Its inner backends
        # borrow that context serially, rather than racing under one receipt.
        with ThreadPoolExecutor(max_workers=1 if host_disk.descriptors() else 2) as pool:
            jobs = {
                'deb': pool.submit(copy_context().run, build, frozen, architecture,
                                   destination=root / 'output/deb', stopped=stopped,
                                   disk_queue=disk_queue),
                'rpm': pool.submit(copy_context().run, build_rpm, frozen, root / 'output/rpm',
                                   release=release, stopped=stopped, disk_queue=disk_queue),
            }
            try:
                for name, job in jobs.items():
                    try:
                        job.result()
                    except (OSError, ValueError, subprocess.CalledProcessError) as error:
                        failures.append(f'{name}: {error}')
            except BaseException:
                stopped.set()
                raise
        if failures:
            raise ValueError('; '.join(failures))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--architecture', default='amd64')
    parser.add_argument('--format', choices=('both', 'deb', 'rpm', 'srpm', 'rpm-source'), default='both')
    parser.add_argument('--rpm-release', default='0.1.dev')
    parser.add_argument('--disk-queue', choices=('always', 'never'), default='always',
                        help='use never for a manual build without host disk admission; '
                             'automation keeps always (the default)')
    arguments = parser.parse_args()
    disk_queue = arguments.disk_queue == 'always'
    try:
        root = Path(__file__).resolve().parents[1]
        bump_version.check_repository()
        if arguments.format == 'both':
            build_both(root, arguments.architecture, arguments.rpm_release, disk_queue=disk_queue)
        elif arguments.format == 'deb':
            build(root, arguments.architecture, disk_queue=disk_queue)
        else:
            build_rpm(root, root / 'output/rpm', release=arguments.rpm_release,
                      mode=arguments.format, disk_queue=disk_queue)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'FAIL: build: {error}\n')
