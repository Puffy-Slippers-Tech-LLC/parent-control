#!/usr/bin/python3
"""Separate fresh wrong-password rejection and password-free Cancel attempts."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    for profile in ('overlay-rejection', 'overlay-prompt'):
        result = smoke(assets=named_input(package_source=True), provision_credentials=True,
                       challenges=True, challenge_profile=profile)
        if result:
            return result
    return 0


if __name__ == '__main__':
    sys.exit(main())
