#!/usr/bin/python3
"""Qualify one genuine MATE challenge across the finite 45-second human pause."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    return smoke(assets=named_input(package_source=True), provision_credentials=True,
                 baseline_auth_pause=True)


if __name__ == '__main__':
    sys.exit(main())
