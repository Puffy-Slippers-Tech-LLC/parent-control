#!/usr/bin/python3
"""Qualify both station entry modes returning to the chosen child's original work."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    for profile in ('kiosk-retained-return-new', 'kiosk-retained-return-open'):
        result = smoke(assets=named_input(package_source=True), provision_credentials=True,
                       challenges=True, challenge_profile=profile)
        if result:
            return result
    return 0


if __name__ == '__main__':
    sys.exit(main())
