#!/usr/bin/python3
"""Qualify fixed kiosk approval and automatic GDM return in the owned envelope."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


if __name__ == '__main__':
    sys.exit(smoke(assets=named_input(), provision_credentials=True, kiosk_approval=True))
