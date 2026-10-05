#!/usr/bin/python3
"""Qualify installed Parent Hebrew text and saved language functionality."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input

ASSETS = named_input(package_source=True)


def main():
    return smoke(assets=ASSETS, provision_credentials=True, parent_rtl=True)


if __name__ == '__main__':
    sys.exit(main())
