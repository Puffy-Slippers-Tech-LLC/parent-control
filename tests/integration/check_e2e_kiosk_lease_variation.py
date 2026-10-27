#!/usr/bin/python3
"""Qualify owned stale-lease refusal and restored short public usability."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    return smoke(assets=named_input(package_source=True), provision_credentials=True,
                 kiosk_entry='lease-variation')


if __name__ == '__main__':
    sys.exit(main())
