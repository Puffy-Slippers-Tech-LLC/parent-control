#!/usr/bin/python3 -IB
"""Render checkout-specific Codex prefixes through the authorized setup entry point."""
import json
import os
from pathlib import Path
import sys


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
    if len(sys.argv) != 1:
        raise ValueError('run through ./setup.sh without helper arguments')
    root = Path(__file__).resolve().parents[1]
    source = render(root)
    destination = root / '.codex/rules/tests.rules'
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(source)
    destination.chmod(0o644)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError):
        sys.exit('codex-rules-install: validation or installation failed')
