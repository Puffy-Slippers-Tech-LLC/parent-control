#!/usr/bin/python3
"""Qualify PARENT08 saved/control snapshots on the installed Parent app."""

from pathlib import Path
import sys
from check_graphical_smoke import main as smoke

ASSETS = Path('/tmp/onpc-parent-setup-input')


if __name__ == '__main__':
    sys.exit(smoke(assets=ASSETS, provision_credentials=True, parent_toggle=True))
