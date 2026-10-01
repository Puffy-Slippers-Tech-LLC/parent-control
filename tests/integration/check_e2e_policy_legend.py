#!/usr/bin/python3
"""Qualify the complete public App Limits legend and unchanged Jordan policies."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input

if __name__ == '__main__':
    sys.exit(smoke(assets=named_input(fixture_source=True), provision_credentials=True,
                   app_row_observations=True, native_fixtures=True, policy_legend=True))
