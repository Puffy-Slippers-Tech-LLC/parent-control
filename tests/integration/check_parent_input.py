#!/usr/bin/python3
"""Acquire the real installed Parent prompt without enabling password input."""

from pathlib import Path
import sys
from check_graphical_smoke import main

if __name__ == '__main__':
    from tools.test_storage import named_input
    sys.exit(main(assets=named_input(),
                  provision_credentials=True, parent_setup=True, parent_input=True))
