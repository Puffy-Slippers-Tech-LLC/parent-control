#!/usr/bin/python3
"""TIME02 minute progression through two independent public child samples."""
import sys

from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    return smoke(assets=named_input(), provision_credentials=True,
                 challenges=True, challenge_profile='countdown-minutes')


if __name__ == '__main__':
    sys.exit(main())
