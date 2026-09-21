#!/usr/bin/python3
"""Qualify REQUEST11/12 kiosk Cancel and Escape on the prepared station."""

from pathlib import Path
import sys
from check_graphical_smoke import main as smoke

ASSETS = Path('/tmp/onpc-parent-setup-input')


if __name__ == '__main__':
    sys.exit(smoke(assets=ASSETS, provision_credentials=True, request_exit=True))
