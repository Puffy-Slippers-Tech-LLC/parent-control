#!/usr/bin/python3
"""Install the development test dispatcher, bound to this checkout."""

import os
from pathlib import Path
import sys
import tempfile


def main():
    if len(sys.argv) != 1 or os.geteuid() != 0:
        raise SystemExit('test-runner-install: run as root without arguments')
    root = Path(__file__).resolve().parents[1]
    source = (root / 'tools/onpc-test-runner').read_text()
    source = source.replace('CHECKOUT = None  # Replaced with an absolute path by install_test_runner.py.',
                            f'CHECKOUT = {str(root)!r}')
    destination = Path('/usr/local/libexec/onpc-test-runner')
    destination.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix='.onpc-test-runner-', dir=destination.parent)
    try:
        with os.fdopen(descriptor, 'w') as stream:
            stream.write(source)
            stream.flush()
            os.fchmod(stream.fileno(), 0o755)
            os.fchown(stream.fileno(), 0, 0)
        os.replace(temporary, destination)
    finally:
        Path(temporary).unlink(missing_ok=True)
    destination = Path('/usr/local/libexec/onpc-export-screenshot')
    descriptor, temporary = tempfile.mkstemp(prefix='.onpc-export-screenshot-', dir=destination.parent)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write((root / 'tools/onpc-export-screenshot').read_bytes())
            stream.flush()
            os.fchmod(stream.fileno(), 0o755)
            os.fchown(stream.fileno(), 0, 0)
        os.replace(temporary, destination)
    finally:
        Path(temporary).unlink(missing_ok=True)
    # Install authorization only after the validated, root-owned helper exists.
    # polkitd watches this directory; activation is immediate (none).
    destination = Path('/etc/polkit-1/rules.d/50-onpc-screenshot-export.rules')
    descriptor, temporary = tempfile.mkstemp(prefix='.onpc-screenshot-policy-', dir=destination.parent)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write((root / 'config/50-onpc-screenshot-export.rules').read_bytes())
            stream.flush()
            os.fchmod(stream.fileno(), 0o644)
            os.fchown(stream.fileno(), 0, 0)
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    finally:
        Path(temporary).unlink(missing_ok=True)
    print('test-runner-install: installed root-owned development tools and scoped screenshot authorization')


if __name__ == '__main__':
    main()
