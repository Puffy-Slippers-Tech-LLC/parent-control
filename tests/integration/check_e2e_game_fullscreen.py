#!/usr/bin/python3
"""Play the fullscreen offline level before the original grant's natural lock."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input

if __name__ == '__main__':
    sys.exit(smoke(assets=named_input(vm_source=True, fixture_source=True), provision_credentials=True,
                   native_app=True, fixture_profile='game', game_expiry=True, game_mode='fullscreen'))
