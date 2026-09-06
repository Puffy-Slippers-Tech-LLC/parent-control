#!/usr/bin/python3
"""Install and reload the narrow development-host libvirtd socket rule."""

import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
PROFILE = Path('/etc/apparmor.d/usr.sbin.libvirtd')
LOCAL = Path('/etc/apparmor.d/local/usr.sbin.libvirtd')
BEGIN = '# BEGIN onpc graphical development tests\n'
END = '# END onpc graphical development tests\n'
INCLUDE = 'include if exists <local/usr.sbin.libvirtd>'


def updated_local(existing, rule):
    block = BEGIN + rule.rstrip() + '\n' + END
    if BEGIN not in existing and END not in existing:
        return existing + ('\n' if existing and not existing.endswith('\n') else '') + block
    if existing.count(BEGIN) != 1 or existing.count(END) != 1:
        raise ValueError('graphical-policy:ambiguous-managed-block')
    before, rest = existing.split(BEGIN)
    if END not in rest:
        raise ValueError('graphical-policy:invalid-managed-block')
    _, after = rest.split(END)
    return before + block + after


def trusted_file(path):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
        raise ValueError('graphical-policy:unsafe-system-file')
    return path.read_text()


def install():
    profile, existing = trusted_file(PROFILE), trusted_file(LOCAL)
    if profile.count(INCLUDE) != 1:
        raise ValueError('graphical-policy:unsupported-local-include')
    rule = (ROOT / 'config/apparmor/onpc-graphical-tests').read_text()
    updated = updated_local(existing, rule)
    # Compile the whole proposed profile before modifying any system policy.
    with tempfile.NamedTemporaryFile(mode='w', prefix='onpc-apparmor-', suffix='.profile') as check:
        check.write(profile.replace(INCLUDE, updated))
        check.flush()
        subprocess.run(['/usr/sbin/apparmor_parser', '--skip-kernel-load', '--skip-cache',
                        '--base=/etc/apparmor.d', check.name], check=True)
    if updated != existing:
        descriptor, temporary = tempfile.mkstemp(prefix='.onpc-graphical-', dir=LOCAL.parent)
        try:
            with os.fdopen(descriptor, 'w') as stream:
                stream.write(updated)
                stream.flush()
                os.fchmod(stream.fileno(), 0o644)
                os.fsync(stream.fileno())
            if trusted_file(LOCAL) != existing:
                raise ValueError('graphical-policy:local-file-changed')
            os.replace(temporary, LOCAL)
        finally:
            Path(temporary).unlink(missing_ok=True)
    # Retry also reloads: a previous failed kernel load must not appear applied.
    subprocess.run(['/usr/sbin/apparmor_parser', '--replace', '--skip-cache', str(PROFILE)], check=True)
    print('graphical-policy: libvirtd anonymous stream peer rule installed and reloaded')


def main():
    if len(sys.argv) != 1 or os.geteuid() != 0:
        raise SystemExit('graphical-policy: run as root without arguments')
    install()


if __name__ == '__main__':
    main()
