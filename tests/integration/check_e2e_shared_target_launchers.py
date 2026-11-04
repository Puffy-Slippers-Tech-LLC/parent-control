#!/usr/bin/python3
"""Qualify Jordan's two Allowed native launchers sharing one target."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


if __name__ == '__main__':
    sys.exit(smoke(assets=named_input(package_source=True, fixture_source=True),
                   provision_credentials=True, shared_target_launchers=True))
