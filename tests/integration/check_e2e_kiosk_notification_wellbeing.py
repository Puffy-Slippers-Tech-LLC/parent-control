#!/usr/bin/python3
"""Installed public preview/settings engineering qualification, not a customer case."""
import sys

from check_graphical_smoke import main as smoke
from tools.test_storage import named_input

ASSETS = named_input(package_source=True)

if __name__ == '__main__':
    sys.exit(smoke(assets=ASSETS, provision_credentials=True,
                   kiosk_eligible_choices=True, kiosk_notification_wellbeing=True))
