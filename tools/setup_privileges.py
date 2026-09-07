#!/usr/bin/python3 -IB
"""Internal setup.sh module: check authorization before invoking fixed setup."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dev_privileges import launch


if __name__ == '__main__':
    try:
        launch('/usr/local/libexec/onpc-setup', sys.argv[1:])
    except (ValueError, OSError):
        sys.exit('setup: noninteractive setup authorization unavailable; '
                 'use an active local administrator session; if the helper is missing, '
                 'run ./setup.sh --bootstrap-tools; repair a denied installation by running '
                 './setup.sh --bootstrap-tools from an administrator-authorized root session')
