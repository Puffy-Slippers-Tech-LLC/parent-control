#!/usr/bin/python3
"""Qualify public transition samples around caller-owned text input."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    return smoke(assets=named_input(), provision_credentials=True, trace_transition=True)


if __name__ == '__main__':
    sys.exit(main())
