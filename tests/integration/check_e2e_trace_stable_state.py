#!/usr/bin/python3
"""Qualify readiness and explicit tokens for unchanged feedback samples."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    return smoke(assets=named_input(), provision_credentials=True, trace_stable_state=True)


if __name__ == '__main__':
    sys.exit(main())
