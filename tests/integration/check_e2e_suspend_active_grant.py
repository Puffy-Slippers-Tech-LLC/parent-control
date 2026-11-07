#!/usr/bin/python3
"""Qualify normal sleep and same-child unlock with real active extra time."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


if __name__ == '__main__':
    sys.exit(smoke(assets=named_input(vm_source=True, fixture_source=True),
                   provision_credentials=True, suspend_active_grant=True))
