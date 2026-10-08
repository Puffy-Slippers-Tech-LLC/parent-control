#!/usr/bin/python3
"""305a: genuine unrelated package reboot request, no complete-case credit."""

import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input

ASSETS = named_input(package_source=True)


def main():
    return smoke(assets=ASSETS, provision_credentials=True, unrelated_reboot_request=True)


if __name__ == '__main__':
    sys.exit(main())
