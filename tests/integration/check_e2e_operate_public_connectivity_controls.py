#!/usr/bin/python3
"""Qualify LIFE06 with a normal Parent control and independent public results."""
import sys

from check_graphical_smoke import main as smoke
from tools.test_storage import named_input

ASSETS = named_input()


def main():
    return smoke(assets=ASSETS, provision_credentials=True,
                 parent_toggle=True, public_connectivity_controls=True)


if __name__ == '__main__':
    sys.exit(main())
