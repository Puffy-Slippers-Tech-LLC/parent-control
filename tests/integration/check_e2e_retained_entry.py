#!/usr/bin/python3
"""Qualify explicit retained visits to both original child desktops."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    return smoke(assets=named_input(vm_source=True, fixture_source=True),
                 provision_credentials=True, parent_entry='retained-children')


if __name__ == '__main__':
    sys.exit(main())
