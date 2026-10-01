#!/usr/bin/python3
"""Qualify native app-grid launch and independently observed normal app use."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    return smoke(assets=named_input(fixture_source=True), provision_credentials=True,
                 native_grid_usable=True)


if __name__ == '__main__':
    sys.exit(main())
