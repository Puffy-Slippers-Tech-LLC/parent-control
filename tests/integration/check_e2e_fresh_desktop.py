#!/usr/bin/python3
"""Qualify fresh Parent and standard fixture desktops in separate VM attempts."""

from pathlib import Path
import sys
from check_graphical_smoke import main as smoke

ASSETS = Path('/tmp/onpc-parent-setup-input')


def main():
    for role in ('parent', 'standard'):
        result = smoke(assets=ASSETS, provision_credentials=True,
                       fresh_desktop=role)
        if result:
            return result
    return 0


if __name__ == '__main__':
    sys.exit(main())
