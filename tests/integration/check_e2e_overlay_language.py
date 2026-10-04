#!/usr/bin/python3
"""Qualify installed Riley overlay language selection and normal relaunch."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input

ASSETS = named_input(package_source=True)


def main():
    return smoke(assets=ASSETS, provision_credentials=True, overlay_language=True)


if __name__ == '__main__':
    sys.exit(main())
