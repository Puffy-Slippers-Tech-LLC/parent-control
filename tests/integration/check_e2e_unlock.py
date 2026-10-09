#!/usr/bin/python3
"""Qualify fresh child zero-time denial and normal return in the guarded VM."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    return smoke(assets=named_input(vm_source=True), provision_credentials=True,
                 challenges=True, challenge_profile='fresh-child-denied')


if __name__ == '__main__':
    sys.exit(main())
