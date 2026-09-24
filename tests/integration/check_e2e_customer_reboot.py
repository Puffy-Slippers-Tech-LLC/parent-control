#!/usr/bin/python3
"""007 fixed LIFE02 fresh install, customer reboot and administrator return."""

import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input

ASSETS = named_input()


def main():
    return smoke(assets=ASSETS, provision_credentials=True, customer_reboot=True)


if __name__ == '__main__':
    sys.exit(main())
