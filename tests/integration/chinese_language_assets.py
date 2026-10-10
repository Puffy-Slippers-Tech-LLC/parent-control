"""Finite Ubuntu/Fedora Chinese readiness profiles; package management owns writes.

Used unchanged by baseline inspection, attempt bootstrap and FIX06. No locale
generation, installation, account configuration or product mutation here.
"""
import gettext
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import struct
import subprocess

LOCALE = 'zh_CN.UTF-8'
PACKAGES = ('locales-all=0', 'language-pack-zh-hans-base=0',
            'language-pack-zh-hans=0',
            'language-pack-gnome-zh-hans-base=0', 'language-pack-gnome-zh-hans=0',
            'mate-polkit=0', 'mate-polkit-common=0',
            'libpam0g=0', 'fonts-noto-cjk=0')
LOCALE_PATH = '/usr/lib/locale/zh_CN.utf8/LC_IDENTIFICATION'
FONT_PATH = '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
CATALOGUES = {
    'mate-polkit': ('_Cancel', '_Authenticate', '_Password:',
                    'An application is attempting to perform an action that requires privileges. '
                    'Authentication is required to perform this action.'),
    'Linux-PAM': ('Password: ', 'Authentication failure'),
    'gnome-shell': ('Activities',),
}
CATALOGUE_PACKAGES = {
    'mate-polkit': ('mate-polkit-common',),
    'Linux-PAM': ('language-pack-zh-hans-base', 'language-pack-zh-hans'),
    'gnome-shell': ('language-pack-gnome-zh-hans-base', 'language-pack-gnome-zh-hans'),
}
FEDORA_PACKAGES = ('glibc-langpack-zh', 'mate-polkit', 'pam', 'gnome-shell',
                   'google-noto-sans-cjk-fonts')
FEDORA_FONT_PATH = '/usr/share/fonts/google-noto-sans-cjk-fonts/NotoSansCJK-Regular.ttc'
FEDORA_CATALOGUE_PACKAGES = {
    'mate-polkit': ('mate-polkit',), 'Linux-PAM': ('pam',), 'gnome-shell': ('gnome-shell',),
}
RPM_LIST_COMMAND = ['/usr/bin/rpm', '-qa', '--queryformat', '%{NAME}\t%{VERSION}-%{RELEASE}\n']
RPM_FILE_FORMAT = '%{NAME}\t%{VERSION}-%{RELEASE}\t%{FILEDIGESTALGO}\n[%{FILENAMES}\t%{FILEDIGESTS}\n]'
GLYPHS = '中文密码授权取消身份验证'
LIMIT = 32 * 1024 * 1024
LOCALE_COMMAND = ['/usr/bin/env', 'LC_ALL=zh_CN.UTF-8', '/usr/bin/locale', 'charmap']


class LocalFiles:
    """Read-only local implementation of the existing guestfs reader interface."""
    def __init__(self, root=Path('/')):
        self.root = Path(root)

    def path(self, path):
        return self.root / path.lstrip('/')

    def lstatns(self, path):
        info = self.path(path).lstat()
        return {name: getattr(info, name) for name in (
            'st_dev', 'st_ino', 'st_mode', 'st_uid', 'st_gid', 'st_nlink',
            'st_size', 'st_mtime_ns', 'st_ctime_ns')}

    def realpath(self, path):
        relative = self.path(path).resolve().relative_to(self.root.resolve())
        return '/' if relative == Path('.') else '/' + str(relative)

    def filesize(self, path):
        return self.path(path).lstat().st_size

    def exists(self, path):
        return self.path(path).exists()

    def is_symlink(self, path):
        return self.path(path).is_symlink()

    def read_file(self, path):
        before = self.lstatns(path)
        fd = os.open(self.path(path), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, 'rb') as stream:
            require(all(getattr(os.fstat(fd), key) == value for key, value in before.items()), 'changed')
            data = stream.read(LIMIT + 1)
            require(all(getattr(os.fstat(fd), key) == value for key, value in before.items()), 'changed')
        require(self.lstatns(path) == before, 'changed')
        return data

    def command(self, argv):
        require(self.root == Path('/') and (argv in (LOCALE_COMMAND, RPM_LIST_COMMAND)
                or argv in [rpm_file_command(name) for name in FEDORA_PACKAGES]), 'read-command')
        result = subprocess.run(argv, check=True, timeout=10, capture_output=True,
                                env={'PATH': '/usr/bin:/bin'})
        require(result.stderr == b'', 'locale-runtime')
        require(len(result.stdout) <= 2 * 1024 * 1024, 'command-bound')
        return result.stdout.decode('utf-8')


