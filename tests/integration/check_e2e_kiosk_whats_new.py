#!/usr/bin/python3
"""Qualify installed child release notes and the preserved station request."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


if __name__ == '__main__':
    sys.exit(smoke(assets=named_input(upgrade_source=True),
                   provision_credentials=True, kiosk_whats_new=True))
