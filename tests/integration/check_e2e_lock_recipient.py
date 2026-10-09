#!/usr/bin/python3
"""Qualify the separate Parent lock recipient, without password delivery."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input

ASSETS = named_input(vm_source=True)


def main():
    return smoke(assets=ASSETS, provision_credentials=True, lock_surface='recipient')


if __name__ == '__main__':
    sys.exit(main())
