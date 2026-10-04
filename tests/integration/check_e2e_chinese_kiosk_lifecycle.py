#!/usr/bin/python3
"""300e genuine upgrade and two-reboot Chinese initial kiosk qualification."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input

ASSETS = named_input(upgrade_source=True)


def main():
    return smoke(assets=ASSETS, provision_credentials=True, chinese_kiosk_lifecycle=True)


if __name__ == '__main__':
    sys.exit(main())
