#!/usr/bin/python3
"""Qualify ordinary Parent daily allowance presets in the guarded VM."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    return smoke(assets=named_input(), provision_credentials=True, allowance_presets=True)


if __name__ == '__main__':
    sys.exit(main())
