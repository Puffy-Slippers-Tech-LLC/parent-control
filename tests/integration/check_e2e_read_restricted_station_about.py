#!/usr/bin/python3
"""Qualify station About information, external-action absence and form return."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


if __name__ == '__main__':
    sys.exit(smoke(assets=named_input(), provision_credentials=True, restricted_station_about=True))
