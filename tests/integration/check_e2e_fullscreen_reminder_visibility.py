#!/usr/bin/python3
"""Qualify Riley's visible and suppressed warnings in independent game intervals."""
import sys

from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    for profile in ('fullscreen-reminder-visible', 'fullscreen-reminder-suppressed'):
        result = smoke(assets=named_input(fixture_source=True), provision_credentials=True,
                       challenges=True, challenge_profile=profile)
        if result:
            return result
    return 0


if __name__ == '__main__':
    sys.exit(main())
