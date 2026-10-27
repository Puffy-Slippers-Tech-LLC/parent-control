#!/usr/bin/python3
"""Qualify isolated system Remote Login readiness and exact restoration."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    return smoke(assets=named_input(package_source=True), provision_credentials=True,
                 kiosk_entry='remote-preparation')


if __name__ == '__main__':
    sys.exit(main())
