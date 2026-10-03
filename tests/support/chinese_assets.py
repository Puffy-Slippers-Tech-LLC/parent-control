"""Synthetic finite language inputs for host readiness/ownership tests only."""
import hashlib
from pathlib import Path
import stat
import struct
from unittest.mock import Mock

import chinese_language_assets as profile


def catalogue(messages):
    values = {'': 'Content-Type: text/plain; charset=UTF-8\nLanguage: zh_CN\n', **messages}
    keys = sorted(values)
    original = [key.encode() for key in keys]
    translated = [values[key].encode() for key in keys]
    count = len(keys)
    offset = 28 + count * 16
    tables, strings = [], b''
    for entries in (original, translated):
        for entry in entries:
            tables.append(struct.pack('<II', len(entry), offset + len(strings)))
            strings += entry + b'\0'
    return struct.pack('<7I', 0x950412de, 0, count, 28, 28 + count * 8, 0, 0) + b''.join(tables) + strings


def font():
    groups = [(ord(char), ord(char), index + 1) for index, char in enumerate(sorted(set(profile.GLYPHS)))]
    sub = struct.pack('>HHIII', 12, 0, 16 + len(groups) * 12, 0, len(groups))
    sub += b''.join(struct.pack('>III', *group) for group in groups)
    cmap = struct.pack('>HHHHI', 0, 1, 3, 10, 12) + sub
    return (struct.pack('>4sIII', b'ttcf', 0x10000, 1, 16)
            + struct.pack('>4sHHHH', b'OTTO', 1, 0, 0, 0)
            + struct.pack('>4sIII', b'cmap', 0, 44, len(cmap)) + cmap)


def populate(files, metadata):
    """Add the finite distro-managed profile to an existing guestfs double."""
    previous = set(files)
    files[profile.LOCALE_PATH] = b'Chinese locale\0UTF-8\0'
    files[profile.FONT_PATH] = font()
    files['/usr/share/locale/zh_CN/LC_MESSAGES/mate-polkit.mo'] = catalogue({
        message: '中文 ' + message for message in profile.CATALOGUES['mate-polkit']})
    files['/usr/share/locale-langpack/zh_CN/LC_MESSAGES/Linux-PAM.mo'] = catalogue({
        message: '中文 ' + message for message in profile.CATALOGUES['Linux-PAM']})
    owners = {
        'locales-all': [profile.LOCALE_PATH], 'fonts-noto-cjk': [profile.FONT_PATH],
        'mate-polkit-common': ['/usr/share/locale/zh_CN/LC_MESSAGES/mate-polkit.mo'],
        'language-pack-zh-hans-base': ['/usr/share/locale-langpack/zh_CN/LC_MESSAGES/Linux-PAM.mo'],
    }
    for owner, paths in owners.items():
        files[f'/var/lib/dpkg/info/{owner}.list'] = ('\n'.join(paths) + '\n').encode()
        files[f'/var/lib/dpkg/info/{owner}.md5sums'] = ''.join(
            hashlib.md5(files[path], usedforsecurity=False).hexdigest() + '  ' + path.lstrip('/') + '\n'
            for path in paths).encode()
    for path in (set(files) - previous) | {'/var/lib/dpkg/status'}:
        metadata.setdefault(path, {'st_mode': stat.S_IFREG | 0o644, 'st_uid': 0,
                                   'st_gid': 0, 'st_nlink': 1})
        for parent in Path(path).parents:
            metadata.setdefault(str(parent), {'st_mode': stat.S_IFDIR | 0o755,
                                              'st_uid': 0, 'st_gid': 0, 'st_nlink': 1})


def guest():
    files, metadata = {}, {}
    files['/var/lib/dpkg/status'] = '\n\n'.join(
        f'Package: {item.split("=")[0]}\nVersion: 1\nStatus: install ok installed\n'
        for item in profile.PACKAGES).encode()
    populate(files, metadata)
    g = Mock()
    g.exists.side_effect = lambda path: path in files or path in metadata
    g.is_symlink.return_value = False
    g.realpath.side_effect = lambda path: path
    g.lstatns.side_effect = lambda path: dict(metadata[path])
    g.filesize.side_effect = lambda path: len(files[path])
    g.read_file.side_effect = files.__getitem__
    g.command.return_value = 'UTF-8\n'
    return g, files, metadata
