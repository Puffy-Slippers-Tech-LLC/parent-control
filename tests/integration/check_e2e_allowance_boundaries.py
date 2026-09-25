#!/usr/bin/python3
"""Qualify Task 040a in the existing guarded installed-product envelope."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    return smoke(assets=named_input(package_source=True), provision_credentials=True,
                 allowance_boundaries=True)


if __name__ == '__main__':
    sys.exit(main())
