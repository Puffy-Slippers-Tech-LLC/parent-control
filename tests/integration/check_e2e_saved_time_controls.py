#!/usr/bin/python3
"""Qualify the shared saved-time kiosk and overlay actions in two fixed slices."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    for profile in ('saved-time-kiosk', 'saved-time-overlay'):
        result = smoke(assets=named_input(package_source=True), provision_credentials=True,
                       challenges=True, challenge_profile=profile)
        if result:
            return result
    return 0


if __name__ == '__main__':
    sys.exit(main())
