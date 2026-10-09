#!/usr/bin/python3
"""Qualify retained Parent desktop/window entry without relaunch or reselection."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    return smoke(assets=named_input(vm_source=True), provision_credentials=True,
                 parent_entry='retained')


if __name__ == '__main__':
    sys.exit(main())
