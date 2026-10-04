#!/usr/bin/python3
"""Qualify fixed Jordan/German and Riley/Hebrew kiosk account restoration."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input

ASSETS = named_input(package_source=True)


def main():
    return smoke(assets=ASSETS, provision_credentials=True, kiosk_language_restoration=True)


if __name__ == '__main__':
    sys.exit(main())
