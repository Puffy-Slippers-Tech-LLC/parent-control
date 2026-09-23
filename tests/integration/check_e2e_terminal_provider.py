#!/usr/bin/python3
"""Qualify direct Parent-command denial from the standard desktop."""

from pathlib import Path
import sys
from check_graphical_smoke import main as smoke

ASSETS = Path('/tmp/onpc-parent-setup-input')


def main():
    return smoke(assets=ASSETS, provision_credentials=True,
                 parent_terminal_provider=True)


if __name__ == '__main__':
    sys.exit(main())
