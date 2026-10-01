#!/usr/bin/python3
"""Qualify local invalid refusal and immediate Reset of a real saved wildcard."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input

if __name__ == '__main__':
    sys.exit(smoke(assets=named_input(fixture_source=True), provision_credentials=True,
                   app_row_observations=True, native_fixtures=True, match_editor=True))
