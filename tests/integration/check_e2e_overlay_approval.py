#!/usr/bin/python3
"""048b: fresh immediate exit, then independent rejection/Cancel compositions."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    for profile in ('overlay-approval-immediate', 'overlay-flow-rejection', 'overlay-flow-cancel'):
        result = smoke(assets=named_input(fixture_source=True), provision_credentials=True,
                       challenges=True, challenge_profile=profile)
        if result:
            return result
    return 0


if __name__ == '__main__':
    sys.exit(main())
