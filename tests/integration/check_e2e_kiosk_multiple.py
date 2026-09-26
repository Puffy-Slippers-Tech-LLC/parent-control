#!/usr/bin/python3
"""Qualify FIX03's finite multiple-account profile under the shared VM lease."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input

if __name__ == '__main__':
    sys.exit(smoke(assets=named_input(), provision_credentials=True, kiosk_multiple=True))
