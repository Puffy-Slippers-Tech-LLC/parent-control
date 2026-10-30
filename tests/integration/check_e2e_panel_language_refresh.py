#!/usr/bin/python3
"""Check that Riley's countdown follows an overlay language Save without extra time."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input

ASSETS = named_input(package_source=True)


def main():
    return smoke(assets=ASSETS, provision_credentials=True, panel_language_refresh=True)


if __name__ == '__main__':
    sys.exit(main())
