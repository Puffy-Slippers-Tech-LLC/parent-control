#!/usr/bin/python3
"""Qualify temporary identity-helper failure and restored public station use."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    return smoke(assets=named_input(package_source=True), provision_credentials=True,
                 kiosk_entry='identity-helper')


if __name__ == '__main__':
    sys.exit(main())
