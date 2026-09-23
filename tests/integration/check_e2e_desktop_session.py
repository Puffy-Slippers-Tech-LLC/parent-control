#!/usr/bin/python3
"""Qualify the shared DESK03 switch command on a fresh Parent desktop."""

from pathlib import Path
import sys
from check_graphical_smoke import main as smoke

ASSETS = Path('/tmp/onpc-parent-setup-input')


def main():
    return smoke(assets=ASSETS, provision_credentials=True, desktop_session_switch=True)


if __name__ == '__main__':
    sys.exit(main())
