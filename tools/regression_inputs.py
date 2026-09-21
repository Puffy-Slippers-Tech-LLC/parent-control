"""Record initial aggregate source identity for informational provenance."""

import hashlib
import subprocess


def identity(root):
    listing = subprocess.run(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'],
                             cwd=root, check=True, stdout=subprocess.PIPE).stdout
    digest = hashlib.sha256()
    for name in sorted(set(listing.split(b'\0')) - {b''}):
        path = root / name.decode('utf-8')
        if path.is_symlink():
            raise ValueError('source inputs contain a symlink')
        if not path.exists():
            continue  # Indexed deletion already present at the start.
        digest.update(name + b'\0')
        digest.update(str(path.stat().st_mode & 0o777).encode() + b'\0')
        with path.open('rb') as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(block)
        digest.update(b'\0')
    return digest.hexdigest()
