#!/usr/bin/python3
"""Check the child can copy and use the future-version and nonmatching apps."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


if __name__ == '__main__':
    sys.exit(smoke(assets=named_input(package_source=True, fixture_source=True),
                   provision_credentials=True, versioned_appimage_assets=True))
