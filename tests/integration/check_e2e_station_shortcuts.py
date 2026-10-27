#!/usr/bin/python3
"""Qualify request-session shortcuts and ordinary-desktop result controls."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


if __name__ == '__main__':
    sys.exit(smoke(assets=named_input(package_source=True), provision_credentials=True,
                   kiosk_entry='station-shortcuts'))
