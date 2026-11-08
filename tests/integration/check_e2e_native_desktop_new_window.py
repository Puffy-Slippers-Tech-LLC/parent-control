#!/usr/bin/python3
"""Qualify desktop activation of a second S window while keeping original work."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


if __name__ == '__main__':
    sys.exit(smoke(assets=named_input(package_source=True, fixture_source=True),
                   provision_credentials=True, native_desktop_new_window=True))
