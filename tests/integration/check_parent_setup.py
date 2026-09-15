#!/usr/bin/python3
"""Qualify E2E-030 setup using freshly built, source-verified fixed inputs."""

from pathlib import Path
import sys
from check_graphical_smoke import main

if __name__ == '__main__':
    sys.exit(main(assets=Path('/tmp/onpc-parent-setup-input'),
                  provision_credentials=True, parent_setup=True))
