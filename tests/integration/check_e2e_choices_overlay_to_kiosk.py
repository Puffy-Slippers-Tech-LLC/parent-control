#!/usr/bin/python3
"""Qualify FLOW12's overlay-to-kiosk binding for both children."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    return smoke(assets=named_input(vm_source=True, fixture_source=True), provision_credentials=True,
                 challenges=True, challenge_profile='choices-overlay-to-kiosk')


if __name__ == '__main__':
    sys.exit(main())
