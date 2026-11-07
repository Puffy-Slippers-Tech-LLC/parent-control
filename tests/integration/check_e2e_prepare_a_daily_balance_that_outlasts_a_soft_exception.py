#!/usr/bin/python3
"""Qualify FLOW18 through its positive returned-child witness, before expiry."""
import sys

from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    return smoke(assets=named_input(), provision_credentials=True, daily_soft_profile=True)


if __name__ == '__main__':
    sys.exit(main())
