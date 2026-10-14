#!/usr/bin/python3
"""Installed kiosk Preferences confinement; no full preference feature history."""
import sys

from check_graphical_smoke import main as smoke
from tools.test_storage import named_input

ASSETS = named_input(package_source=True)

if __name__ == '__main__':
    sys.exit(smoke(assets=ASSETS, provision_credentials=True,
                   kiosk_preferences_confinement=True))
