#!/usr/bin/python3 -I -S -B
"""Exec the fixed offline fixture target build with compact inherited leases.

Descriptor compaction belongs exclusively to this fresh helper process. The
calling coordinator retains its own descriptor table and original lease numbers.
"""
import argparse
import fcntl
import os
from pathlib import Path
import re
import stat


def compact(lease_fds):
    """Move inherited leases to contiguous OCI-preserved descriptors, from 3."""
    originals = tuple(lease_fds)
    if (any(type(fd) is not int or fd < 3 for fd in originals)
            or len(set(originals)) != len(originals)):
        raise ValueError('invalid fixture container lease descriptors')
    for descriptor in originals:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ValueError('fixture container lease must be a regular file')
    final = tuple(range(3, 3 + len(originals)))
    floor = max((*originals, *final), default=2) + 1
    copies = []
    try:
        # Preserve every original before overwriting any low descriptor. This
        # handles permutations and originals overlapping the destination slots.
        for descriptor in originals:
            copies.append(fcntl.fcntl(descriptor, fcntl.F_DUPFD_CLOEXEC, floor))
        for temporary, destination in zip(copies, final):
            os.dup2(temporary, destination, inheritable=True)
        for descriptor in originals:
            if descriptor not in final:
                os.close(descriptor)
        return final
    finally:
        for descriptor in copies:
            os.close(descriptor)


def _directory(value):
    path = Path(value)
    if not path.is_absolute() or path.resolve(strict=True) != path or not path.is_dir():
        raise ValueError('fixture container paths must be existing canonical directories')
    return path


def command(source, workspace, target, image, lease_fds):
    source, workspace = _directory(source), _directory(workspace)
    if source == workspace or source.parent != workspace.parent:
        raise ValueError('fixture container source/workspace must be distinct sibling allocations')
    compiled = _directory(workspace / 'compiled')
    if any(compiled.iterdir()):
        raise ValueError('fixture container compiler output must be empty')
    _directory(workspace / 'scratch')
    if target not in ('ubuntu', 'fedora'):
        raise ValueError('unsupported fixture container target')
    if type(image) is not str or re.fullmatch('[0-9a-f]{64}', image) is None:
        raise ValueError('fixture container requires an exact bare image identity')
    leases = tuple(lease_fds)
    if any(type(fd) is not int for fd in leases) or leases != tuple(range(3, 3 + len(leases))):
        raise ValueError('fixture container descriptors must be compact')
    flags = [value for descriptor in leases for value in ('--lease-fd', str(descriptor))]
    return ['podman', 'run', '--rm', '--pull=never', '--network=none',
            '--userns=keep-id', '--cap-drop=all', '--preserve-fds=' + str(len(leases)),
            '--env', 'TMPDIR=/work/scratch', '--env', 'PYTHONDONTWRITEBYTECODE=1',
            '--volume', f'{source}:/source:ro,Z',
            '--volume', f'{workspace}:/work:rw,Z', image,
            '/usr/bin/python3', '-I', '-S', '-B', '/source/tools/fixture_target_build.py',
            '--source', '/source', '--output', '/work/compiled', '--target', target, *flags]


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--target', choices=('ubuntu', 'fedora'), required=True)
    parser.add_argument('--image', required=True)
    parser.add_argument('--lease-fd', type=int, action='append', default=[])
    arguments = parser.parse_args()
    try:
        # Validate the complete fixed command before descriptor mutation.
        mapped = tuple(range(3, 3 + len(arguments.lease_fd)))
        invocation = command(arguments.source, arguments.workspace, arguments.target,
                             arguments.image, mapped)
        compact(arguments.lease_fd)
        os.execvpe('podman', invocation, os.environ)
    except (OSError, ValueError) as error:
        parser.exit(1, 'fixture container: ' + str(error) + '\n')


if __name__ == '__main__':
    main()
