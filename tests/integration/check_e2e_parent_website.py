#!/usr/bin/python3
"""Qualify the owned Parent website link without following it."""

import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input

ASSETS = named_input()


def main():
    return smoke(assets=ASSETS, provision_credentials=True,
                 license_viewer_provider=True, information_link='website')


if __name__ == '__main__':
    sys.exit(main())
