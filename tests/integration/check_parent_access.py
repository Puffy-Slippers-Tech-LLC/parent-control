#!/usr/bin/python3
"""Review E2E-004 screens; strict public execution owns customer acceptance."""

from pathlib import Path
import sys
from check_graphical_smoke import main

if __name__ == '__main__':
    sys.exit(main(assets=Path('/tmp/onpc-parent-setup-input'),
                  provision_credentials=True, parent_access=True))
