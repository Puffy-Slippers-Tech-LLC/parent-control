#!/usr/bin/python3
"""Qualify a denied new game while Jordan's original game remains playable."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input

if __name__ == '__main__':
    sys.exit(smoke(assets=named_input(vm_source=True, fixture_source=True), provision_credentials=True,
                   native_app=True, fixture_profile='game', retained_game_denial=True))
