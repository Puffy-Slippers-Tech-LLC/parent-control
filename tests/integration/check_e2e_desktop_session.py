#!/usr/bin/python3
"""Qualify DESK02/03/04 with separate Switch User and confirmed Log Out attempts."""

from pathlib import Path
import sys
from check_graphical_smoke import main as smoke

ASSETS = Path('/tmp/onpc-parent-setup-input')


if __name__ == '__main__':
    status = smoke(assets=ASSETS, provision_credentials=True, desktop_session_logout=True)
    if status:
        sys.exit(status)
    sys.exit(smoke(assets=ASSETS, provision_credentials=True, desktop_session_switch=True))
