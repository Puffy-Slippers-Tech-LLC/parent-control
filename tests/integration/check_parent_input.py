#!/usr/bin/python3
"""Acquire the real installed Parent prompt without enabling password input."""

from pathlib import Path
import sys
from check_graphical_smoke import main

if __name__ == '__main__':
    sys.exit(main(assets=Path('/tmp/onpc-parent-setup-input'),
                  provision_credentials=True, parent_setup=True, parent_input=True))
