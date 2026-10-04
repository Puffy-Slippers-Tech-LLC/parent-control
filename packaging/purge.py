#!/usr/bin/python3
"""Explicit saved-data deletion through native transactions and shared cleanup."""
from __future__ import annotations

import json
import os
from pathlib import Path
import platform
import stat
import subprocess
import sys

PRODUCT = 'oh-no-parent-control'
CLEANUP = Path('/usr/share/oh-no-parent-control/lifecycle/postrm')


def distribution(release):
    if release.get('ID') == 'ubuntu':
        return 'ubuntu'
    if (release.get('ID'), release.get('VERSION_ID'), release.get('VARIANT_ID')) == (
            'fedora', '44', 'workstation'):
        return 'fedora'
    raise ValueError('purge:unsupported-distribution')


def secure(path, *, directory=True, missing=False):
    for parent in reversed(path.parents):
        info = parent.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            raise ValueError('purge:unsafe-ancestor')
    try:
        info = path.lstat()
    except FileNotFoundError:
        if missing:
            return
        raise
    expected = stat.S_ISDIR if directory else stat.S_ISREG
    if not expected(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
        raise ValueError('purge:unsafe-owned-path')
    if not directory and info.st_nlink != 1:
        raise ValueError('purge:unsafe-owned-file-links')


def cleanup_source():
    secure(CLEANUP, directory=False)
    descriptor = os.open(CLEANUP, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, 'r', encoding='utf-8') as stream:
        info = os.fstat(stream.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022
                or info.st_nlink != 1 or info.st_size > 512 * 1024):
            raise ValueError('purge:unsafe-cleanup-source')
        return stream.read()


def rpm_installed():
    result = subprocess.run(['rpm', '-qa', '--queryformat', '%{NAME}\n'],
                            check=True, text=True, stdout=subprocess.PIPE)
    return PRODUCT in result.stdout.splitlines()


def verify_fedora_pam():
    subprocess.run(['authselect', 'check'], check=True)
    current = subprocess.run(['authselect', 'current', '--raw'], check=True,
                             text=True, stdout=subprocess.PIPE).stdout.split()
    if not current or current[0] == 'custom/' + PRODUCT:
        raise ValueError('purge:product-pam-still-selected')
    record = Path('/var/lib/oh-no-parent-control/fedora-authselect.json')
    if record.exists() or record.is_symlink():
        secure(record, directory=False)
        value = json.loads(record.read_text())
        original = value.get('original') if isinstance(value, dict) else None
        if not isinstance(original, list) or current != original:
            raise ValueError('purge:original-pam-not-restored')
    for path in Path('/etc/pam.d').iterdir():
        if path.name.endswith(('.pam-old', '.pam-new', '.dpkg-old', '.dpkg-dist', '~')):
            continue
        if path.is_file():
            for line in path.read_text().splitlines():
                if line.strip() and not line.lstrip().startswith('#') and (
                        'pam_oh_no_parent_control.so' in line or
                        '/usr/libexec/oh-no-parent-control-' in line):
                    raise ValueError('purge:product-pam-reference-remains')


def purge(*, yes=False):
    if os.geteuid() != 0:
        raise ValueError('purge:root-required')
    target = distribution(platform.freedesktop_os_release())
    # Read trusted package-owned bytes before the transaction erases this
    # executable and its source. No erased product import/helper is needed.
    source = cleanup_source()
    if target == 'ubuntu':
        identity = subprocess.run(['dpkg-query', '-W', '-f=${Package}', PRODUCT],
                                  check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
        if identity != PRODUCT:
            raise ValueError('purge:package-identity')
        subprocess.run(['apt-get', '-o', 'DPkg::Lock::Timeout=120', 'purge',
                        *(['-y'] if yes else []), PRODUCT],
                       check=True)
        return
    if not rpm_installed():
        raise ValueError('purge:package-not-installed')
    subprocess.run(['dnf', 'remove', '--no-autoremove', *(['-y'] if yes else []), PRODUCT], check=True)
    if rpm_installed():
        raise ValueError('purge:package-still-installed')
    for path in (Path('/var/lib/oh-no-parent-control'), Path('/var/log/oh-no-parent-control')):
        secure(path, missing=True)
    verify_fedora_pam()
    # The standalone shared postrm retries all remaining owned integrations,
    # accounts and execution-policy restoration before deleting saved data.
    # Exact roots, symlink/mount refusals and retained retry records remain
    # shared with Debian purge; this adds no independent deletion algorithm.
    subprocess.run(['/bin/sh', '-s', '--', 'purge'], input=source, text=True, check=True)


def main():
    if sys.argv[1:] not in ([], ['--yes']):
        raise ValueError('purge:no-arguments-accepted')
    purge(yes=sys.argv[1:] == ['--yes'])


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f'purge: {error}', file=sys.stderr)
        sys.exit(getattr(error, 'returncode', 1))
