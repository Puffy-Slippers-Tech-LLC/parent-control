#!/usr/bin/python3
"""Qualify checked-state events during synchronous public accessibility input."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    return smoke(assets=named_input(), provision_credentials=True, accessibility_input_trace=True)


if __name__ == '__main__':
    sys.exit(main())
