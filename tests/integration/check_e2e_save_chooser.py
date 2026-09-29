#!/usr/bin/python3
"""Qualify the real diagnostic Save and independent Cancel handoff."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    return smoke(assets=named_input(), provision_credentials=True, save_chooser=True)


if __name__ == '__main__':
    sys.exit(main())
