#!/usr/bin/python3
"""Qualify the complete installed Parent consumer while its needles are reviewed."""

from pathlib import Path
import sys
from check_graphical_smoke import main

if __name__ == '__main__':
    sys.exit(main(assets=Path('/tmp/onpc-parent-setup-input'),
                  provision_credentials=True, parent_about=True))
