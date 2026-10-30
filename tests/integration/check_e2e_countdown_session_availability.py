#!/usr/bin/python3
"""Child countdown unavailable while locked/at sign-in, restored on retained entry."""
import sys

from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    return smoke(assets=named_input(), provision_credentials=True,
                 challenges=True, challenge_profile='countdown-session')


if __name__ == '__main__':
    sys.exit(main())
