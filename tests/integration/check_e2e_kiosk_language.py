#!/usr/bin/python3
"""Qualify installed Jordan kiosk personal language selection and persistence."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input

ASSETS = named_input(package_source=True)


def main():
    return smoke(assets=ASSETS, provision_credentials=True, kiosk_language=True)


if __name__ == '__main__':
    sys.exit(main())
