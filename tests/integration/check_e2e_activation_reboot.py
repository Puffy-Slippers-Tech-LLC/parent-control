#!/usr/bin/python3
"""139: real update, required reboot and usable saved Parent/child settings."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input

ASSETS = named_input(reboot_source=True)


def main():
    return smoke(assets=ASSETS, provision_credentials=True, activation_reboot=True)


if __name__ == '__main__':
    sys.exit(main())
