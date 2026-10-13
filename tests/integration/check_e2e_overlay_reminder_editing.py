#!/usr/bin/python3
"""Qualify installed Riley overlay reminder Save/Cancel and empty-list readback."""
import sys

from check_graphical_smoke import main as smoke
from tools.test_storage import named_input

ASSETS = named_input(package_source=True)


def main():
    return smoke(assets=ASSETS, provision_credentials=True, overlay_reminder_editing=True)


if __name__ == '__main__':
    sys.exit(main())
