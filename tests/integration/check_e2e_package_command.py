#!/usr/bin/python3
"""006 fixed LIFE04 install composition qualification."""

import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input

ASSETS = named_input()


def main():
    return smoke(assets=ASSETS, provision_credentials=True, package_install=True)


if __name__ == '__main__':
    sys.exit(main())
