#!/usr/bin/python3
"""Qualify full public native match/access edits and independent row readback."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input

if __name__ == '__main__':
    sys.exit(smoke(assets=named_input(fixture_source=True), provision_credentials=True,
                   app_row_observations=True, native_fixtures=True, policy_edit=True))
