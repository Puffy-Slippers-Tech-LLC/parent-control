#!/usr/bin/python3
"""Qualify saved fullscreen reminder preference and main Cancel preservation."""
import sys

from check_graphical_smoke import main as smoke
from tools.test_storage import named_input

ASSETS = named_input(package_source=True)


def main():
    return smoke(assets=ASSETS, provision_credentials=True, reminder_fullscreen_preference=True)


if __name__ == '__main__':
    sys.exit(main())
