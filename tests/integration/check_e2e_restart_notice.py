#!/usr/bin/python3
"""301 installed first-restart notice, all three surfaces and one normal reboot."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input

ASSETS = named_input(package_source=True)


def main():
    return smoke(assets=ASSETS, provision_credentials=True, restart_notice=True)


if __name__ == '__main__':
    sys.exit(main())
