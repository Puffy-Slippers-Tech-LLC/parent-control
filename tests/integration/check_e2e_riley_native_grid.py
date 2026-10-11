#!/usr/bin/python3
"""Qualify Riley's same-target grid launch and independently observed draft effect."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    return smoke(assets=named_input(vm_source=True, fixture_source=True), provision_credentials=True,
                 riley_native_grid=True)


if __name__ == '__main__':
    sys.exit(main())
