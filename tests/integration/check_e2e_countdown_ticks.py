#!/usr/bin/python3
"""TIME02 minute-to-seconds transition and two exact public decreases."""
import sys

from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    return smoke(assets=named_input(), provision_credentials=True,
                 challenges=True, challenge_profile='countdown-ticks')


if __name__ == '__main__':
    sys.exit(main())
