"""Record initial aggregate source identity for informational provenance."""

import hashlib
import os
from pathlib import Path
import subprocess


def paths(root):
    """Git-visible working files, including new source but excluding ignored output.

    Read bytes from the working tree, never from HEAD or the index. Deleted
    indexed files stay deleted; nested repositories are not source payloads.
    Keep links in the inventory so the reader can refuse them explicitly.
    """
    # Installed evidence producers run as root in the dispatcher's validated,
    # developer-owned checkout. Scope trust to this read, as provenance does.
    listing = subprocess.run(['git', '-c', 'safe.directory=' + str(root),
                              'ls-files', '-z', '--cached', '--others', '--exclude-standard'],
                             cwd=root, check=True, stdout=subprocess.PIPE).stdout
    selected = []
    for name in sorted(set(listing.split(b'\0')) - {b''}):
        relative = Path(os.fsdecode(name))
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('invalid source input path')
        path = root / relative
        if not os.path.lexists(path):
            continue
        if path.is_dir() and not path.is_symlink():
            continue
        selected.append(relative)
    return selected


def identity(root):
    digest = hashlib.sha256()
    for relative in paths(root):
        name = os.fsencode(relative)
        path = root / relative
        if path.is_symlink():
            raise ValueError('source inputs contain a symlink')
        if not path.exists():
            continue  # Indexed deletion already present at the start.
        if path.is_dir():
            # Git reports an untracked nested checkout as a directory entry.
            # It is not a source file in this checkout.
            continue
        digest.update(name + b'\0')
        digest.update(str(path.stat().st_mode & 0o777).encode() + b'\0')
        with path.open('rb') as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(block)
        digest.update(b'\0')
    return digest.hexdigest()
