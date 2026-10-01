#!/usr/bin/python3
"""Qualify FLOW16's fresh Jordan thirty-minute binding."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    return smoke(assets=named_input(), provision_credentials=True,
                 fresh_thirty_allowance=True, fresh_thirty_child='existing')


if __name__ == '__main__':
    sys.exit(main())
