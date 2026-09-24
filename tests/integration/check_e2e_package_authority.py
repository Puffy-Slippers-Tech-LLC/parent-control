#!/usr/bin/python3
"""005 fixed package authority/completion qualification."""

import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input

ASSETS = named_input()


def main():
    return smoke(assets=ASSETS, provision_credentials=True, package_authority=True)


if __name__ == '__main__':
    sys.exit(main())
