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
    files.setdefault('/usr/lib/os-release', b'ID=ubuntu\nVERSION_ID="26.04"\n')
    files[profile.LOCALE_PATH] = b'Chinese locale\0UTF-8\0'
    files[profile.FONT_PATH] = font()
    files['/usr/share/locale/zh_CN/LC_MESSAGES/mate-polkit.mo'] = catalogue({
        message: '中文 ' + message for message in profile.CATALOGUES['mate-polkit']})
    files['/usr/share/locale-langpack/zh_CN/LC_MESSAGES/Linux-PAM.mo'] = catalogue({
        message: '中文 ' + message for message in profile.CATALOGUES['Linux-PAM']})
    files['/usr/share/locale-langpack/zh_CN/LC_MESSAGES/gnome-shell.mo'] = catalogue({'Activities': '活动'})
    owners = {
        'locales-all': [profile.LOCALE_PATH], 'fonts-noto-cjk': [profile.FONT_PATH],
        'mate-polkit-common': ['/usr/share/locale/zh_CN/LC_MESSAGES/mate-polkit.mo'],
        'language-pack-zh-hans-base': ['/usr/share/locale-langpack/zh_CN/LC_MESSAGES/Linux-PAM.mo'],
        'language-pack-gnome-zh-hans-base': ['/usr/share/locale-langpack/zh_CN/LC_MESSAGES/gnome-shell.mo'],
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


def populate_fedora(files, metadata):
    """RPM-owned synthetic files and their independent SHA-256 manifests."""
    files['/usr/lib/os-release'] = b'ID=fedora\nVERSION_ID=44\nVARIANT_ID=workstation\n'
    files['/etc/selinux/config'] = b'SELINUX=enforcing\nSELINUXTYPE=targeted\n'
    files['/sys/fs/selinux/enforce'] = b'1\n'
    files[profile.LOCALE_PATH] = b'Chinese locale\0UTF-8\0'
    files[profile.FEDORA_FONT_PATH] = font()
    owners = {'glibc-langpack-zh': [profile.LOCALE_PATH],
              'google-noto-sans-cjk-fonts': [profile.FEDORA_FONT_PATH]}
    for domain, messages in profile.CATALOGUES.items():
        path = f'/usr/share/locale/zh_CN/LC_MESSAGES/{domain}.mo'
        files[path] = catalogue({message: '中文 ' + message for message in messages})
        owners[profile.FEDORA_CATALOGUE_PACKAGES[domain][0]] = [path]
    profile_paths = {'/usr/lib/os-release', '/etc/selinux/config', '/sys/fs/selinux/enforce',
                     *(path for paths in owners.values() for path in paths)}
    for path in profile_paths:
        metadata.setdefault(path, {'st_mode': stat.S_IFREG | 0o644, 'st_uid': 0,
                                   'st_gid': 0, 'st_nlink': 1})
        for parent in Path(path).parents:
            metadata.setdefault(str(parent), {'st_mode': stat.S_IFDIR | 0o755,
                                              'st_uid': 0, 'st_gid': 0, 'st_nlink': 1})
    return {owner: {path: hashlib.sha256(files[path]).hexdigest() for path in paths}
            for owner, paths in owners.items()}


def guest(os_id='ubuntu'):
    files, metadata = {}, {}
    if os_id == 'fedora':
        records = populate_fedora(files, metadata)
    else:
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
    if os_id == 'fedora':
        g.rpm_records = records
        g.rpm_versions = dict.fromkeys(profile.FEDORA_PACKAGES, '1-1.fc44')
        def command(argv):
            if argv == profile.LOCALE_COMMAND:
                return 'UTF-8\n'
            if argv == profile.RPM_LIST_COMMAND:
                return ''.join(f'{name}\t{version}\n' for name, version in g.rpm_versions.items())
            assert argv == profile.rpm_file_command(argv[-1])
            name = argv[-1]
            return f'{name}\t{g.rpm_versions[name]}\t8\n' + ''.join(
                f'{path}\t{digest}\n' for path, digest in records[name].items())
        g.command.side_effect = command
    else:
        g.command.return_value = 'UTF-8\n'
    return g, files, metadata
