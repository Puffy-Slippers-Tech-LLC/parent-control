#!/usr/bin/python3
"""005a fixed product-free graphical entry qualification; no installation."""

import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input

ASSETS = named_input()


def main():
    return smoke(assets=ASSETS, provision_credentials=True, product_free_entry=True)


if __name__ == '__main__':
    sys.exit(main())
