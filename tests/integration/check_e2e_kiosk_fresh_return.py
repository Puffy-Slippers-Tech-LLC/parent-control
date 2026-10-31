#!/usr/bin/python3
"""Qualify new Riley/Jamie and independently open Jordan/Casey station requests."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    for profile in ('kiosk-fresh-return-new', 'kiosk-fresh-return-open'):
        result = smoke(assets=named_input(package_source=True), provision_credentials=True,
                       challenges=True, challenge_profile=profile)
        if result:
            return result
    return 0


if __name__ == '__main__':
    sys.exit(main())
