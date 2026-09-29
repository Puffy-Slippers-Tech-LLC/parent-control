#!/usr/bin/python3
"""Qualify the owned Parent privacy link without following it."""

import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input

ASSETS = named_input()


def main():
    return smoke(assets=ASSETS, provision_credentials=True,
                 license_viewer_provider=True, information_link='privacy')


if __name__ == '__main__':
    sys.exit(main())
