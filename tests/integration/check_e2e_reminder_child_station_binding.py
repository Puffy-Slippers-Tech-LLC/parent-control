#!/usr/bin/python3
"""Qualify Jordan overlay readback and Riley station deletion Save/Cancel."""
import sys

from check_graphical_smoke import main as smoke
from tools.test_storage import named_input

ASSETS = named_input(package_source=True)


def main():
    return smoke(assets=ASSETS, provision_credentials=True, reminder_child_station_binding=True)


if __name__ == '__main__':
    sys.exit(main())
