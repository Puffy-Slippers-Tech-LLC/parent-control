#!/usr/bin/python3
"""Qualify case 1's product-free GDM Parent navigation and return."""

from pathlib import Path
import sys
from check_graphical_smoke import main as smoke

ASSETS = Path('/tmp/onpc-parent-setup-input')


if __name__ == '__main__':
    sys.exit(smoke(
        assets=ASSETS, provision_credentials=True, gdm_product_free=True))
