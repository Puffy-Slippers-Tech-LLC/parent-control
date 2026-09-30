"""Prepare RPM sources, SRPMs or local binaries from the shared package allowlist."""
from __future__ import annotations

import argparse
from email.utils import parsedate_to_datetime
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile

if __package__:
    from . import package_inputs, rpm_builder
    from .test_storage import scratch_directory, scratch_descriptors
else:
    import package_inputs
    import rpm_builder
    from test_storage import scratch_directory, scratch_descriptors


def metadata(root: Path, release: str):
    version = json.loads((root / 'data/app.json').read_text())['version']
    if not re.fullmatch(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)', version):
        raise ValueError('invalid product version')
    if not re.fullmatch(r'[0-9]+(?:\.[a-zA-Z0-9]+)*', release):
        raise ValueError('RPM release must contain only dot-separated letters/numbers and start with a number')
    changelog = (root / 'debian/changelog').read_text()
    timestamp = re.search(r'^ -- .*  (.+)$', changelog, re.MULTILINE)
    if timestamp is None:
        raise ValueError('missing shared source timestamp in changelog')
    epoch = int(parsedate_to_datetime(timestamp.group(1)).timestamp())
    return version, epoch


def sources(root: Path, workspace: Path, release: str):
    source = workspace / 'source'
    source.mkdir()
    selected = package_inputs.copy(root, source)
    version, epoch = metadata(source, release)
    top = workspace / 'rpmbuild'
    for directory in ('SOURCES', 'SPECS', 'BUILD', 'BUILDROOT', 'RPMS', 'SRPMS'):
        (top / directory).mkdir(parents=True)
    name = f'oh-no-parent-control-{version}'
    archive = top / 'SOURCES' / f'{name}.tar.xz'
    with tarfile.open(archive, 'w:xz', format=tarfile.PAX_FORMAT) as output:
        for relative in selected:
            path = source / relative
            info = output.gettarinfo(str(path), arcname=f'{name}/{relative.as_posix()}')
            info.uid = info.gid = 0
            info.uname = info.gname = 'root'
            info.mtime = epoch
            with path.open('rb') as stream:
                output.addfile(info, stream)
    spec = top / 'SPECS/oh-no-parent-control.spec'
    content = (source / 'rpm/oh-no-parent-control.spec.in').read_text()
    for token, value in (('@VERSION@', version), ('@RELEASE@', release)):
        if content.count(token) != 1:
            raise ValueError(f'invalid RPM spec slot: {token}')
        content = content.replace(token, value)
    spec.write_text(content)
    identity = top / 'SOURCES' / f'{name}.inputs.json'
    identity.write_text(json.dumps({
        'version': version, 'release': release,
        'source_sha256': package_inputs.digest(source, selected),
        'archive_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
        'files': [p.as_posix() for p in selected],
    }, indent=2) + '\n')
    return top, spec, archive, identity


def export(artifact: Path, output: Path):
    target = output / artifact.name
    if artifact.is_symlink() or not artifact.is_file():
        raise ValueError('RPM artifact must be a regular file')
    if target.is_symlink() or (target.exists() and not target.is_file()):
        raise ValueError('refusing substituted RPM artifact path')
    shutil.copy2(artifact, target)


def native_fedora44():
    release_file = Path('/etc/os-release').read_text()
    return bool(re.search(r'^ID=[\"\']?fedora[\"\']?$', release_file, re.MULTILINE)
                and re.search(r'^VERSION_ID=[\"\']?44[\"\']?$', release_file, re.MULTILINE))


def build(root: Path, output: Path, *, release='0.1.dev', mode='rpm'):
    if mode not in ('rpm', 'srpm', 'rpm-source'):
        raise ValueError('invalid RPM build mode')
    with tempfile.TemporaryDirectory(prefix='onpc-rpm-', dir=scratch_directory()) as temporary:
        top, spec, archive, identity = sources(root, Path(temporary), release)
        output.mkdir(parents=True, exist_ok=True)
        for artifact in (archive, identity, spec):
            export(artifact, output)
        if mode != 'rpm-source':
            native = mode == 'rpm' and native_fedora44()
            mock = mode == 'rpm' and not native and shutil.which('mock') is not None
            container = not native and not mock and (mode == 'rpm' or shutil.which('rpmbuild') is None)
            if container:
                if shutil.which('podman') is None:
                    raise ValueError(f'rpmbuild or Fedora 44 builder is missing; sources retained in {output}; run ./setup.sh --rpm-build-tools')
                arguments = rpm_builder.command(root, top, mode)
            else:
                if shutil.which('rpmbuild') is None:
                    raise ValueError('rpmbuild is missing; run ./setup.sh --rpm-build-tools')
                arguments = ['rpmbuild', '--define', f'_topdir {top}', '--define', 'dist .fc44',
                             '-ba' if native else '-bs', str(spec)]
            log = top / 'build.log'
            try:
                with log.open('w') as stream:
                    subprocess.run(arguments, cwd=top, check=True,
                                   stdout=stream, stderr=subprocess.STDOUT,
                                   pass_fds=scratch_descriptors())
            finally:
                export(log, output)
            if mock:
                srpm, = top.glob('SRPMS/*.rpm')
                export(srpm, output)
                result = top / 'mock-results'
                try:
                    subprocess.run(['mock', '--root', 'fedora-44-x86_64', '--rebuild', str(srpm),
                                    '--resultdir', str(result)], cwd=top, check=True,
                                   pass_fds=scratch_descriptors())
                finally:
                    # Retain the builder's normal evidence even when it fails.
                    for log in result.glob('*.log'):
                        export(log, output)
                for artifact in result.glob('*.rpm'):
                    export(artifact, output)
                binaries = list(result.glob('*.x86_64.rpm'))
            else:
                binaries = list(top.glob('RPMS/x86_64/*.rpm'))
            if mode == 'rpm' and not any(artifact.name.startswith('oh-no-parent-control-')
                                          and not artifact.name.startswith(('oh-no-parent-control-debuginfo-',
                                                                           'oh-no-parent-control-debugsource-'))
                                          for artifact in binaries):
                raise ValueError(f'Fedora builder produced no product binary RPM; see {output / "build.log"}')
        artifacts = [archive, identity, spec, *top.glob('SRPMS/*.rpm'), *top.glob('RPMS/*/*.rpm')]
        for artifact in artifacts:
            export(artifact, output)
    print(f'SUCCESS: RPM artifacts are in {output}', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--srpm', action='store_true')
    modes.add_argument('--sources-only', action='store_true')
    parser.add_argument('--release', default='0.1.dev')
    parser.add_argument('--output', type=Path)
    arguments = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    try:
        build(root, arguments.output or root / 'output/rpm', release=arguments.release,
              mode='rpm-source' if arguments.sources_only else 'srpm' if arguments.srpm else 'rpm')
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'FAIL: RPM build: {error}\n')
