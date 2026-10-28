#!/usr/bin/python3
"""Qualify genuine kiosk update, activation and usable approval/reentry."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input

ASSETS = named_input(upgrade_source=True)


def main():
    return smoke(assets=ASSETS, provision_credentials=True, kiosk_entry='update-reentry')


if __name__ == '__main__':
    sys.exit(main())
