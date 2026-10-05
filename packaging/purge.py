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
INTENT = Path('/run/oh-no-parent-control-purge-intent.json')
INTENT_PURPOSE = 'onpc-native-rpm-purge-v1'


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


def debian_purged():
    result = subprocess.run(['dpkg-query', '-W', '-f=${Package}\t${db:Status-Abbrev}\n'],
                            check=True, text=True, stdout=subprocess.PIPE)
    for row in result.stdout.splitlines():
        fields = row.split('\t')
        if fields[0] == PRODUCT and (len(fields) != 2 or fields[1][1:2] != 'n'):
            return False
    return True


def verify_purged_data():
    for path in (Path('/var/lib/oh-no-parent-control'), Path('/var/log/oh-no-parent-control')):
        if path.exists() or path.is_symlink():
            raise ValueError('purge:saved-data-remains')


def process_identity(pid):
    """Use the public proc ABI; command names never establish ownership."""
    info = os.stat(f'/proc/{pid}')
    with open(f'/proc/{pid}/stat', encoding='ascii') as stream:
        value = stream.read(8193)
    fields = value.rpartition(') ')[2].split()
    if len(value) > 8192 or len(fields) < 20 or info.st_uid != 0:
        raise ValueError('purge:unsafe-intent-process')
    return int(fields[1]), int(fields[19])


def current_boot():
    with open('/proc/sys/kernel/random/boot_id', encoding='ascii') as stream:
        return stream.read(128).strip()


def read_intent():
    secure(INTENT, directory=False, missing=True)
    try:
        descriptor = os.open(INTENT, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    except FileNotFoundError:
        return None
    with os.fdopen(descriptor, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_nlink != 1
                or stat.S_IMODE(info.st_mode) != 0o600 or info.st_size > 1024):
            raise ValueError('purge:unsafe-intent')
        raw = stream.read(1025)
    if len(raw) > 1024:
        raise ValueError('purge:unsafe-intent')
    value = json.loads(raw)
    if (not isinstance(value, dict) or set(value) != {
            'purpose', 'owner_pid', 'owner_start', 'boot_id'} or
            value['purpose'] != INTENT_PURPOSE or
            type(value['owner_pid']) is not int or value['owner_pid'] <= 1 or
            type(value['owner_start']) is not int or value['owner_start'] <= 0 or
            not isinstance(value['boot_id'], str) or len(value['boot_id']) != 36):
        raise ValueError('purge:invalid-intent')
    return value, (info.st_dev, info.st_ino)


def remove_intent(identity):
    """Remove only the exact file created or consumed by this operation."""
    try:
        info = INTENT.lstat()
    except FileNotFoundError:
        return
    if (info.st_dev, info.st_ino) != identity or not stat.S_ISREG(info.st_mode):
        raise ValueError('purge:intent-replaced')
    INTENT.unlink()


def begin_intent():
    existing = read_intent()
    if existing:
        value, identity = existing
        live = False
        if value['boot_id'] == current_boot():
            try:
                live = process_identity(value['owner_pid'])[1] == value['owner_start']
            except FileNotFoundError:
                pass
        if live:
            raise ValueError('purge:already-running')
        remove_intent(identity)
    value = {'purpose': INTENT_PURPOSE, 'owner_pid': os.getpid(),
             'owner_start': process_identity(os.getpid())[1], 'boot_id': current_boot()}
    descriptor = os.open(INTENT, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    info = os.fstat(descriptor)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(json.dumps(value).encode('ascii'))
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        remove_intent((info.st_dev, info.st_ino))
        raise
    return info.st_dev, info.st_ino


def rpm_removal_phase():
    """Select purge only inside the native transaction descended from its CLI.

    Stale, canceled and unrelated intents retain ordinary removal behavior.
    This verifier is embedded in RPM postun and needs no erased payload.
    """
    if os.geteuid() != 0:
        return 'remove'
    try:
        intent = read_intent()
        if intent is None:
            return 'remove'
        value, identity = intent
        if value['boot_id'] != current_boot():
            return 'remove'
        pid = os.getpid()
        matched = False
        for _ in range(32):
            parent, start = process_identity(pid)
            if pid == value['owner_pid'] and start == value['owner_start']:
                matched = True
                break
            if parent <= 1 or parent == pid:
                return 'remove'
            pid = parent
    except (OSError, ValueError, json.JSONDecodeError):
        # A foreign/malformed marker can never upgrade an unrelated erase to
        # purge. Matching transaction PAM failures fail below.
        return 'remove'
    if not matched:
        return 'remove'
    # PAM restoration is still checked before deleting saved data, while RPM
    # holds the transaction boundary against reinstall. Failure keeps intent
    # and saved restoration records until the CLI's owned finally cleanup.
    verify_fedora_pam()
    remove_intent(identity)
    return 'purge'


def verify_fedora_pam():
    # The embedded RPM verifier's stdout is a finite shell action token.
    # Native status prose must not become part of that token.
    subprocess.run(['authselect', 'check'], check=True, stdout=subprocess.PIPE)
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
    cleanup_source()
    for path in (Path('/var/lib/oh-no-parent-control'), Path('/var/log/oh-no-parent-control')):
        secure(path, missing=True)
    if target == 'ubuntu':
        identity = subprocess.run(['dpkg-query', '-W', '-f=${Package}', PRODUCT],
                                  check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
        if identity != PRODUCT:
            raise ValueError('purge:package-identity')
        subprocess.run(['apt-get', '-o', 'DPkg::Lock::Timeout=120', 'purge',
                        *(['-y'] if yes else []), PRODUCT],
                       check=True)
        if not debian_purged():
            raise ValueError('purge:package-not-purged')
        verify_purged_data()
        print('oh-no-parent-control: saved-state purge outcome=accepted')
        return
    if not rpm_installed():
        raise ValueError('purge:package-not-installed')
    intent = begin_intent()
    try:
        subprocess.run(['dnf', 'remove', '--no-autoremove', *(['-y'] if yes else []), PRODUCT], check=True)
    finally:
        remove_intent(intent)
    if rpm_installed():
        raise ValueError('purge:package-still-installed')
    for path in (Path('/var/lib/oh-no-parent-control'), Path('/var/log/oh-no-parent-control')):
        secure(path, missing=True)
    verify_fedora_pam()
    # Native RPM postun consumed this action's live process-bound intent and
    # performed shared guarded purge while the transaction excluded reinstall.
    # There is deliberately no destructive work after the native lock releases.
    verify_purged_data()
    print('oh-no-parent-control: saved-state purge outcome=accepted')
    # DNF prints transaction progress after postun's reminder. Repeat it only
    # after successful verification, without creating/removing runtime state.
    sys.stdout.flush()
    notice = '*** REBOOT REQUIRED: reboot to finish removing Oh No! Parent Control. ***'
    if sys.stderr.isatty() and os.environ.get('TERM', '') not in ('', 'dumb'):
        notice = '\033[1;31m' + notice + '\033[0m'
    print(notice, file=sys.stderr)


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
