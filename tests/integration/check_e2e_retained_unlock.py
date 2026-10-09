#!/usr/bin/env python3
"""Qualify independent configured-zero retained GDM and actual lock denial."""

import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input

ASSETS = named_input(vm_source=True)


def main():
    result = smoke(assets=ASSETS, provision_credentials=True, lock_surface='retained-denied')
    if result:
        return result
    return smoke(assets=ASSETS, provision_credentials=True, lock_surface='child-denied')


if __name__ == '__main__':
    sys.exit(main())
