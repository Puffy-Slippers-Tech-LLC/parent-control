#!/usr/bin/python3
"""Fixed Shell approval and automatic return in one fresh guarded attempt."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    return smoke(assets=named_input(fixture_source=True), provision_credentials=True,
                 challenges=True, challenge_profile='overlay-approved-exit')


if __name__ == '__main__':
    sys.exit(main())
