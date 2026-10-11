#!/usr/bin/python3
"""Qualify PARENT17/18 warning, target safety and Cancel with a real grant."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    return smoke(assets=named_input(package_source=True), provision_credentials=True, revoke_cancel=True)


if __name__ == '__main__':
    sys.exit(main())
