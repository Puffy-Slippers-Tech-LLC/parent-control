#!/usr/bin/python3 -IB
"""Install machine-wide reads and render checkout-specific Codex prefixes."""
import json
import os
from pathlib import Path
import sys
import stat
import tempfile


SYSTEM_RULES = Path('/etc/codex/rules/onpc-read-only.rules')


def install_system_rules(root, destination=SYSTEM_RULES):
    """Manage only our rule file; preserve all other system and user policies."""
    data = (root / 'config/codex-read-only.rules').read_bytes()
    if any(path.is_symlink() for path in (destination, *destination.parents)):
        raise ValueError('symlink in system rules path')
    destination.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    for path in destination.parents:
        info = path.stat()
        # Repair only the two root-owned Codex directories managed by setup.
        # Ancestors such as /etc must already be trusted; never relax checks.
        if (path in (destination.parent, destination.parent.parent)
                and info.st_uid == info.st_gid == 0 and info.st_mode & 0o022):
            path.chmod(stat.S_IMODE(info.st_mode) & ~0o022)
            info = path.stat()
            print('codex-rules-install: secured managed Codex directory permissions')
        if info.st_uid != 0 or info.st_mode & 0o022:
            raise ValueError('unsafe system rules directory')
    if destination.exists():
        info = destination.stat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError('unsafe system rules file')
        if (destination.read_bytes() == data and info.st_uid == 0 and info.st_gid == 0
                and stat.S_IMODE(info.st_mode) == 0o644):
            print('codex-rules-install: machine-wide read rules already current')
            return
    descriptor, temporary = tempfile.mkstemp(prefix='.onpc-rules-', dir=destination.parent)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fchmod(stream.fileno(), 0o644)
            os.fchown(stream.fileno(), 0, 0)
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    finally:
        Path(temporary).unlink(missing_ok=True)
    print('codex-rules-install: installed machine-wide read rules')


def render(root):
    for name in ('run-unit-tests', 'run-ui-tests', 'run-tests', 'diagnose', 'test-vm',
                 'cleanup-screenshots', 'read-only'):
        path = root / 'tools' / name
        if not path.is_file() or path.is_symlink() or not os.access(path, os.X_OK):
            raise ValueError('missing or nonexecutable launcher; restore checkout executable modes')
    source = (root / 'config/codex-tests.rules').read_text()
    # Replace inside Starlark string literals; quoted spaces remain one argv token.
    return source.replace('@CHECKOUT@', json.dumps(str(root))[1:-1])


def main():
    root = Path(__file__).resolve().parents[1]
    if sys.argv[1:] == ['--system'] and os.geteuid() == 0:
        install_system_rules(root)
        return
    if len(sys.argv) != 1:
        raise ValueError('run through ./setup.sh --codex-rules-only')
    source = render(root)
    destination = root / '.codex/rules/tests.rules'
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_symlink():
        raise ValueError('symlink in checkout rules path')
    if not destination.exists() or destination.read_text() != source:
        destination.write_text(source)
    destination.chmod(0o644)


if __name__ == '__main__':
    try:
        main()
    except ValueError as error:
        sys.exit(f'codex-rules-install: {error}')
    except OSError as error:
        sys.exit(f'codex-rules-install: filesystem operation failed (errno={error.errno})')
