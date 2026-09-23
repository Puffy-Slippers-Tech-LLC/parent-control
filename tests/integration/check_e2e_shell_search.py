#!/usr/bin/python3
"""Qualify administrator launch and standard unavailability in owned attempts."""

from pathlib import Path
import sys
from check_graphical_smoke import main as smoke

ASSETS = Path('/tmp/onpc-parent-setup-input')


def main():
    for mode in ('parent_search_launch', 'shell_search'):
        result = smoke(assets=ASSETS, provision_credentials=True, **{mode: True})
        if result:
            return result
    return 0


if __name__ == '__main__':
    sys.exit(main())
