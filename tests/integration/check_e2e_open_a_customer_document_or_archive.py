#!/usr/bin/python3
"""Qualify bounded declared ZIP reads through the guarded installed envelope."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    return smoke(assets=named_input(), provision_credentials=True,
                 fresh_desktop='parent', archive_open=True)


if __name__ == '__main__':
    sys.exit(main())
