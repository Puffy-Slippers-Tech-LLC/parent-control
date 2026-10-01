#!/usr/bin/python3
"""Qualify native usable launch flows and immutable same-window activity reads."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    return smoke(assets=named_input(fixture_source=True), provision_credentials=True,
                 app_activity=True)


if __name__ == '__main__':
    sys.exit(main())
