#!/usr/bin/python3
"""Qualify Parent saving and control inhibition during one public toggle."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    return smoke(assets=named_input(), provision_credentials=True, parent_save_trace=True)


if __name__ == '__main__':
    sys.exit(main())
