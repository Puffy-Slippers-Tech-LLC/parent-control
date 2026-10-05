#!/usr/bin/python3
"""Qualify named-child custom input, save traces and independent readback."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    return smoke(assets=named_input(package_source=True), provision_credentials=True,
                 custom_save_trace=True, named_child_custom_saves=True)


if __name__ == '__main__':
    sys.exit(main())
