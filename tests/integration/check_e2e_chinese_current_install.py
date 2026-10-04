#!/usr/bin/python3
"""300k fixed current-source install and Chinese untouched kiosk presentation."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input

ASSETS = named_input(package_source=True)


def main():
    return smoke(assets=ASSETS, provision_credentials=True, chinese_current_install=True)


if __name__ == '__main__':
    sys.exit(main())
