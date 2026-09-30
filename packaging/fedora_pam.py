#!/usr/bin/python3
"""Own a custom authselect profile without overwriting administrator PAM edits."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess

PROFILE = 'custom/oh-no-parent-control'
PROFILE_DIR = Path('/etc/authselect/custom/oh-no-parent-control')
STATE = Path('/var/lib/oh-no-parent-control/fedora-authselect.json')
STACK = Path('/usr/share/oh-no-parent-control/pam/managed-stack')
PAM_DIR = Path('/etc/pam.d')
PAM_FILES = ('system-auth', 'password-auth', 'fingerprint-auth', 'smartcard-auth')
BEGIN = '# BEGIN Oh No! Parent Control managed PAM\n'
END = '# END Oh No! Parent Control managed PAM\n'


def run(*arguments, capture=False):
    return subprocess.run(['authselect', *arguments], check=True, text=True,
                          stdout=subprocess.PIPE if capture else None)


def selection():
    values = run('current', '--raw', capture=True).stdout.split()
    if not values or any(not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_/-]*', v) or '..' in v
                         for v in values):
        raise ValueError('invalid authselect selection')
    return values


def secure(path: Path, *, directory=False):
    # Root-owned ancestors, including custom-profile and private state roots.
    for parent in reversed(path.parents):
        info = parent.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            raise ValueError('unsafe authselect path ancestor')
    info = path.lstat()
    expected = stat.S_ISDIR if directory else stat.S_ISREG
    if not expected(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
        raise ValueError('unsafe authselect ownership or substituted path')


def digests():
    secure(PROFILE_DIR, directory=True)
    result = {}
    for path in sorted(PROFILE_DIR.rglob('*')):
        if path.is_dir() and not path.is_symlink():
            secure(path, directory=True)
            continue
        secure(path)
        result[path.relative_to(PROFILE_DIR).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def save(record):
    # The shared preinst has already created and checked the private state root.
    secure(STATE.parent, directory=True)
    if STATE.exists() or STATE.is_symlink():
        secure(STATE)
    temporary = STATE.with_suffix('.pending')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(record, stream)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, STATE)
    finally:
        temporary.unlink(missing_ok=True)


def verify_pam(*, installed):
    for name in PAM_FILES:
        contents = (PAM_DIR / name).read_text()
        has_module = 'pam_oh_no_parent_control.so' in contents
        has_gate = '/usr/libexec/oh-no-parent-control-login-check' in contents
        if (installed and not (has_module and has_gate)) or (not installed and (has_module or has_gate)):
            raise ValueError('PAM integration does not match the requested state')


def configure(action):
    run('check')  # Never use --force or adopt locally edited generated stacks.
    current = selection()
    record = None
    if STATE.exists() or STATE.is_symlink():
        secure(STATE)
        record = json.loads(STATE.read_text())
        original = record.get('original') if isinstance(record, dict) else None
        if (not isinstance(record, dict) or record.get('version') != 1
                or not isinstance(original, list) or not original
                or any(not isinstance(v, str) or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_/-]*', v)
                       or '..' in v for v in original)
                or original[0] == PROFILE or not isinstance(record.get('files'), dict)
                or any(not isinstance(k, str) or Path(k).is_absolute() or '..' in Path(k).parts
                       or not isinstance(v, str) or not re.fullmatch(r'[a-f0-9]{64}', v)
                       for k, v in record['files'].items())
                or record.get('phase') not in ('creating', 'prepared', 'installed', 'restored')):
            raise ValueError('invalid original authselect selection')
    if action == 'remove' and record is None:
        verify_pam(installed=False)
        return
    if record is None:
        if current[0] == PROFILE or PROFILE_DIR.exists() or PROFILE_DIR.is_symlink():
            raise ValueError('reserved authselect profile already exists; preserving it')
        if 'without-nullok' in current[1:]:
            raise ValueError('current PAM profile disallows the passwordless kiosk; preserving it')
        record = dict(version=1, original=current, files={}, phase='creating')
        save(record)
    if action == 'install':
        if current not in (record['original'], [PROFILE, *record['original'][1:]]):
            raise ValueError('authselect selection changed; preserving it')
        existing = PROFILE_DIR.exists() or PROFILE_DIR.is_symlink()
        if existing:
            if not record['files'] or digests() != record['files']:
                raise ValueError('package authselect profile changed; preserving it')
        else:
            run('create-profile', 'oh-no-parent-control', '-b', record['original'][0])
        replacement = {}
        stack = BEGIN + STACK.read_text() + END
        for name in PAM_FILES:
            path = PROFILE_DIR / name
            secure(path)
            contents = path.read_text()
            if existing:
                if not contents.startswith(BEGIN) or contents.count(END) != 1:
                    raise ValueError('invalid owned managed PAM block')
                contents = contents.split(END, 1)[1]
            else:
                if 'pam_malcontent.so' in contents or 'pam_oh_no_parent_control.so' in contents:
                    raise ValueError('base profile has conflicting parental-control PAM modules')
            replacement[path] = stack + contents
        for path, contents in replacement.items():
            path.write_text(contents)
        record['files'] = digests()
        record['phase'] = 'prepared'
        save(record)
        run('select', PROFILE, *record['original'][1:])
        run('check')
        verify_pam(installed=True)
        record['phase'] = 'installed'
        save(record)
    else:
        if current != [PROFILE, *record['original'][1:]]:
            if current == record['original'] and record['phase'] == 'restored':
                verify_pam(installed=False)
                return
            raise ValueError('authselect selection changed; resolve it before removal')
        if digests() != record['files']:
            raise ValueError('package authselect profile changed; preserving it')
        run('select', *record['original'])
        run('check')
        verify_pam(installed=False)
        # Only our verified files; never follow links or delete foreign additions.
        for name in record['files']:
            (PROFILE_DIR / name).unlink()
        for path in sorted(PROFILE_DIR.rglob('*'), reverse=True):
            path.rmdir()
        PROFILE_DIR.rmdir()
        record['phase'] = 'restored'
        save(record)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('install', 'remove'))
    arguments = parser.parse_args()
    if os.geteuid() != 0:
        parser.exit(1, 'fedora-pam: must run as root\n')
    try:
        configure(arguments.action)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'fedora-pam: {error}\n')
