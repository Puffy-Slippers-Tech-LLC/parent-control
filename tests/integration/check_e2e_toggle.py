#!/usr/bin/python3
"""Qualify UI17 on the installed Parent Screen time limit switch."""

from pathlib import Path
import sys
from check_graphical_smoke import main as smoke

ASSETS = Path('/tmp/onpc-parent-setup-input')


if __name__ == '__main__':
    sys.exit(smoke(assets=ASSETS, provision_credentials=True, parent_toggle=True))
