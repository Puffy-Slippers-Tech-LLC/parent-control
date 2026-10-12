#!/usr/bin/python3
"""Qualify the installed child's countdown-animation preference and ownership."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    return smoke(assets=named_input(), provision_credentials=True,
                 challenges=True, challenge_profile='countdown-animation')


if __name__ == '__main__':
    sys.exit(main())
