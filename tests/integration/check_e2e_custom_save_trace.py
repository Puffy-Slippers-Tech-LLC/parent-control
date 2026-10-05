#!/usr/bin/python3
"""Qualify saving during ordinary rapid custom allowance input."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    return smoke(assets=named_input(package_source=True), provision_credentials=True, custom_save_trace=True)


if __name__ == '__main__':
    sys.exit(main())
