#!/usr/bin/python3
"""Qualify command locking and independently supplied lock entry, without secrets."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input

ASSETS = named_input(vm_source=True)


def main():
    result = smoke(assets=ASSETS, provision_credentials=True, lock_surface='command')
    if result:
        return result
    return smoke(assets=ASSETS, provision_credentials=True, lock_surface='supplied')


if __name__ == '__main__':
    sys.exit(main())
