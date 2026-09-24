#!/usr/bin/python3
"""Qualify GDM recipient, refusal, freshness and Escape-return proofs."""

from pathlib import Path
import sys
from check_graphical_smoke import main as smoke

from tools.test_storage import named_input
ASSETS = named_input()


if __name__ == '__main__':
    sys.exit(smoke(
        assets=ASSETS, provision_credentials=True, gdm_recipient=True))
