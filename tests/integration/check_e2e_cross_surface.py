#!/usr/bin/python3
"""Qualify FLOW12's kiosk-to-overlay binding for both children."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    return smoke(assets=named_input(vm_source=True, fixture_source=True), provision_credentials=True,
                 challenges=True, challenge_profile='cross-surface')


if __name__ == '__main__':
    sys.exit(main())
