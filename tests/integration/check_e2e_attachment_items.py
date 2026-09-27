#!/usr/bin/python3
"""Qualify public attachment metadata and single-item removal; never Send."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    return smoke(assets=named_input(), provision_credentials=True, attachment_items=True)


if __name__ == '__main__':
    sys.exit(main())
