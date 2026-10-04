#!/usr/bin/python3
"""Qualify two Chinese native kiosk approvals in the maintained envelope."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input

ASSETS = named_input(package_source=True)


def main():
    return smoke(assets=ASSETS, provision_credentials=True, chinese_native_auth=True)


if __name__ == '__main__':
    sys.exit(main())
