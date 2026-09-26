#!/usr/bin/python3
"""Qualify invalid kiosk durations without opening authentication."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


if __name__ == '__main__':
    sys.exit(smoke(assets=named_input(), provision_credentials=True, request_duration=True))
