#!/usr/bin/python3
"""Qualify selected-child kiosk reminders and exact overlay saved-value continuity."""
import sys

from check_graphical_smoke import main as smoke
from tools.test_storage import named_input

ASSETS = named_input(package_source=True)


def main():
    return smoke(assets=ASSETS, provision_credentials=True, kiosk_reminder_binding=True)


if __name__ == '__main__':
    sys.exit(main())
