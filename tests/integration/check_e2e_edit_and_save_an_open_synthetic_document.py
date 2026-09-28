#!/usr/bin/python3
"""Qualify guarded synthetic source mutation, readback and owned cleanup."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    return smoke(assets=named_input(), provision_credentials=True,
                 fresh_desktop='parent', source_change=True)


if __name__ == '__main__':
    sys.exit(main())
