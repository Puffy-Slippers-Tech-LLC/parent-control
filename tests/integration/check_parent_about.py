#!/usr/bin/python3
"""Qualify the complete installed Parent consumer while its needles are reviewed."""

from pathlib import Path
import sys
from check_graphical_smoke import main

if __name__ == '__main__':
    from tools.test_storage import named_input
    sys.exit(main(assets=named_input(),
                  provision_credentials=True, parent_about=True))
