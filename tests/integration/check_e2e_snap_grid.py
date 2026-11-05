#!/usr/bin/python3
"""Qualify allowed Snap grid launches and preserved work in two windows."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input

if __name__ == '__main__':
    sys.exit(smoke(assets=named_input(vm_source=True, fixture_source=True),
                   provision_credentials=True, native_grid_usable=True, fixture_profile='snap'))