def require(value, code):
    if not value:
        raise ValueError('baseline:chinese-' + code + '; run tools/prepare-vm')


def file_identity(g, path):
    # guestfs lstatns includes access times, unlike LocalFiles.lstatns. Reads
    # on bootstrap's writable mount may legitimately update atime. Preserve
    # the same inode/ownership/content-change identity on both readers, using
    # each API's nanosecond timestamp spelling.
    stable = {'st_dev', 'st_ino', 'st_mode', 'st_uid', 'st_gid', 'st_nlink', 'st_size',
              'st_mtime_ns', 'st_ctime_ns', 'st_mtime_sec', 'st_mtime_nsec',
              'st_ctime_sec', 'st_ctime_nsec'}
    return {key: value for key, value in g.lstatns(path).items() if key in stable}


def read(g, path, limit=LIMIT):
    """Fixed root-owned, bounded regular inputs; reject unsafe ancestors/replacement."""
    parents = {}
    for parent in reversed(Path(path).parents):
        name = str(parent)
        require(g.exists(name) and not g.is_symlink(name), 'parent')
        info = file_identity(g, name)
        require(g.realpath(name) == name and stat.S_ISDIR(info['st_mode'])
                and info['st_uid'] == info['st_gid'] == 0
                and not info['st_mode'] & 0o022, 'parent')
        parents[name] = info
    require(g.exists(path) and not g.is_symlink(path), 'missing-file')
    before = file_identity(g, path)
    require(g.realpath(path) == path and stat.S_ISREG(before['st_mode'])
            and before['st_uid'] == before['st_gid'] == 0
            and before['st_nlink'] == 1 and not before['st_mode'] & 0o022
            and 0 < g.filesize(path) <= limit, 'file')
    data = g.read_file(path)
    require(type(data) is bytes and 0 < len(data) <= limit
            and file_identity(g, path) == before
            and all(file_identity(g, name) == info and g.realpath(name) == name
                    for name, info in parents.items()), 'changed')
    return data


def font_coverage(data):
    """Independently inspect the installed font's Unicode format-12 cmap.

    This fixed Noto TTC profile needs only the first face and BMP Chinese
    characters. Unsupported/corrupt tables refuse rather than guessing coverage.
    """
    def unpack(fmt, offset):
        require(0 <= offset <= len(data) - struct.calcsize(fmt), 'font-table')
        return struct.unpack_from(fmt, data, offset)
    require(data[:4] == b'ttcf', 'font-format')
    count, = unpack('>I', 8)
    require(1 <= count <= 32, 'font-faces')
    face, = unpack('>I', 12)
    require(data[face:face + 4] in (b'OTTO', b'\x00\x01\x00\x00'), 'font-face')
    tables, = unpack('>H', face + 4)
    require(1 <= tables <= 128, 'font-tables')
    cmaps = []
    for index in range(tables):
        tag, _, offset, size = unpack('>4sIII', face + 12 + index * 16)
        require(offset + size <= len(data), 'font-table')
        if tag == b'cmap':
            cmaps.append((offset, size))
    require(len(cmaps) == 1, 'font-cmap')
    cmap, size = cmaps[0]
    version, records = unpack('>HH', cmap)
    require(version == 0 and 1 <= records <= 64, 'font-cmap')
    coverage = set()
    for index in range(records):
        platform, encoding, offset = unpack('>HHI', cmap + 4 + index * 8)
        if platform not in (0, 3) or platform == 3 and encoding != 10:
            continue
        sub = cmap + offset
        format_, = unpack('>H', sub)
        if format_ != 12:
            continue
        _, reserved, length, _, groups = unpack('>HHIII', sub)
        require(reserved == 0 and length == 16 + groups * 12
                and groups <= 100000 and offset + length <= size, 'font-groups')
        previous = -1
        for group in range(groups):
            start, end, glyph = unpack('>III', sub + 16 + group * 12)
            require(previous < start <= end <= 0x10ffff, 'font-group-order')
            previous = end
            coverage.update(char for char in GLYPHS if start <= ord(char) <= end
                            and glyph + ord(char) - start > 0)
    require(coverage == set(GLYPHS), 'font-coverage')
    return len(coverage)


