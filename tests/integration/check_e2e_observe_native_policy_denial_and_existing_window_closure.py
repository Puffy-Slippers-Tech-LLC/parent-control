#!/usr/bin/python3
"""Qualify closure of captured child work after a Parent app block."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


if __name__ == '__main__':
    sys.exit(smoke(assets=named_input(package_source=True, fixture_source=True),
                   provision_credentials=True, native_policy_closure=True))
