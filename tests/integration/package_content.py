"""Installation identity independent of Debian archive timestamps/compression.

Only the delivery container is normalized. File bytes (including compressed
assets), ownership, permissions, links and all control files remain significant.
No archive members are extracted or executed.
"""

import hashlib
import io
import json
from pathlib import PurePosixPath
import tarfile


def require(condition, category):
    if not condition:
        raise ValueError('package-content:' + category)


def archive_digest(raw):
    """Hash an uncompressed control/data tar, rejecting ambiguous layouts."""
    entries = {}
    try:
        with tarfile.open(fileobj=io.BytesIO(raw), mode='r:') as archive:
            for member in archive:
                path = PurePosixPath(member.name)
                require(not path.is_absolute() and '..' not in path.parts,
                        'invalid-path')
                name = path.as_posix()
                require(name not in entries, 'duplicate-path')
                require(member.isfile() or member.isdir() or member.issym()
                        or member.islnk(), 'unsupported-member')
                require(name != '.' or member.isdir(), 'invalid-root')
                content = None
                if member.isfile():
                    with archive.extractfile(member) as stream:
                        content = hashlib.file_digest(stream, 'sha256').hexdigest()
                # Preserve unfamiliar extension metadata conservatively. PAX
                # timestamps, like tar/ar timestamps, are delivery metadata.
                pax = {key: value for key, value in member.pax_headers.items()
                       if key not in ('mtime', 'atime', 'ctime')}
                entries[name] = {
                    'kind': ('file' if member.isfile() else 'directory' if member.isdir()
                             else 'symlink' if member.issym() else 'hardlink'),
                    'mode': member.mode, 'uid': member.uid, 'gid': member.gid,
                    'uname': member.uname, 'gname': member.gname,
                    'target': member.linkname, 'size': member.size,
                    'sha256': content, 'pax': pax,
                }
    except (tarfile.TarError, EOFError) as error:
        raise ValueError('package-content:invalid-archive') from error
    require(bool(entries), 'empty-archive')
    for name, entry in entries.items():
        for parent in PurePosixPath(name).parents:
            ancestor = entries.get(parent.as_posix())
            require(ancestor is None or ancestor['kind'] == 'directory',
                    'non-directory-ancestor')
        if entry['kind'] == 'hardlink':
            target = entries.get(PurePosixPath(entry['target']).as_posix())
            require(target is not None and target['kind'] == 'file', 'invalid-hardlink')
    return hashlib.sha256(json.dumps(entries, sort_keys=True,
                                    separators=(',', ':')).encode()).hexdigest()


def digest(package, commands):
    """Use the guarded command transport; parse each archive only once."""
    parts = [archive_digest(commands.run(['dpkg-deb', option, str(package)],
                                        merge_stderr=False))
             for option in ('--ctrl-tarfile', '--fsys-tarfile')]
    return hashlib.sha256(('onpc-package-content-v1\n' + '\n'.join(parts)).encode()).hexdigest()
