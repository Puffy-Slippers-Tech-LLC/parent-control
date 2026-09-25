#!/usr/bin/python3
"""Qualify FLOW01 same-user entry and FLOW16 in the guarded VM envelope."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    return smoke(assets=named_input(), provision_credentials=True, set_allowance=True)


if __name__ == '__main__':
    sys.exit(main())
