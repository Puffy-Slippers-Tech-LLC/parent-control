#!/usr/bin/python3
"""Qualify kiosk rejection/Cancel in the shared owned attempt envelope."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


if __name__ == '__main__':
    sys.exit(smoke(assets=named_input(), provision_credentials=True, kiosk_rejection=True))
