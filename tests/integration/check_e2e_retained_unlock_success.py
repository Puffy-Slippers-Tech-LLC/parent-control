#!/usr/bin/python3
"""Qualify independent direct and retained-GDM child unlock with preserved work."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input

ASSETS = named_input(vm_source=True, fixture_source=True)


def main():
    result = smoke(assets=ASSETS, provision_credentials=True, lock_surface='child-success')
    if result:
        return result
    return smoke(assets=ASSETS, provision_credentials=True, lock_surface='retained-success')


if __name__ == '__main__':
    sys.exit(main())
