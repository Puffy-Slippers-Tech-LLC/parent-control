"""Persistent guest mounts derived from the selected domain's virtiofs exports."""

import json
from pathlib import PurePosixPath
import re
import stat
import xml.etree.ElementTree as ET

RECORD = '/var/lib/onpc-baseline-preparation/mounts.json'


def require(condition):
    if not condition:
        raise ValueError('guest:virtiofs-mapping-conflict')


def mappings(xml):
    result = []
    for node in ET.fromstring(xml).findall('devices/filesystem'):
        driver = node.find('driver')
        if driver is None or driver.get('type') != 'virtiofs':
            continue
        source, target = node.find('source'), node.find('target')
        require(node.get('type') == 'mount' and source is not None and target is not None)
        path, tag = source.get('dir', ''), target.get('dir', '')
        require(path.startswith('/') and not path.startswith('//')
                and len(PurePosixPath(path).parts) > 1
                and str(PurePosixPath(path)) == path
                and '..' not in PurePosixPath(path).parts
                and not any(ord(char) < 32 for char in path)
                and tag and not any(char.isspace() or ord(char) < 32 for char in tag))
        # Never hide operating-system or preparation inputs behind a host export.
        require(PurePosixPath(path).parts[1] not in (
            'bin', 'sbin', 'etc', 'usr', 'var', 'proc', 'sys', 'dev', 'run', 'boot', 'lib', 'lib64'))
        require(all(tag != item['tag'] and path != item['path']
                    and not path.startswith(item['path'] + '/')
                    and not item['path'].startswith(path + '/') for item in result))
        result.append(dict(path=path, tag=tag, readonly=node.find('readonly') is not None))
    return sorted(result, key=lambda item: item['path'])


def escape(value):
    return ''.join('\\%03o' % ord(char) if char in '\\ \t\n#' else char for char in value)


def unescape(value):
    return re.sub(r'\\([0-7]{3})', lambda match: chr(int(match[1], 8)), value)


def reconcile(g, declared):
    """Append missing mappings, preserving matching and unrelated fstab bytes."""
    if not declared:
        return
    info = g.lstatns('/etc/fstab')
    require(g.realpath('/etc/fstab') == '/etc/fstab' and stat.S_ISREG(info['st_mode'])
            and info['st_uid'] == 0 and info['st_nlink'] == 1
            and not info['st_mode'] & 0o022)
    original = g.read_file('/etc/fstab').decode('utf-8')
    rows = [line.split() for line in original.splitlines()
            if line.strip() and not line.lstrip().startswith('#')]
    additions = []
    # Audit the complete declaration before writing any configuration.
    for item in declared:
        path, tag = item['path'], item['tag']
        matches = [row for row in rows if len(row) >= 2 and (
            unescape(row[1]) == path or (unescape(row[0]) == tag
                                        and len(row) >= 3 and row[2] == 'virtiofs'))]
        require(len(matches) <= 1)
        if matches:
            row = matches[0]
            require(len(row) >= 4 and unescape(row[0]) == tag
                    and unescape(row[1]) == path and row[2] == 'virtiofs'
                    and ('ro' in row[3].split(',')) == item['readonly']
                    and 'noauto' not in row[3].split(','))
        point = ''
        for part in PurePosixPath(path).parts[1:]:
            point += '/' + part
            if g.exists(point) or g.is_symlink(point):
                current = g.lstatns(point)
                require(g.realpath(point) == point and stat.S_ISDIR(current['st_mode'])
                        and current['st_uid'] == 0 and not current['st_mode'] & 0o022)
        if not matches:
            require(not g.exists(path) or not g.ls(path))
            options = 'ro' if item['readonly'] else 'defaults'
            additions.append(f'{escape(tag)} {escape(path)} virtiofs {options},nofail 0 0\n')
    for item in declared:
        point = ''
        for part in PurePosixPath(item['path']).parts[1:]:
            point += '/' + part
            if not g.exists(point):
                g.mkdir(point)
                g.chmod(0o755, point)
    if additions:
        updated = original + ('\n' if original and not original.endswith('\n') else '')
        contents = (updated + ''.join(additions)).encode('utf-8')
        # Match the baseline reconcilers' durable replace pattern: an interrupted
        # write must never leave the guest with a truncated boot mount table.
        temporary = '/etc/fstab.onpc-baseline-new'
        if g.exists(temporary) or g.is_symlink(temporary):
            current = g.lstatns(temporary)
            require(g.realpath(temporary) == temporary and stat.S_ISREG(current['st_mode'])
                    and current['st_uid'] == 0 and current['st_nlink'] == 1
                    and not current['st_mode'] & 0o022)
        g.write(temporary, contents)
        g.chown(0, info['st_gid'], temporary)
        g.chmod(stat.S_IMODE(info['st_mode']), temporary)
        require(g.read_file(temporary) == contents)
        g.sync()
        g.mv(temporary, '/etc/fstab')
        g.sync()
        require(g.read_file('/etc/fstab') == contents)


def mount_and_verify(runner):
    """Require the actual kernel mount, including during later preparation boots."""
    with open(RECORD, encoding='utf-8') as stream:
        declared = json.load(stream)
    for item in declared:
        command = ['findmnt', '--json', '--mountpoint', item['path'],
                   '--output', 'SOURCE,FSTYPE,OPTIONS']
        result = runner.run(command, check=False)
        if result.returncode == 1:
            runner.run(['mount', '--', item['path']])
            result = runner.run(command)
        require(result.returncode == 0)
        rows = json.loads(result.stdout).get('filesystems', [])
        require(len(rows) == 1 and rows[0]['source'] == item['tag']
                and rows[0]['fstype'] == 'virtiofs'
                and ('ro' in rows[0]['options'].split(',')) == item['readonly'])
