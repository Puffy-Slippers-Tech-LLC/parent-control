#!/usr/bin/python3
"""Qualify a five-second guarded wait between independent About reads."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    return smoke(assets=named_input(), provision_credentials=True, real_interval=True)


if __name__ == '__main__':
    sys.exit(main())
