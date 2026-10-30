#!/usr/bin/python3
"""Qualify positive daily time combined with a real two-minute addition."""

import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    return smoke(assets=named_input(), provision_credentials=True, time_profiles_grant=True)


if __name__ == '__main__':
    sys.exit(main())
