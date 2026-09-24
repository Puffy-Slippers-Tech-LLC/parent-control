#!/usr/bin/python3
"""Qualify REQUEST04 eligible station accounts in the guarded installed VM."""

from pathlib import Path
import sys
from check_graphical_smoke import main as smoke

from tools.test_storage import named_input
ASSETS = named_input()


if __name__ == '__main__':
    sys.exit(smoke(assets=ASSETS, provision_credentials=True, kiosk_eligible_choices=True))
