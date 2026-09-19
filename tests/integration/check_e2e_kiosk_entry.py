#!/usr/bin/python3
"""Qualify REQUEST01/03 on the prepared request station."""

from pathlib import Path
import sys
from check_graphical_smoke import main as smoke

ASSETS = Path('/tmp/onpc-parent-setup-input')


if __name__ == '__main__':
    sys.exit(smoke(assets=ASSETS, provision_credentials=True, kiosk_entry=True))
