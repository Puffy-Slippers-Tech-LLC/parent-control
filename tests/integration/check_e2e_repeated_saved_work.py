#!/usr/bin/python3
"""Qualify Jordan's repeated saves and retained work after natural exhaustion."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


if __name__ == '__main__':
    sys.exit(smoke(assets=named_input(package_source=True, fixture_source=True),
                   provision_credentials=True, repeated_saved_work=True))
