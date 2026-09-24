#!/usr/bin/python3
"""Qualify DESK04 logout and DESK03 switch in separate restored attempts."""

from pathlib import Path
import sys
from check_graphical_smoke import main as smoke

from tools.test_storage import named_input
ASSETS = named_input()


def main():
    result = smoke(assets=ASSETS, provision_credentials=True, desktop_session_logout=True)
    if result != 0:
        return result
    return smoke(assets=ASSETS, provision_credentials=True, desktop_session_switch=True)


if __name__ == '__main__':
    sys.exit(main())
