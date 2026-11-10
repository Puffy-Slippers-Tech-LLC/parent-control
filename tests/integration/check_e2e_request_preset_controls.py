#!/usr/bin/python3
"""Qualify saved request presets, restoration and Custom Hours at the station."""
import sys

from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


if __name__ == '__main__':
    sys.exit(smoke(assets=named_input(package_source=True), provision_credentials=True,
                   request_preset_controls=True))
