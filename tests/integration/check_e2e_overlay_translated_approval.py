#!/usr/bin/python3
"""Hebrew Riley request/success, English Shell approval and unchanged usable activity."""
import sys

from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    # Independent entries start from clean declared state, never a prior grant.
    for _ in range(2):
        result = smoke(assets=named_input(fixture_source=True), provision_credentials=True,
                       challenges=True, challenge_profile='overlay-translated-approval')
        if result:
            return result
    return 0


if __name__ == '__main__':
    sys.exit(main())
