#!/usr/bin/python3
"""300d finite genuine v1.2 installation, activation reboot and current upgrade."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input

ASSETS = named_input(upgrade_source=True)


def main():
    return smoke(assets=ASSETS, provision_credentials=True, package_upgrade=True)


if __name__ == '__main__':
    sys.exit(main())
