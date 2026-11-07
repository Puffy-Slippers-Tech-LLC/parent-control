#!/usr/bin/python3
"""Qualify the added comma copy; reuse the delivered space-path mechanism."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


if __name__ == '__main__':
    sys.exit(smoke(assets=named_input(package_source=True, fixture_source=True),
                   provision_credentials=True, native_comma_path=True))
