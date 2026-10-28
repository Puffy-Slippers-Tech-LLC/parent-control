#!/usr/bin/python3
"""Qualify brief admission contention and restored short public usability."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    return smoke(assets=named_input(package_source=True), provision_credentials=True,
                 kiosk_entry='admission-contention')


if __name__ == '__main__':
    sys.exit(main())
