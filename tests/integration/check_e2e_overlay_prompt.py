#!/usr/bin/python3
"""Two independent Shell approval requests in one owned installed history."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    return smoke(assets=named_input(package_source=True), provision_credentials=True,
                 challenges=True, challenge_profile='overlay-prompt')


if __name__ == '__main__':
    sys.exit(main())
