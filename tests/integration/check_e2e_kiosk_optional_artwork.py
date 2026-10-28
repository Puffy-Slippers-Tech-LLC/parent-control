#!/usr/bin/python3
"""Verify missing optional scenery preserves entry, approval and restored requests."""
import sys

from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


if __name__ == '__main__':
    sys.exit(smoke(assets=named_input(package_source=True), provision_credentials=True,
                   confinement_usability='optional-artwork'))