def platform(g, os_id=None):
    """Pin the canonical release file, including Fedora's Workstation variant."""
    fields = {}
    for line in read(g, '/usr/lib/os-release', 64 * 1024).decode().splitlines():
        if '=' not in line or line.startswith('#'):
            continue
        key, value = line.split('=', 1)
        require(key not in fields, 'release')
        fields[key] = value.strip('"\'')
    found = fields.get('ID')
    require((found, fields.get('VERSION_ID')) == ('ubuntu', '26.04') or
            (found, fields.get('VERSION_ID'), fields.get('VARIANT_ID')) ==
            ('fedora', '44', 'workstation'), 'unsupported-platform')
    require(os_id is None or os_id == found, 'unsupported-platform')
    if found == 'fedora':
        config = read(g, '/etc/selinux/config', 64 * 1024).decode()
        require(re.findall(r'^SELINUX=(\S+)\s*$', config, re.M) == ['enforcing']
                and re.findall(r'^SELINUXTYPE=(\S+)\s*$', config, re.M) == ['targeted'], 'selinux')
        # Offline guestfs has no mounted securityfs. Live reads also require
        # enforcement now, without invoking a write or changing SELinux mode.
        if g.exists('/sys/fs/selinux/enforce'):
            require(g.read_file('/sys/fs/selinux/enforce').strip() == b'1', 'selinux')
    return found


def rpm_file_command(name):
    require(name in FEDORA_PACKAGES, 'package-identity')
    return ['/usr/bin/rpm', '-q', '--queryformat', RPM_FILE_FORMAT, name]


def rpm_inventory(g):
    raw = g.command(RPM_LIST_COMMAND)
    require(type(raw) is str and 0 < len(raw.encode()) <= 2 * 1024 * 1024, 'package-status')
    packages = {}
    for line in raw.splitlines():
        row = line.split('\t')
        require(len(row) == 2, 'package-status')
        name, version = row
        if name not in FEDORA_PACKAGES:
            continue
        require(name not in packages and re.fullmatch(r'[A-Za-z0-9.+:~\-]+', version), 'package-status')
        packages[name] = version
    records = {}
    for name, version in packages.items():
        raw = g.command(rpm_file_command(name))
        require(type(raw) is str and 0 < len(raw.encode()) <= 2 * 1024 * 1024, 'package-identity')
        lines = raw.splitlines()
        require(lines[0].split('\t') == [name, version, '8'], 'package-identity')
        files = {}
        for line in lines[1:]:
            row = line.split('\t')
            require(len(row) == 2 and row[0].startswith('/') and row[0] not in files, 'package-identity')
            files[row[0]] = row[1]
        records[name] = files
    return packages, records


