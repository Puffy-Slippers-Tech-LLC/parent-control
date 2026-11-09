#!/usr/bin/python3
"""Qualify raising daily time without clearing an existing real grant."""
import sys

from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    return smoke(assets=named_input(), provision_credentials=True, time_profiles_dominant=True)


if __name__ == '__main__':
    sys.exit(main())
