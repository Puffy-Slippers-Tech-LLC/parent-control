#!/usr/bin/env python3
"""Task 004's fixed single-use challenge qualification in the owned VM."""

import sys

from check_graphical_smoke import main as smoke
from tools.test_storage import named_input

ASSETS = named_input()


def main():
    return smoke(assets=ASSETS, provision_credentials=True, challenges=True)


if __name__ == '__main__':
    sys.exit(main())