def verify(g, os_id=None):
    os_id = platform(g, os_id)
    from guest_test_dependencies import verify_packages
    if os_id == 'fedora':
        packages, records = rpm_inventory(g)
        require(set(packages) == set(FEDORA_PACKAGES), 'missing-package')
    else:
        packages = verify_packages(read(g, '/var/lib/dpkg/status').decode(), PACKAGES)
    require(all(re.fullmatch(r'[A-Za-z0-9.+:~\-]+', value) for value in packages.values()),
            'package-version')
    files = {}
    def packaged(path, owners, limit=LIMIT):
        data = read(g, path, limit)
        if os_id == 'fedora':
            digests = [records[owner][path] for owner in owners if path in records[owner]]
            require(len(digests) == 1 and re.fullmatch('[0-9a-f]{64}', digests[0]), 'package-identity')
            require(hashlib.sha256(data).hexdigest() == digests[0], 'package-bytes')
            return data
        digests = []
        for owner in owners:
            manifest = f'/var/lib/dpkg/info/{owner}.md5sums'
            if not g.exists(manifest) and not g.is_symlink(manifest):
                continue
            rows = [line.split() for line in read(g, manifest, 2 * 1024 * 1024).decode().splitlines()]
            matches = [row[0] for row in rows if len(row) == 2 and row[1] == path.lstrip('/')]
            require(len(matches) <= 1 and all(re.fullmatch('[0-9a-f]{32}', digest)
                                             for digest in matches), 'package-identity')
            digests.extend(matches)
        require(hashlib.md5(data, usedforsecurity=False).hexdigest() in digests, 'package-bytes')
        return data
    locale_data = packaged(LOCALE_PATH, ('glibc-langpack-zh',) if os_id == 'fedora' else ('locales-all',))
    require(b'UTF-8\x00' in locale_data and b'Chinese' in locale_data, 'locale')
    # Execute only the distribution's read-only locale query, inside the guest
    # root for guestfs. Package names/IDENTIFICATION alone cannot prove a usable
    # generated locale or detect absent LC_CTYPE data.
    try:
        require(g.command(LOCALE_COMMAND) == 'UTF-8\n', 'locale-runtime')
    except (RuntimeError, subprocess.CalledProcessError, OSError) as error:
        raise ValueError('baseline:chinese-locale-runtime; run tools/prepare-vm') from error
    files[LOCALE_PATH] = hashlib.sha256(locale_data).hexdigest()
    translations = {}
    for domain, messages in CATALOGUES.items():
        candidates = [f'/usr/share/{directory}/zh_CN/LC_MESSAGES/{domain}.mo'
                      for directory in ('locale', 'locale-langpack')]
        present = [path for path in candidates if g.exists(path) or g.is_symlink(path)]
        require(len(present) == 1, 'catalogue-identity')
        owners = FEDORA_CATALOGUE_PACKAGES if os_id == 'fedora' else CATALOGUE_PACKAGES
        if os_id == 'fedora':
            require(present[0] == candidates[0], 'catalogue-identity')
        data = packaged(present[0], owners[domain], 2 * 1024 * 1024)
        catalog = gettext.GNUTranslations(io.BytesIO(data))
        values = [catalog.gettext(message) for message in messages]
        require(all(value != message and any('\u4e00' <= char <= '\u9fff' for char in value)
                    for message, value in zip(messages, values)), 'translation-fallback')
        files[present[0]] = hashlib.sha256(data).hexdigest()
        translations[domain] = len(messages)
    font_path = FEDORA_FONT_PATH if os_id == 'fedora' else FONT_PATH
    font = packaged(font_path, ('google-noto-sans-cjk-fonts',) if os_id == 'fedora' else ('fonts-noto-cjk',))
    glyphs = font_coverage(font)
    files[font_path] = hashlib.sha256(font).hexdigest()
    return {'profile': 'chinese', 'os_id': os_id, 'release': '44' if os_id == 'fedora' else '26.04',
            'locale': LOCALE, 'provider': 'mate-polkit', 'packages': packages,
            'translations': translations, 'cjk_glyphs': glyphs, 'files': files,
            'runtime_locale': 'UTF-8'}


