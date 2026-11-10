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
    from . import bump_version, deb_builder, package_inputs, host_disk, build_targets
    from .test_storage import scratch_directory, scratch_descriptors
else:
    import deb_builder
    import bump_version
    import package_inputs
    import host_disk
    import build_targets
    from test_storage import scratch_directory, scratch_descriptors


def build(root: Path, architecture: str = 'x86_64', *, destination: Path | None = None, stopped=None,
          disk_queue=True, target='ubuntu26.04', environment=None, package_command=None,
          builder_root: Path | None = None) -> None:
    selected = build_targets.get(target, 'x86_64' if architecture == 'amd64' else architecture, 'deb')
    with (host_disk.operation('Building the DEB package', stopped=stopped)
          if disk_queue else nullcontext()):
        return _build(root, selected.package_architecture, destination=destination or selected.output(root),
                      environment=environment, package_command=package_command, builder_root=builder_root)


def _build(root: Path, architecture: str, *, destination: Path | None = None, environment=None,
           package_command=None, builder_root: Path | None = None) -> None:
    with tempfile.TemporaryDirectory(prefix='onpc-package-', dir=scratch_directory()) as temporary:
        source = Path(temporary) / 'source'
        source.mkdir()
        package_inputs.copy(root, source)
        native_command = package_command or ['make', '--no-print-directory', '_build-package',
                                              f'DEB_HOST_ARCH={architecture}']
        native = deb_builder.native_debian()
        arguments = (native_command if native else
                     [*deb_builder.command(builder_root or source, Path(temporary), architecture,
                                           environment=environment)[:-4],
                      *native_command])
        # Podman needs the caller's prepared rootless storage. Package build
        # settings enter the container only through its explicit arguments.
        subprocess.run(
            arguments, cwd=source, check=True,
            env=host_disk.environment(environment if native else None),
            pass_fds=(*scratch_descriptors(), *host_disk.descriptors()))
        output = destination or root / 'output/deb'
        output.mkdir(parents=True, exist_ok=True)
        artifacts = (Path(temporary).iterdir() if package_command else (source / 'output/deb').iterdir())
        for artifact in artifacts:
            if not artifact.is_file():
                continue
            shutil.move(str(artifact), output / artifact.name)
    print(f'SUCCESS: build artifacts are in {output}', flush=True)


def build_rpm(root: Path, output: Path, *, release='0.1.dev', mode='rpm', stopped=None,
              disk_queue=True, target='fedora44', architecture='x86_64'):
    if __package__:
        from .build_rpm import build as backend
    else:
        from build_rpm import build as backend
    with (host_disk.operation('Building the RPM package', stopped=stopped)
          if disk_queue else nullcontext()):
        return backend(root, output, release=release, mode=mode, target=target, architecture=architecture,
                       inherited_fds=host_disk.descriptors(),
                       inherited_environment=host_disk.environment())


def build_both(root: Path, architecture: str, release: str, *, disk_queue=True, targets=None, mode='rpm') -> None:
    targets = build_targets.configured(root) if targets is None else targets
    architecture = 'x86_64' if architecture == 'amd64' else architecture
    if any(target.architecture != architecture for target in targets):
        raise ValueError('requested architecture does not match configured targets')
    # One snapshot gives every target the same checkout generation. Each
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
        with ThreadPoolExecutor(max_workers=1 if host_disk.descriptors() else max(1, len(targets))) as pool:
            jobs = {}
            for target in targets:
                options = dict(stopped=stopped, disk_queue=disk_queue, target=target.name)
                if target.package_format == 'deb':
                    job = pool.submit(copy_context().run, build, frozen, architecture,
                                      destination=target.output(root), **options)
                else:
                    job = pool.submit(copy_context().run, build_rpm, frozen, target.output(root),
                                      architecture=architecture, release=release, mode=mode, **options)
                jobs[f'{target.name}/{architecture}'] = job
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
    parser.add_argument('--architecture', default='x86_64')
    parser.add_argument('--build-target', help='build only this configured target')
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
        targets = build_targets.configured(root)
        package_format = 'rpm' if arguments.format in ('srpm', 'rpm-source') else arguments.format
        targets = tuple(target for target in targets if
                        (package_format == 'both' or target.package_format == package_format)
                        and (arguments.build_target is None or target.name == arguments.build_target))
        if not targets:
            raise ValueError('no configured build targets match the selection')
        build_both(root, arguments.architecture, arguments.rpm_release, disk_queue=disk_queue,
                   targets=targets, mode=arguments.format if arguments.format in ('srpm', 'rpm-source') else 'rpm')
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'FAIL: build: {error}\n')
