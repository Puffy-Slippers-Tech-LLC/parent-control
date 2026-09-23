#!/usr/bin/python3
"""Qualify disabled-child availability in a fresh guarded installed attempt."""

from pathlib import Path
import sys
from check_graphical_smoke import main as smoke

ASSETS = Path('/tmp/onpc-parent-setup-input')


if __name__ == '__main__':
    sys.exit(smoke(assets=ASSETS, provision_credentials=True, request_choices=True))