def preflight(g, os_id='ubuntu'):
    """Only the distribution's recorded files may be adopted by preparation.

    Package managers own atomic placement and partial configured-package retry;
    this profile never overwrites a colliding unregistered input itself.
    """
    require(os_id in ('ubuntu', 'fedora'), 'unsupported-platform')
    paths = [LOCALE_PATH, FEDORA_FONT_PATH if os_id == 'fedora' else FONT_PATH]
    paths += [f'/usr/share/{directory}/zh_CN/LC_MESSAGES/{domain}.mo'
              for directory in ('locale', 'locale-langpack') for domain in CATALOGUES]
    owned = set()
    if os_id == 'fedora':
        platform(g, os_id)
        _, records = rpm_inventory(g)
        owned.update(path for files in records.values() for path in files)
    for name in (() if os_id == 'fedora' else ('locales-all', 'fonts-noto-cjk',
                 *(owner for owners in CATALOGUE_PACKAGES.values() for owner in owners))):
        listing = f'/var/lib/dpkg/info/{name}.list'
        if g.exists(listing) or g.is_symlink(listing):
            owned.update(read(g, listing, 2 * 1024 * 1024).decode().splitlines())
    for path in paths:
        ancestor = Path(path).parent
        while not g.exists(str(ancestor)) and not g.is_symlink(str(ancestor)):
            require(ancestor != ancestor.parent, 'parent')
            ancestor = ancestor.parent
        for parent in (ancestor, *ancestor.parents):
            name = str(parent)
            info = g.lstatns(name)
            require(g.realpath(name) == name and stat.S_ISDIR(info['st_mode'])
                    and info['st_uid'] == info['st_gid'] == 0
                    and not info['st_mode'] & 0o022, 'parent')
        if g.exists(path) or g.is_symlink(path):
            require(path in owned, 'unowned-collision')
            read(g, path)


def verify_transport(transport):
    """Same read-only oracle for RAM snapshots, before any product action."""
    modules = {'chinese_language_assets': Path(__file__),
               'guest_test_dependencies': Path(__file__).with_name('guest_test_dependencies.py')}
    source = 'import sys,types,json\n'
    for name in modules:
        source += f'{name}=types.ModuleType({name!r}); sys.modules[{name!r}]={name}\n'
    for name, path in modules.items():
        source += f'exec({path.read_text()!r},{name}.__dict__)\n'
    source += 'print(json.dumps(chinese_language_assets.verify(chinese_language_assets.LocalFiles()),sort_keys=True))\n'
    raw = transport.call(['/usr/bin/python3', '-I', '-'], input=source.encode(), timeout=90)
    require(type(raw) is bytes and 0 < len(raw) <= 8192, 'response-bound')
    value = json.loads(raw)
    require(type(value) is dict and raw == (json.dumps(value, sort_keys=True) + '\n').encode(), 'response')
    validate_receipt(value)
    return value


def validate_receipt(value):
    require(type(value) is dict and (value.get('os_id'), value.get('release'))
            in (('ubuntu', '26.04'), ('fedora', '44')), 'receipt-platform')
    fedora = value['os_id'] == 'fedora'
    require(type(value) is dict and set(value) == {
        'profile', 'os_id', 'release', 'locale', 'provider', 'packages',
        'translations', 'cjk_glyphs', 'files', 'runtime_locale'} and value['profile'] == 'chinese'
        and value['locale'] == LOCALE and value['provider'] == 'mate-polkit'
        and value['runtime_locale'] == 'UTF-8'
        and type(value['packages']) is dict
        and set(value['packages']) == (set(FEDORA_PACKAGES) if fedora else
                                      {item.split('=')[0] for item in PACKAGES})
        and all(type(version) is str and re.fullmatch(r'[A-Za-z0-9.+:~\-]+', version)
                for version in value['packages'].values())
        and value['translations'] == {domain: len(messages) for domain, messages in CATALOGUES.items()}
        and value['cjk_glyphs'] == len(set(GLYPHS)) and type(value['files']) is dict,
        'receipt')
    expected = {LOCALE_PATH, FEDORA_FONT_PATH if fedora else FONT_PATH}
    for domain in CATALOGUES:
        candidates = {f'/usr/share/{directory}/zh_CN/LC_MESSAGES/{domain}.mo'
                      for directory in (('locale',) if fedora else ('locale', 'locale-langpack'))}
        selected = set(value['files']) & candidates
        require(len(selected) == 1, 'receipt-catalogue')
        expected.update(selected)
    require(set(value['files']) == expected and all(type(digest) is str
            and re.fullmatch('[0-9a-f]{64}', digest) for digest in value['files'].values()), 'receipt-files')
