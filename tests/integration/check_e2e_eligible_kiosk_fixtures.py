#!/usr/bin/python3
"""Qualify FIX03's locked-approver exclusion and every retained eligible pair."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input

if __name__ == '__main__':
    sys.exit(smoke(assets=named_input(), provision_credentials=True, kiosk_ineligible=True))
